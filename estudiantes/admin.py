from django.contrib import admin
from .models import Estudiante

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ['codigo_estudiante', 'nombre_completo', 'programa', 'semestre', 'activo']
    list_filter = ['activo', 'programa', 'semestre']
    search_fields = ['codigo_estudiante', 'nombre_completo', 'correo']
    readonly_fields = ['fecha_registro']