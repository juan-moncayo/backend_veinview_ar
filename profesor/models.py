from django.db import models
from django.contrib.auth.models import User
from estudiantes.models import Estudiante
from placa.models import PracticaActiva

class ResumenPractica(models.Model):
    """Resumen y calificación de prácticas finalizadas"""
    practica = models.OneToOneField(PracticaActiva, on_delete=models.CASCADE, related_name='resumen')
    profesor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='practicas_evaluadas')
    
    # Estadísticas calculadas
    total_datos_capturados = models.IntegerField(default=0)
    inclinacion_promedio = models.FloatField(null=True, blank=True, help_text="Ángulo promedio (°)")
    fuerza_promedio = models.FloatField(null=True, blank=True, help_text="Fuerza promedio (g)")
    fuerza_maxima = models.FloatField(null=True, blank=True, help_text="Fuerza máxima (g)")
    
    # Evaluación
    calificacion = models.FloatField(null=True, blank=True, help_text="Calificación de 0.0 a 5.0")
    observaciones = models.TextField(blank=True)
    
    # Criterios de evaluación (personalizable)
    tecnica_correcta = models.BooleanField(default=False)
    angulo_adecuado = models.BooleanField(default=False)
    presion_controlada = models.BooleanField(default=False)
    
    fecha_evaluacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Resumen de Práctica"
        verbose_name_plural = "Resúmenes de Prácticas"
        ordering = ['-fecha_evaluacion']
    
    def __str__(self):
        return f"Evaluación - {self.practica.estudiante.nombre_completo}"