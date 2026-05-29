# placa/models.py
from django.db import models
from django.utils import timezone
from estudiantes.models import Estudiante
from .constants import tecnica_correcta as evaluar_tecnica
import secrets


class DispositivoESP32(models.Model):
    nombre          = models.CharField(max_length=100, default="VeinView Device")
    mac_address     = models.CharField(max_length=17, unique=True)
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
    ESTADOS = [
        ("iniciada",   "Iniciada"),
        ("pausada",    "Pausada"),
        ("finalizada", "Finalizada"),
    ]

    TIPOS = [
        ("examen",  "Examen — iniciada por profesor"),
        ("prueba",  "Prueba — iniciada por estudiante"),
    ]

    estudiante  = models.ForeignKey(Estudiante, on_delete=models.CASCADE,
                                    related_name="practicas")
    dispositivo = models.ForeignKey(DispositivoESP32, on_delete=models.CASCADE,
                                    related_name="practicas")

    estado = models.CharField(max_length=20, choices=ESTADOS, default="iniciada")
    tipo   = models.CharField(max_length=10, choices=TIPOS, default="examen")

    fecha_inicio      = models.DateTimeField(auto_now_add=True)
    fecha_pausa       = models.DateTimeField(null=True, blank=True)
    fecha_reanudacion = models.DateTimeField(null=True, blank=True)
    fecha_fin         = models.DateTimeField(null=True, blank=True)

    duracion_total_segundos = models.IntegerField(default=0)

    numero_intentos    = models.IntegerField(default=0)
    intentos_exitosos  = models.IntegerField(default=0)
    precision_promedio = models.FloatField(default=0.0)

    # Para detectar inactividad del sensor
    ultima_actividad_sensor = models.DateTimeField(null=True, blank=True)
    ultima_fuerza_sensor    = models.FloatField(default=0.0)

    class Meta:
        verbose_name        = "Práctica Activa"
        verbose_name_plural = "Prácticas Activas"
        ordering            = ["-fecha_inicio"]

    def __str__(self):
        return f"{self.estudiante.nombre_completo} - {self.tipo} - {self.estado}"

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
        self.numero_intentos = max(1, total // DATOS_POR_INTENTO)

        proporcion = correctos / total if total > 0 else 0
        self.intentos_exitosos = int(self.numero_intentos * proporcion)

    def registrar_intento(self, exitoso=False):
        self.numero_intentos += 1
        if exitoso:
            self.intentos_exitosos += 1
        self.save(update_fields=["numero_intentos", "intentos_exitosos"])

    def verificar_inactividad(self):
        """
        Retorna True si la práctica debe finalizarse por inactividad.
        Inactividad = sin movimiento de fuerza significativo en 5 minutos.
        Umbral de ruido: 20g de diferencia.
        """
        if self.estado != "iniciada":
            return False
        if not self.ultima_actividad_sensor:
            # Si nunca hubo lectura, dar 5 minutos desde inicio
            limite = self.fecha_inicio + timezone.timedelta(minutes=5)
            return timezone.now() > limite
        limite = self.ultima_actividad_sensor + timezone.timedelta(minutes=5)
        return timezone.now() > limite


class DatosSensor(models.Model):
    practica    = models.ForeignKey(PracticaActiva, on_delete=models.CASCADE,
                                    related_name="datos_sensores")
    dispositivo = models.ForeignKey(DispositivoESP32, on_delete=models.CASCADE,
                                    related_name="datos")

    aceleracion_x = models.FloatField()
    aceleracion_y = models.FloatField()
    aceleracion_z = models.FloatField()
    giroscopio_x  = models.FloatField()
    giroscopio_y  = models.FloatField()
    giroscopio_z  = models.FloatField()
    angulo_pitch  = models.FloatField()
    angulo_roll   = models.FloatField()
    angulo_yaw    = models.FloatField()

    fuerza  = models.FloatField()
    presion = models.FloatField(null=True, blank=True)

    timestamp  = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_origen  = models.GenericIPAddressField(null=True, blank=True)

    tecnica_correcta = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "Dato de Sensor"
        verbose_name_plural = "Datos de Sensores"
        ordering            = ["-timestamp"]
        indexes = [
            models.Index(fields=["practica", "-timestamp"]),
            models.Index(fields=["dispositivo", "-timestamp"]),
        ]

    def save(self, *args, **kwargs):
        self.tecnica_correcta = evaluar_tecnica(self.angulo_pitch, self.fuerza)
        super().save(*args, **kwargs)
        # Actualizar actividad del sensor en la práctica
        self._actualizar_actividad_practica()

    def _actualizar_actividad_practica(self):
        """
        Actualiza ultima_actividad_sensor si la fuerza cambió más de 20g
        respecto a la última lectura (umbral de ruido del sensor).
        """
        try:
            practica = self.practica
            diferencia = abs(self.fuerza - practica.ultima_fuerza_sensor)
            if diferencia >= 20.0:
                PracticaActiva.objects.filter(pk=practica.pk).update(
                    ultima_actividad_sensor=timezone.now(),
                    ultima_fuerza_sensor=self.fuerza,
                )
        except Exception:
            pass

    def __str__(self):
        return f"Práctica {self.practica.id} - {self.timestamp.strftime('%H:%M:%S')}"