from django.db import models
from django.contrib.auth.models import User


class Estudiante(models.Model):
    """Modelo para estudiantes que realizan prácticas de canalización"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='estudiante')
    
    # ✅ TEMPORAL: Hacer el campo nullable y con blank=True
    profesor = models.ForeignKey(
        'profesor.Profesor',
        on_delete=models.CASCADE,
        related_name='estudiantes',
        help_text="Profesor asignado a este estudiante",
        null=True,  # ✅ Temporal
        blank=True  # ✅ Temporal
    )
    
    codigo_estudiante = models.CharField(max_length=20, unique=True)
    nombre_completo = models.CharField(max_length=200)
    correo = models.EmailField(unique=True)
    programa = models.CharField(max_length=100, default="Enfermería")
    semestre = models.IntegerField()
    telefono = models.CharField(max_length=20, blank=True)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"
        ordering = ['nombre_completo']
    
    def __str__(self):
        return f"{self.codigo_estudiante} - {self.nombre_completo}"
    
    def total_practicas(self):
        """Retorna el número total de prácticas del estudiante"""
        return self.practicas.count()
    
    def practicas_finalizadas(self):
        """Retorna el número de prácticas finalizadas"""
        return self.practicas.filter(estado='finalizada').count()