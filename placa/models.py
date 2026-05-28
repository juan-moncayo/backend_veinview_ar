# placa/models.py
from django.db import models
from django.utils import timezone
from estudiantes.models import Estudiante
from .constants import tecnica_correcta as evaluar_tecnica   # ← centralizado
import secrets


class DispositivoESP32(models.Model):
    """Dispositivo ESP32 para captura de datos de sensores."""
    nombre          = models.CharField(max_length=100, default="VeinView Device")
    mac_address     = models.CharField(max_length=17, unique=True,
                                       help_text="Formato: XX:XX:XX:XX:XX:XX")
    api_key         = models.CharField(max_length=64, unique=True, editable=False)
    activo          = models.BooleanField(default=True)
    fecha_registro  = models.DateTimeField(auto_now_add=True)
    ultima_conexion = models.DateTimeField(null=True, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name        = "Dispositivo ESP32"
        verbose_name_plural = "Dispositivos ESP32"
        ordering            = ["-fecha_registro"]

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.mac_address})"


class PracticaActiva(models.Model):
    """Control de prácticas activas."""
    ESTADOS = [
        ("iniciada",   "Iniciada"),
        ("pausada",    "Pausada"),
        ("finalizada", "Finalizada"),
    ]

    estudiante  = models.ForeignKey(Estudiante, on_delete=models.CASCADE,
                                    related_name="practicas")
    dispositivo = models.ForeignKey(DispositivoESP32, on_delete=models.CASCADE,
                                    related_name="practicas")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="iniciada")

    fecha_inicio      = models.DateTimeField(auto_now_add=True)
    fecha_pausa       = models.DateTimeField(null=True, blank=True)
    fecha_reanudacion = models.DateTimeField(null=True, blank=True)
    fecha_fin         = models.DateTimeField(null=True, blank=True)

    duracion_total_segundos = models.IntegerField(default=0,
                              help_text="Duración acumulada en segundos")

    numero_intentos    = models.IntegerField(default=0)
    intentos_exitosos  = models.IntegerField(default=0)
    precision_promedio = models.FloatField(default=0.0,
                         help_text="Precisión promedio (%)")

    class Meta:
        verbose_name        = "Práctica Activa"
        verbose_name_plural = "Prácticas Activas"
        ordering            = ["-fecha_inicio"]

    def __str__(self):
        return f"{self.estudiante.nombre_completo} - {self.estado}"

    # ── Transiciones de estado ──────────────────────────────────────────────

    def pausar(self):
        if self.estado != "iniciada":
            return
        self.estado      = "pausada"
        self.fecha_pausa = timezone.now()
        referencia = self.fecha_reanudacion or self.fecha_inicio
        self.duracion_total_segundos += int(
            (self.fecha_pausa - referencia).total_seconds()
        )
        self.save()

    def reanudar(self):
        if self.estado != "pausada":
            return
        self.estado            = "iniciada"
        self.fecha_reanudacion = timezone.now()
        self.save()

    def finalizar(self):
        if self.estado not in ("iniciada", "pausada"):
            return
        ahora = timezone.now()
        if self.estado == "iniciada":
            referencia = self.fecha_reanudacion or self.fecha_inicio
            self.duracion_total_segundos += int((ahora - referencia).total_seconds())
        self.estado    = "finalizada"
        self.fecha_fin = ahora
        self.calcular_metricas()
        self.save()

    # ── Métricas ────────────────────────────────────────────────────────────

    def calcular_metricas(self):
        datos = DatosSensor.objects.filter(practica=self)
        total = datos.count()

        if total == 0:
            self.precision_promedio = 0.0
            self.numero_intentos    = 0
            self.intentos_exitosos  = 0
            return

        correctos = datos.filter(tecnica_correcta=True).count()
        self.precision_promedio = round(correctos / total * 100, 2)

        DATOS_POR_INTENTO = 5
        if total >= 10:
            self.numero_intentos = total // DATOS_POR_INTENTO
        else:
            self.numero_intentos = 1

        proporcion = correctos / total if total > 0 else 0
        self.intentos_exitosos = int(self.numero_intentos * proporcion)
        if self.precision_promedio == 100.0 and self.intentos_exitosos == 0:
            self.intentos_exitosos = 1

    def registrar_intento(self, exitoso=False):
        self.numero_intentos += 1
        if exitoso:
            self.intentos_exitosos += 1
        self.save(update_fields=["numero_intentos", "intentos_exitosos"])


class DatosSensor(models.Model):
    """Datos capturados de los sensores MPU6050 y celda de carga."""
    practica    = models.ForeignKey(PracticaActiva, on_delete=models.CASCADE,
                                    related_name="datos_sensores")
    dispositivo = models.ForeignKey(DispositivoESP32, on_delete=models.CASCADE,
                                    related_name="datos")

    # MPU6050
    aceleracion_x = models.FloatField(help_text="Aceleración eje X (g)")
    aceleracion_y = models.FloatField(help_text="Aceleración eje Y (g)")
    aceleracion_z = models.FloatField(help_text="Aceleración eje Z (g)")
    giroscopio_x  = models.FloatField(help_text="Giroscopio eje X (°/s)")
    giroscopio_y  = models.FloatField(help_text="Giroscopio eje Y (°/s)")
    giroscopio_z  = models.FloatField(help_text="Giroscopio eje Z (°/s)")
    angulo_pitch  = models.FloatField(help_text="Ángulo pitch (°)")
    angulo_roll   = models.FloatField(help_text="Ángulo roll (°)")
    angulo_yaw    = models.FloatField(help_text="Ángulo yaw (°)")

    # Celda de carga
    fuerza  = models.FloatField(help_text="Fuerza aplicada (gramos-fuerza)")
    presion = models.FloatField(help_text="Presión calculada (N/cm²)",
                                null=True, blank=True)

    timestamp  = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_origen  = models.GenericIPAddressField(null=True, blank=True)

    # CORREGIDO: usa función centralizada de constants.py
    tecnica_correcta = models.BooleanField(default=False,
                       help_text="¿Datos dentro del rango óptimo?")

    class Meta:
        verbose_name        = "Dato de Sensor"
        verbose_name_plural = "Datos de Sensores"
        ordering            = ["-timestamp"]
        indexes = [
            models.Index(fields=["practica", "-timestamp"]),
            models.Index(fields=["dispositivo", "-timestamp"]),
        ]

    def save(self, *args, **kwargs):
        # Evaluación usando la función centralizada — misma lógica que alertas_ra()
        self.tecnica_correcta = evaluar_tecnica(self.angulo_pitch, self.fuerza)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Práctica {self.practica.id} - {self.timestamp.strftime('%H:%M:%S')}"