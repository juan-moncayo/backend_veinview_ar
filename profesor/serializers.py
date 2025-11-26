from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profesor, ResumenPractica, EncuestaSistema, ReporteGeneral
from placa.models import PracticaActiva, DatosSensor
from estudiantes.models import Estudiante


# ✅ NUEVO: Serializer para Profesor
class ProfesorSerializer(serializers.ModelSerializer):
    """Serializer para información del profesor"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    total_estudiantes = serializers.SerializerMethodField()
    practicas_hoy = serializers.SerializerMethodField()
    
    class Meta:
        model = Profesor
        fields = [
            'id',
            'username',
            'email',
            'nombre_completo',
            'cedula',
            'correo',
            'telefono',
            'especialidad',
            'activo',
            'fecha_registro',
            'total_estudiantes',
            'practicas_hoy'
        ]
        read_only_fields = ['fecha_registro']
    
    def get_total_estudiantes(self, obj):
        return obj.total_estudiantes()
    
    def get_practicas_hoy(self, obj):
        return obj.practicas_hoy()


# ✅ NUEVO: Serializer para Login de Profesor
class ProfesorLoginSerializer(serializers.Serializer):
    """Serializer para login de profesor"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


# ✅ NUEVO: Serializer para Registro de Profesor
class ProfesorRegistroSerializer(serializers.Serializer):
    """Serializer para registrar nuevo profesor"""
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField()
    nombre_completo = serializers.CharField(max_length=200)
    cedula = serializers.CharField(max_length=20)
    correo = serializers.EmailField()
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    especialidad = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    def validate_username(self, value):
        """Validar que el username no exista"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este nombre de usuario ya existe")
        return value
    
    def validate_cedula(self, value):
        """Validar que la cédula no exista"""
        if Profesor.objects.filter(cedula=value).exists():
            raise serializers.ValidationError("Ya existe un profesor con esta cédula")
        return value
    
    def validate_correo(self, value):
        """Validar que el correo no exista"""
        if Profesor.objects.filter(correo=value).exists():
            raise serializers.ValidationError("Ya existe un profesor con este correo")
        return value


class ResumenPracticaSerializer(serializers.ModelSerializer):
    """Serializer para resúmenes de prácticas"""
    estudiante_nombre = serializers.CharField(source='practica.estudiante.nombre_completo', read_only=True)
    estudiante_codigo = serializers.CharField(source='practica.estudiante.codigo_estudiante', read_only=True)
    profesor_nombre = serializers.CharField(source='profesor.nombre_completo', read_only=True)
    fecha_practica = serializers.DateTimeField(source='practica.fecha_inicio', read_only=True)
    duracion_minutos = serializers.SerializerMethodField()
    
    class Meta:
        model = ResumenPractica
        fields = [
            'id', 'practica', 'profesor', 'profesor_nombre',
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
    profesor_nombre = serializers.CharField(source='estudiante.profesor.nombre_completo', read_only=True)
    puntuacion_promedio = serializers.ReadOnlyField()
    
    class Meta:
        model = EncuestaSistema
        fields = [
            'id', 'estudiante', 'estudiante_nombre', 'profesor_nombre', 'practica',
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
    profesor_nombre = serializers.CharField(source='profesor.nombre_completo', read_only=True)
    periodo = serializers.SerializerMethodField()
    
    class Meta:
        model = ReporteGeneral
        fields = [
            'id', 'titulo', 'profesor', 'profesor_nombre',
            'fecha_inicio', 'fecha_fin', 'periodo',
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
    # Información del profesor
    profesor = ProfesorSerializer()
    
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