from django.contrib import admin
from .models import Estudiante


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = [
        'codigo_estudiante',
        'nombre_completo',
        'get_profesor',
        'programa',
        'semestre',
        'activo',
        'get_total_practicas'
    ]
    list_filter = [
        'activo',
        'programa',
        'semestre',
        'profesor'
    ]
    search_fields = [
        'codigo_estudiante',
        'nombre_completo',
        'correo',
        'profesor__nombre_completo'
    ]
    readonly_fields = ['fecha_registro']
    
    fieldsets = (
        ('Información Personal', {
            'fields': (
                'user',
                'codigo_estudiante',
                'nombre_completo',
                'correo',
                'telefono'
            )
        }),
        ('Información Académica', {
            'fields': (
                'profesor',
                'programa',
                'semestre',
                'activo'
            )
        }),
        ('Fechas', {
            'fields': ('fecha_registro',),
            'classes': ('collapse',)
        }),
    )
    
    def get_profesor(self, obj):
        """Muestra el profesor asignado"""
        return obj.profesor.nombre_completo
    get_profesor.short_description = 'Profesor'
    
    def get_total_practicas(self, obj):
        """Muestra el total de prácticas del estudiante"""
        return obj.total_practicas()
    get_total_practicas.short_description = 'Total Prácticas'