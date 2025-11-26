from rest_framework import serializers
from .models import Estudiante
from django.contrib.auth.models import User


class EstudianteSerializer(serializers.ModelSerializer):
    """Serializer para leer estudiantes"""
    profesor_nombre = serializers.CharField(source='profesor.nombre_completo', read_only=True)
    profesor_id = serializers.IntegerField(source='profesor.id', read_only=True)
    total_practicas = serializers.SerializerMethodField()
    practicas_finalizadas = serializers.SerializerMethodField()
    
    class Meta:
        model = Estudiante
        fields = [
            'id',
            'codigo_estudiante',
            'nombre_completo',
            'correo',
            'programa',
            'semestre',
            'telefono',
            'activo',
            'fecha_registro',
            'profesor',
            'profesor_id',
            'profesor_nombre',
            'total_practicas',
            'practicas_finalizadas'
        ]
        read_only_fields = ['fecha_registro']
    
    def get_total_practicas(self, obj):
        """Total de prácticas del estudiante"""
        return obj.total_practicas()
    
    def get_practicas_finalizadas(self, obj):
        """Total de prácticas finalizadas"""
        return obj.practicas_finalizadas()


class EstudianteCreateSerializer(serializers.Serializer):
    """Serializer simplificado para crear estudiantes desde el frontend"""
    profesor_id = serializers.IntegerField()
    codigo_estudiante = serializers.CharField(max_length=20)
    nombre_completo = serializers.CharField(max_length=200)
    correo = serializers.EmailField()
    programa = serializers.CharField(max_length=100, default='Enfermería', required=False)
    semestre = serializers.IntegerField(default=1, required=False)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    def validate_profesor_id(self, value):
        """Validar que el profesor existe"""
        from profesor.models import Profesor
        try:
            Profesor.objects.get(id=value)
        except Profesor.DoesNotExist:
            raise serializers.ValidationError("Profesor no encontrado")
        return value
    
    def validate_codigo_estudiante(self, value):
        """Validar que el código no exista"""
        if Estudiante.objects.filter(codigo_estudiante=value).exists():
            raise serializers.ValidationError(
                "Ya existe un estudiante con este código"
            )
        return value
    
    def validate_correo(self, value):
        """Validar que el correo no exista"""
        if Estudiante.objects.filter(correo=value).exists():
            raise serializers.ValidationError(
                "Ya existe un estudiante con este correo"
            )
        return value


class EstudianteUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar estudiantes"""
    nombre_completo = serializers.CharField(max_length=200, required=False)
    correo = serializers.EmailField(required=False)
    programa = serializers.CharField(max_length=100, required=False)
    semestre = serializers.IntegerField(required=False)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    activo = serializers.BooleanField(required=False)
    
    def validate_correo(self, value):
        """Validar que el correo no exista (excepto el del estudiante actual)"""
        estudiante = self.context.get('estudiante')
        if Estudiante.objects.filter(correo=value).exclude(id=estudiante.id).exists():
            raise serializers.ValidationError(
                "Ya existe un estudiante con este correo"
            )
        return value