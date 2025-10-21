from rest_framework import serializers
from .models import Estudiante


class EstudianteSerializer(serializers.ModelSerializer):
    """Serializer para leer estudiantes"""
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
            'fecha_registro'
        ]
        read_only_fields = ['fecha_registro']


class EstudianteCreateSerializer(serializers.Serializer):
    """Serializer simplificado para crear estudiantes desde el frontend"""
    codigo_estudiante = serializers.CharField(max_length=20)
    nombre_completo = serializers.CharField(max_length=200)
    correo = serializers.EmailField()
    programa = serializers.CharField(max_length=100, default='Enfermería', required=False)
    semestre = serializers.IntegerField(default=1, required=False)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
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