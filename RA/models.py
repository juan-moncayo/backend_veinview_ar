from django.db import models
from placa.models import PracticaActiva, DatosSensor
from estudiantes.models import Estudiante
from django.utils import timezone


class SesionRA(models.Model):
    """
    Sesiones de Realidad Aumentada para visualización de prácticas
    """
    ESTADOS = [
        ('conectando', 'Conectando'),
        ('activa', 'Activa'),
        ('pausada', 'Pausada'),
        ('desconectada', 'Desconectada'),
        ('error', 'Error'),
    ]
    
    estudiante = models.ForeignKey(
        Estudiante, 
        on_delete=models.CASCADE, 
        related_name='sesiones_ra'
    )
    practica = models.ForeignKey(
        PracticaActiva,
        on_delete=models.CASCADE,
        related_name='sesiones_ra',
        null=True,
        blank=True
    )
    
    # Información de conexión
    session_token = models.CharField(max_length=64, unique=True, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    dispositivo_ra = models.CharField(max_length=100, help_text="Tipo de dispositivo RA (HoloLens, Meta Quest, etc.)")
    
    # Estado de la sesión
    estado = models.CharField(max_length=20, choices=ESTADOS, default='conectando')
    
    # Control de tiempo
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_ultima_actividad = models.DateTimeField(auto_now=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    
    # Configuración de visualización
    modo_visualizacion = models.CharField(
        max_length=50,
        default='overlay',
        help_text="Modo de visualización: overlay, hologram, mixed"
    )
    escala_modelo = models.FloatField(default=1.0, help_text="Escala del modelo 3D")
    opacidad = models.FloatField(default=0.8, help_text="Opacidad de 0.0 a 1.0")
    
    # Estadísticas de la sesión
    total_datos_recibidos = models.IntegerField(default=0)
    latencia_promedio = models.FloatField(default=0.0, help_text="Latencia promedio en ms")
    
    class Meta:
        verbose_name = "Sesión RA"
        verbose_name_plural = "Sesiones RA"
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"Sesión RA - {self.estudiante.nombre_completo} - {self.estado}"
    
    def save(self, *args, **kwargs):
        if not self.session_token:
            import secrets
            self.session_token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)
    
    def finalizar(self):
        """Finaliza la sesión RA"""
        self.estado = 'desconectada'
        self.fecha_fin = timezone.now()
        self.save()
    
    def esta_activa(self):
        """Verifica si la sesión está activa (menos de 30 segundos de inactividad)"""
        if self.estado not in ['activa', 'pausada']:
            return False
        
        tiempo_inactividad = timezone.now() - self.fecha_ultima_actividad
        return tiempo_inactividad.total_seconds() < 30


class DatosVisualizacionRA(models.Model):
    """
    Registro de datos enviados a la visualización RA
    """
    sesion = models.ForeignKey(
        SesionRA,
        on_delete=models.CASCADE,
        related_name='datos_visualizacion'
    )
    dato_sensor = models.ForeignKey(
        DatosSensor,
        on_delete=models.CASCADE,
        related_name='visualizaciones_ra'
    )
    
    # Metadata de envío
    timestamp_envio = models.DateTimeField(auto_now_add=True)
    timestamp_recepcion = models.DateTimeField(null=True, blank=True)
    latencia_ms = models.FloatField(null=True, blank=True, help_text="Latencia en milisegundos")
    
    # Estado de entrega
    entregado = models.BooleanField(default=False)
    error_entrega = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Dato de Visualización RA"
        verbose_name_plural = "Datos de Visualización RA"
        ordering = ['-timestamp_envio']
        indexes = [
            models.Index(fields=['sesion', '-timestamp_envio']),
        ]
    
    def __str__(self):
        return f"Dato RA - Sesión {self.sesion.id} - {self.timestamp_envio.strftime('%H:%M:%S')}"


class ConfiguracionRA(models.Model):
    """
    Configuración personalizada de visualización RA por estudiante
    """
    estudiante = models.OneToOneField(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='config_ra'
    )
    
    # Preferencias de visualización
    color_angulo_correcto = models.CharField(max_length=7, default='#00FF00', help_text="Color hex para ángulos correctos")
    color_angulo_incorrecto = models.CharField(max_length=7, default='#FF0000', help_text="Color hex para ángulos incorrectos")
    color_fuerza_correcta = models.CharField(max_length=7, default='#0000FF', help_text="Color hex para fuerza correcta")
    
    # Opciones de interfaz
    mostrar_grid = models.BooleanField(default=True, help_text="Mostrar grilla de referencia")
    mostrar_angulos = models.BooleanField(default=True, help_text="Mostrar valores de ángulos")
    mostrar_fuerza = models.BooleanField(default=True, help_text="Mostrar valores de fuerza")
    mostrar_historial = models.BooleanField(default=True, help_text="Mostrar gráfico de historial")
    
    # Audio
    audio_feedback = models.BooleanField(default=True, help_text="Activar feedback de audio")
    volumen = models.FloatField(default=0.5, help_text="Volumen de 0.0 a 1.0")
    
    # Frecuencia de actualización
    fps_objetivo = models.IntegerField(default=30, help_text="FPS objetivo para actualización")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración RA"
        verbose_name_plural = "Configuraciones RA"
    
    def __str__(self):
        return f"Config RA - {self.estudiante.nombre_completo}"


class EventoRA(models.Model):
    """
    Registro de eventos importantes en sesiones RA
    """
    TIPOS_EVENTO = [
        ('conexion', 'Conexión Establecida'),
        ('desconexion', 'Desconexión'),
        ('error', 'Error'),
        ('cambio_config', 'Cambio de Configuración'),
        ('inicio_practica', 'Inicio de Práctica'),
        ('fin_practica', 'Fin de Práctica'),
        ('calibracion', 'Calibración'),
    ]
    
    sesion = models.ForeignKey(
        SesionRA,
        on_delete=models.CASCADE,
        related_name='eventos'
    )
    
    tipo = models.CharField(max_length=20, choices=TIPOS_EVENTO)
    descripcion = models.TextField()
    datos_adicionales = models.JSONField(null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Evento RA"
        verbose_name_plural = "Eventos RA"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"