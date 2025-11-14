from django.db import models
from django.utils import timezone
from estudiantes.models import Estudiante
import secrets

class DispositivoESP32(models.Model):
    """Dispositivo ESP32 para captura de datos de sensores"""
    nombre = models.CharField(max_length=100, default="VeinView Device")
    mac_address = models.CharField(max_length=17, unique=True, help_text="Formato: XX:XX:XX:XX:XX:XX")
    api_key = models.CharField(max_length=64, unique=True, editable=False)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    ultima_conexion = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Dispositivo ESP32"
        verbose_name_plural = "Dispositivos ESP32"
        ordering = ['-fecha_registro']
    
    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nombre} ({self.mac_address})"


class PracticaActiva(models.Model):
    """Control de prácticas activas - solo un estudiante activo a la vez"""
    ESTADOS = [
        ('iniciada', 'Iniciada'),
        ('pausada', 'Pausada'),
        ('finalizada', 'Finalizada'),
    ]
    
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='practicas')
    dispositivo = models.ForeignKey(DispositivoESP32, on_delete=models.CASCADE, related_name='practicas')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='iniciada')
    
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_pausa = models.DateTimeField(null=True, blank=True)
    fecha_reanudacion = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    
    duracion_total_segundos = models.IntegerField(default=0, help_text="Duración acumulada en segundos")
    
    # NUEVO: Métricas de desempeño
    numero_intentos = models.IntegerField(default=0, help_text="Número de intentos de canalización")
    intentos_exitosos = models.IntegerField(default=0, help_text="Intentos con técnica correcta")
    precision_promedio = models.FloatField(default=0.0, help_text="Precisión promedio (%)")
    
    class Meta:
        verbose_name = "Práctica Activa"
        verbose_name_plural = "Prácticas Activas"
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"{self.estudiante.nombre_completo} - {self.estado}"
    
    def pausar(self):
        """Pausa la práctica actual"""
        if self.estado == 'iniciada':
            self.estado = 'pausada'
            self.fecha_pausa = timezone.now()
            if self.fecha_reanudacion:
                duracion = (self.fecha_pausa - self.fecha_reanudacion).total_seconds()
            else:
                duracion = (self.fecha_pausa - self.fecha_inicio).total_seconds()
            self.duracion_total_segundos += int(duracion)
            self.save()
    
    def reanudar(self):
        """Reanuda la práctica pausada"""
        if self.estado == 'pausada':
            self.estado = 'iniciada'
            self.fecha_reanudacion = timezone.now()
            self.save()
    
    def finalizar(self):
        """Finaliza la práctica y calcula métricas"""
        if self.estado in ['iniciada', 'pausada']:
            ahora = timezone.now()
            if self.estado == 'iniciada':
                if self.fecha_reanudacion:
                    duracion = (ahora - self.fecha_reanudacion).total_seconds()
                else:
                    duracion = (ahora - self.fecha_inicio).total_seconds()
                self.duracion_total_segundos += int(duracion)
            
            self.estado = 'finalizada'
            self.fecha_fin = ahora
            
            # Calcular métricas finales
            self.calcular_metricas()
            self.save()
    
    def calcular_metricas(self):
        """Calcula métricas de desempeño de la práctica"""
        datos = self.datos_sensores.all()
        if datos.exists():
            # Calcular precisión basada en ángulos y fuerza
            total_datos = datos.count()
            datos_correctos = datos.filter(
                angulo_pitch__gte=10,
                angulo_pitch__lte=30,
                fuerza__gte=50,
                fuerza__lte=300
            ).count()
            
            self.precision_promedio = (datos_correctos / total_datos * 100) if total_datos > 0 else 0
    
    def registrar_intento(self, exitoso=False):
        """Registra un nuevo intento de canalización"""
        self.numero_intentos += 1
        if exitoso:
            self.intentos_exitosos += 1
        self.save(update_fields=['numero_intentos', 'intentos_exitosos'])


class DatosSensor(models.Model):
    """Datos capturados de los sensores MPU6050 y celda de carga"""
    practica = models.ForeignKey(PracticaActiva, on_delete=models.CASCADE, related_name='datos_sensores')
    dispositivo = models.ForeignKey(DispositivoESP32, on_delete=models.CASCADE, related_name='datos')
    
    # Datos MPU6050 - Inclinación
    aceleracion_x = models.FloatField(help_text="Aceleración eje X (m/s²)")
    aceleracion_y = models.FloatField(help_text="Aceleración eje Y (m/s²)")
    aceleracion_z = models.FloatField(help_text="Aceleración eje Z (m/s²)")
    
    giroscopio_x = models.FloatField(help_text="Giroscopio eje X (°/s)")
    giroscopio_y = models.FloatField(help_text="Giroscopio eje Y (°/s)")
    giroscopio_z = models.FloatField(help_text="Giroscopio eje Z (°/s)")
    
    angulo_pitch = models.FloatField(help_text="Ángulo de inclinación pitch (°)")
    angulo_roll = models.FloatField(help_text="Ángulo de inclinación roll (°)")
    angulo_yaw = models.FloatField(help_text="Ángulo de inclinación yaw (°)")
    
    # Datos Celda de Carga - Presión/Fuerza
    fuerza = models.FloatField(help_text="Fuerza aplicada (gramos)")
    presion = models.FloatField(help_text="Presión calculada (N/cm²)", null=True, blank=True)
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    
    # NUEVO: Indicador de técnica correcta
    tecnica_correcta = models.BooleanField(default=False, help_text="¿Datos dentro de rango óptimo?")
    
    class Meta:
        verbose_name = "Dato de Sensor"
        verbose_name_plural = "Datos de Sensores"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['practica', '-timestamp']),
            models.Index(fields=['dispositivo', '-timestamp']),
        ]
    
    def save(self, *args, **kwargs):
        # Evaluar si la técnica es correcta basándose en rangos
        self.tecnica_correcta = (
            10 <= self.angulo_pitch <= 30 and
            50 <= self.fuerza <= 300
        )
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Práctica {self.practica.id} - {self.timestamp.strftime('%H:%M:%S')}"