from rest_framework import serializers
from .models import ResumenPractica, EncuestaSistema, ReporteGeneral
from placa.models import PracticaActiva, DatosSensor
from estudiantes.models import Estudiante


class ResumenPracticaSerializer(serializers.ModelSerializer):
    """Serializer para resúmenes de prácticas"""
    estudiante_nombre = serializers.CharField(source='practica.estudiante.nombre_completo', read_only=True)
    estudiante_codigo = serializers.CharField(source='practica.estudiante.codigo_estudiante', read_only=True)
    fecha_practica = serializers.DateTimeField(source='practica.fecha_inicio', read_only=True)
    duracion_minutos = serializers.SerializerMethodField()
    
    class Meta:
        model = ResumenPractica
        fields = [
            'id', 'practica', 'profesor',
            'estudiante_nombre', 'estudiante_codigo', 'fecha_practica',
            'total_datos_capturados', 'inclinacion_promedio', 
            'fuerza_promedio', 'fuerza_maxima', 'fuerza_minima',
            'numero_intentos', 'intentos_exitosos', 'precision_porcentaje',
            'tiempo_canalizacion', 'duracion_minutos',
            'calificacion', 'observaciones',
            'tecnica_correcta', 'angulo_adecuado', 'presion_controlada',
            'fecha_evaluacion'
        ]
        read_only_fields = ['fecha_evaluacion']
    
    def get_duracion_minutos(self, obj):
        """Convierte duración a minutos"""
        return round(obj.tiempo_canalizacion / 60, 2)


class ResumenPracticaCreateSerializer(serializers.Serializer):
    """Serializer para crear resumen y calcular estadísticas automáticamente"""
    practica_id = serializers.IntegerField()
    calcular_automatico = serializers.BooleanField(default=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)
    
    def validate_practica_id(self, value):
        """Validar que la práctica existe y está finalizada"""
        try:
            practica = PracticaActiva.objects.get(id=value)
        except PracticaActiva.DoesNotExist:
            raise serializers.ValidationError("Práctica no encontrada")
        
        if practica.estado != 'finalizada':
            raise serializers.ValidationError("La práctica debe estar finalizada para generar resumen")
        
        if hasattr(practica, 'resumen'):
            raise serializers.ValidationError("Esta práctica ya tiene un resumen generado")
        
        return value


class EncuestaSistemaSerializer(serializers.ModelSerializer):
    """Serializer para encuestas del sistema"""
    estudiante_nombre = serializers.CharField(source='estudiante.nombre_completo', read_only=True)
    puntuacion_promedio = serializers.ReadOnlyField()
    
    class Meta:
        model = EncuestaSistema
        fields = [
            'id', 'estudiante', 'estudiante_nombre', 'practica',
            'facilidad_uso', 'utilidad_sistema', 'precision_sensores',
            'interfaz_clara', 'mejora_aprendizaje',
            'aspectos_positivos', 'aspectos_negativos', 'sugerencias',
            'recomendaria', 'puntuacion_promedio',
            'fecha_respuesta'
        ]
        read_only_fields = ['fecha_respuesta', 'puntuacion_promedio']


class EncuestaSistemaCreateSerializer(serializers.Serializer):
    """Serializer para crear encuestas desde el frontend"""
    estudiante_id = serializers.IntegerField()
    practica_id = serializers.IntegerField(required=False, allow_null=True)
    
    facilidad_uso = serializers.IntegerField(min_value=1, max_value=5)
    utilidad_sistema = serializers.IntegerField(min_value=1, max_value=5)
    precision_sensores = serializers.IntegerField(min_value=1, max_value=5)
    interfaz_clara = serializers.IntegerField(min_value=1, max_value=5)
    mejora_aprendizaje = serializers.IntegerField(min_value=1, max_value=5)
    
    aspectos_positivos = serializers.CharField(required=False, allow_blank=True)
    aspectos_negativos = serializers.CharField(required=False, allow_blank=True)
    sugerencias = serializers.CharField(required=False, allow_blank=True)
    recomendaria = serializers.BooleanField(default=True)
    
    def validate_estudiante_id(self, value):
        """Validar que el estudiante existe"""
        try:
            Estudiante.objects.get(id=value)
        except Estudiante.DoesNotExist:
            raise serializers.ValidationError("Estudiante no encontrado")
        return value
    
    def validate_practica_id(self, value):
        """Validar que la práctica existe si se proporciona"""
        if value:
            try:
                PracticaActiva.objects.get(id=value)
            except PracticaActiva.DoesNotExist:
                raise serializers.ValidationError("Práctica no encontrada")
        return value


