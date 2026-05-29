from rest_framework import serializers
from .models import DispositivoESP32, PracticaActiva, DatosSensor
from estudiantes.models import Estudiante


class DispositivoESP32Serializer(serializers.ModelSerializer):
    class Meta:
        model = DispositivoESP32
        fields = ['id', 'nombre', 'mac_address', 'activo', 'ultima_conexion', 'ip_address']
        read_only_fields = ['api_key']


class EstudianteSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estudiante
        fields = ['id', 'codigo_estudiante', 'nombre_completo']


class PracticaActivaSerializer(serializers.ModelSerializer):
    estudiante          = EstudianteSimpleSerializer(read_only=True)
    tiempo_transcurrido = serializers.SerializerMethodField()

    class Meta:
        model = PracticaActiva
        fields = [
            'id', 'estudiante', 'estado', 'tipo',
            'fecha_inicio', 'fecha_fin',
            'duracion_total_segundos', 'tiempo_transcurrido',
            'numero_intentos', 'intentos_exitosos', 'precision_promedio',
            'ultima_actividad_sensor',
        ]

    def get_tiempo_transcurrido(self, obj):
        from django.utils import timezone
        if obj.estado in ('finalizada', 'pausada'):
            return obj.duracion_total_segundos
        ahora = timezone.now()
        referencia = obj.fecha_reanudacion or obj.fecha_inicio
        return int(obj.duracion_total_segundos + (ahora - referencia).total_seconds())


class DatosSensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatosSensor
        fields = [
            'id', 'practica', 'dispositivo',
            'aceleracion_x', 'aceleracion_y', 'aceleracion_z',
            'giroscopio_x', 'giroscopio_y', 'giroscopio_z',
            'angulo_pitch', 'angulo_roll', 'angulo_yaw',
            'fuerza', 'presion', 'timestamp', 'tecnica_correcta'
        ]
        read_only_fields = ['timestamp']


class DatosSensorCreateSerializer(serializers.Serializer):
    ax     = serializers.FloatField()
    ay     = serializers.FloatField()
    az     = serializers.FloatField()
    gx     = serializers.FloatField()
    gy     = serializers.FloatField()
    gz     = serializers.FloatField()
    pitch  = serializers.FloatField()
    roll   = serializers.FloatField()
    yaw    = serializers.FloatField()
    fuerza = serializers.FloatField()
    presion = serializers.FloatField(required=False, allow_null=True)