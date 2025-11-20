from rest_framework import serializers
from .models import SesionRA, DatosVisualizacionRA, ConfiguracionRA, EventoRA
from estudiantes.models import Estudiante
from placa.models import PracticaActiva, DatosSensor


class SesionRASerializer(serializers.ModelSerializer):
    """Serializer para sesiones RA"""
    estudiante_nombre = serializers.CharField(source='estudiante.nombre_completo', read_only=True)
    estudiante_codigo = serializers.CharField(source='estudiante.codigo_estudiante', read_only=True)
    practica_id = serializers.IntegerField(source='practica.id', read_only=True, allow_null=True)
    tiempo_activo = serializers.SerializerMethodField()
    
    class Meta:
        model = SesionRA
        fields = [
            'id', 'estudiante', 'estudiante_nombre', 'estudiante_codigo',
            'practica', 'practica_id', 'session_token', 'ip_address',
            'dispositivo_ra', 'estado', 'fecha_inicio', 'fecha_ultima_actividad',
            'fecha_fin', 'modo_visualizacion', 'escala_modelo', 'opacidad',
            'total_datos_recibidos', 'latencia_promedio', 'tiempo_activo'
        ]
        read_only_fields = ['session_token', 'fecha_inicio', 'fecha_ultima_actividad', 'fecha_fin']
    
    def get_tiempo_activo(self, obj):
        """Calcula el tiempo activo en segundos"""
        from django.utils import timezone
        if obj.fecha_fin:
            return int((obj.fecha_fin - obj.fecha_inicio).total_seconds())
        return int((timezone.now() - obj.fecha_inicio).total_seconds())


class SesionRACreateSerializer(serializers.Serializer):
    """Serializer para crear una nueva sesión RA"""
    estudiante_id = serializers.IntegerField()
    practica_id = serializers.IntegerField(required=False, allow_null=True)
    dispositivo_ra = serializers.CharField(max_length=100)
    modo_visualizacion = serializers.CharField(max_length=50, default='overlay')
    escala_modelo = serializers.FloatField(default=1.0, min_value=0.1, max_value=10.0)
    opacidad = serializers.FloatField(default=0.8, min_value=0.0, max_value=1.0)
    
    def validate_estudiante_id(self, value):
        """Validar que el estudiante existe"""
        try:
            Estudiante.objects.get(id=value)
        except Estudiante.DoesNotExist:
            raise serializers.ValidationError("Estudiante no encontrado")
        return value
    
    def validate_practica_id(self, value):
        """Validar que la práctica existe y está activa"""
        if value:
            try:
                practica = PracticaActiva.objects.get(id=value)
                if practica.estado not in ['iniciada', 'pausada']:
                    raise serializers.ValidationError("La práctica debe estar iniciada o pausada")
            except PracticaActiva.DoesNotExist:
                raise serializers.ValidationError("Práctica no encontrada")
        return value


class DatosVisualizacionRASerializer(serializers.ModelSerializer):
    """Serializer para datos de visualización RA"""
    class Meta:
        model = DatosVisualizacionRA
        fields = [
            'id', 'sesion', 'dato_sensor', 'timestamp_envio',
            'timestamp_recepcion', 'latencia_ms', 'entregado', 'error_entrega'
        ]
        read_only_fields = ['timestamp_envio']


class ConfiguracionRASerializer(serializers.ModelSerializer):
    """Serializer para configuración RA"""
    estudiante_nombre = serializers.CharField(source='estudiante.nombre_completo', read_only=True)
    
    class Meta:
        model = ConfiguracionRA
        fields = [
            'id', 'estudiante', 'estudiante_nombre',
            'color_angulo_correcto', 'color_angulo_incorrecto', 'color_fuerza_correcta',
            'mostrar_grid', 'mostrar_angulos', 'mostrar_fuerza', 'mostrar_historial',
            'audio_feedback', 'volumen', 'fps_objetivo',
            'fecha_creacion', 'fecha_modificacion'
        ]
        read_only_fields = ['fecha_creacion', 'fecha_modificacion']


class EventoRASerializer(serializers.ModelSerializer):
    """Serializer para eventos RA"""
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = EventoRA
        fields = [
            'id', 'sesion', 'tipo', 'tipo_display',
            'descripcion', 'datos_adicionales', 'timestamp'
        ]
        read_only_fields = ['timestamp']


class DatosSensorRASerializer(serializers.ModelSerializer):
    """
    Serializer optimizado para enviar datos de sensores a Unreal Engine
    Solo incluye los campos necesarios para la visualización
    """
    timestamp_unix = serializers.SerializerMethodField()
    
    class Meta:
        model = DatosSensor
        fields = [
            'id', 'timestamp', 'timestamp_unix',
            'angulo_pitch', 'angulo_roll', 'angulo_yaw',
            'fuerza', 'presion',
            'aceleracion_x', 'aceleracion_y', 'aceleracion_z',
            'giroscopio_x', 'giroscopio_y', 'giroscopio_z',
            'tecnica_correcta'
        ]
    
    def get_timestamp_unix(self, obj):
        """Convierte timestamp a Unix timestamp para Unreal Engine"""
        import time
        return int(time.mktime(obj.timestamp.timetuple()) * 1000)


class StreamDatosRASerializer(serializers.Serializer):
    """
    Serializer para el stream de datos a Unreal Engine
    Formato optimizado para bajo uso de ancho de banda
    """
    session_token = serializers.CharField()
    timestamp = serializers.IntegerField(help_text="Unix timestamp en ms")
    
    # Datos del sensor (optimizados)
    pitch = serializers.FloatField()
    roll = serializers.FloatField()
    yaw = serializers.FloatField()
    fuerza = serializers.FloatField()
    presion = serializers.FloatField(allow_null=True)
    
    # Estado
    tecnica_correcta = serializers.BooleanField()
    
    # Metadata opcional
    practica_id = serializers.IntegerField(required=False, allow_null=True)
    dato_id = serializers.IntegerField(required=False, allow_null=True)


class EstadoPracticaRASerializer(serializers.Serializer):
    """
    Serializer para enviar el estado completo de una práctica a Unreal Engine
    """
    practica_activa = serializers.BooleanField()
    practica_id = serializers.IntegerField(allow_null=True)
    estudiante_nombre = serializers.CharField(allow_null=True)
    estado = serializers.CharField(allow_null=True)
    
    # Métricas en tiempo real
    tiempo_transcurrido = serializers.IntegerField()
    numero_intentos = serializers.IntegerField()
    precision_actual = serializers.FloatField()
    
    # Último dato
    ultimo_dato = serializers.DictField(allow_null=True)
    
    # Rangos óptimos para visualización
    rangos_optimos = serializers.DictField()


class RespuestaConexionRASerializer(serializers.Serializer):
    """
    Serializer para la respuesta de conexión exitosa
    """
    status = serializers.CharField()
    message = serializers.CharField()
    session_token = serializers.CharField()
    sesion_id = serializers.IntegerField()
    
    # Información del estudiante
    estudiante = serializers.DictField()
    
    # Configuración inicial
    configuracion = serializers.DictField()
    
    # URLs de endpoints
    endpoints = serializers.DictField()


class HeartbeatSerializer(serializers.Serializer):
    """
    Serializer para el heartbeat (mantener sesión activa)
    """
    session_token = serializers.CharField()
    timestamp = serializers.IntegerField()
    latencia_cliente = serializers.FloatField(required=False, allow_null=True)