class ReporteGeneralSerializer(serializers.ModelSerializer):
    """Serializer para reportes generales"""
    generado_por_nombre = serializers.CharField(source='generado_por.get_full_name', read_only=True)
    periodo = serializers.SerializerMethodField()
    
    class Meta:
        model = ReporteGeneral
        fields = [
            'id', 'titulo', 'fecha_inicio', 'fecha_fin', 'periodo',
            'generado_por', 'generado_por_nombre',
            'total_estudiantes', 'total_practicas', 'total_datos_capturados',
            'promedio_precision', 'promedio_intentos', 'promedio_tiempo',
            'promedio_calificacion', 'promedio_satisfaccion', 'total_encuestas',
            'fecha_generacion'
        ]
        read_only_fields = ['fecha_generacion']
    
    def get_periodo(self, obj):
        """Formato legible del período"""
        return f"{obj.fecha_inicio.strftime('%d/%m/%Y')} - {obj.fecha_fin.strftime('%d/%m/%Y')}"


class ReporteGeneralCreateSerializer(serializers.Serializer):
    """Serializer para crear reportes generales"""
    titulo = serializers.CharField(max_length=200, default="Reporte de Desempeño")
    fecha_inicio = serializers.DateTimeField()
    fecha_fin = serializers.DateTimeField()
    
    def validate(self, data):
        """Validar que fecha_fin sea posterior a fecha_inicio"""
        if data['fecha_fin'] <= data['fecha_inicio']:
            raise serializers.ValidationError(
                "La fecha de fin debe ser posterior a la fecha de inicio"
            )
        return data


class EstadisticasEstudianteSerializer(serializers.Serializer):
    """Serializer para estadísticas individuales de estudiante"""
    estudiante_id = serializers.IntegerField()
    estudiante_nombre = serializers.CharField()
    estudiante_codigo = serializers.CharField()
    
    total_practicas = serializers.IntegerField()
    practicas_finalizadas = serializers.IntegerField()
    
    promedio_precision = serializers.FloatField()
    promedio_intentos = serializers.FloatField()
    promedio_tiempo_minutos = serializers.FloatField()
    promedio_calificacion = serializers.FloatField()
    
    mejor_practica = serializers.DictField()
    ultima_practica = serializers.DictField()


class MetricasTiempoRealSerializer(serializers.Serializer):
    """Serializer para métricas en tiempo real de una práctica activa"""
    practica_id = serializers.IntegerField()
    estudiante_nombre = serializers.CharField()
    estado = serializers.CharField()
    
    tiempo_transcurrido = serializers.IntegerField()
    numero_intentos = serializers.IntegerField()
    precision_actual = serializers.FloatField()
    
    ultimos_datos = serializers.ListField()
    angulo_actual = serializers.FloatField()
    fuerza_actual = serializers.FloatField()


class DashboardProfesorSerializer(serializers.Serializer):
    """Serializer para dashboard del profesor con todas las métricas"""
    # Estadísticas generales
    total_estudiantes_activos = serializers.IntegerField()
    total_practicas_hoy = serializers.IntegerField()
    practicas_en_curso = serializers.IntegerField()
    
    # Promedios del día
    promedio_precision_hoy = serializers.FloatField()
    promedio_calificacion_hoy = serializers.FloatField()
    
    # Listas
    practicas_activas = serializers.ListField()
    ultimas_practicas_finalizadas = serializers.ListField()
    estudiantes_mejor_desempeno = serializers.ListField()
    
    # Encuestas recientes
    promedio_satisfaccion_reciente = serializers.FloatField()
    total_encuestas_mes = serializers.IntegerField()