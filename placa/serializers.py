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
    estudiante = EstudianteSimpleSerializer(read_only=True)
    tiempo_transcurrido = serializers.SerializerMethodField()
    
    class Meta:
        model = PracticaActiva
        fields = ['id', 'estudiante', 'estado', 'fecha_inicio', 'fecha_fin', 
                  'duracion_total_segundos', 'tiempo_transcurrido']
    
    def get_tiempo_transcurrido(self, obj):
        from django.utils import timezone
        if obj.estado == 'finalizada':
            return obj.duracion_total_segundos
        elif obj.estado == 'pausada':
            return obj.duracion_total_segundos
        else:  # iniciada
            ahora = timezone.now()
            if obj.fecha_reanudacion:
                tiempo_actual = (ahora - obj.fecha_reanudacion).total_seconds()
            else:
                tiempo_actual = (ahora - obj.fecha_inicio).total_seconds()
            return int(obj.duracion_total_segundos + tiempo_actual)


class DatosSensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatosSensor
        fields = [
            'id', 'practica', 'dispositivo',
            'aceleracion_x', 'aceleracion_y', 'aceleracion_z',
            'giroscopio_x', 'giroscopio_y', 'giroscopio_z',
            'angulo_pitch', 'angulo_roll', 'angulo_yaw',
            'fuerza', 'presion', 'timestamp'
        ]
        read_only_fields = ['timestamp']


class DatosSensorCreateSerializer(serializers.Serializer):
    """Serializer para recibir datos del ESP32"""
    # MPU6050
    ax = serializers.FloatField()
    ay = serializers.FloatField()
    az = serializers.FloatField()
    gx = serializers.FloatField()
    gy = serializers.FloatField()
    gz = serializers.FloatField()
    pitch = serializers.FloatField()
    roll = serializers.FloatField()
    yaw = serializers.FloatField()
    
    # Celda de carga
    fuerza = serializers.FloatField()
    presion = serializers.FloatField(required=False, allow_null=True)