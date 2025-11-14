from django.contrib import admin
from .models import ResumenPractica, EncuestaSistema, ReporteGeneral


@admin.register(ResumenPractica)
class ResumenPracticaAdmin(admin.ModelAdmin):
    list_display = [
        'practica', 
        'get_estudiante', 
        'calificacion', 
        'precision_porcentaje',
        'numero_intentos',
        'tecnica_correcta',
        'fecha_evaluacion'
    ]
    list_filter = [
        'tecnica_correcta', 
        'angulo_adecuado', 
        'presion_controlada',
        'fecha_evaluacion'
    ]
    search_fields = [
        'practica__estudiante__nombre_completo',
        'practica__estudiante__codigo_estudiante',
        'observaciones'
    ]
    readonly_fields = [
        'fecha_evaluacion',
        'total_datos_capturados',
        'inclinacion_promedio',
        'fuerza_promedio',
        'fuerza_maxima',
        'fuerza_minima',
        'numero_intentos',
        'intentos_exitosos',
        'precision_porcentaje',
        'tiempo_canalizacion'
    ]
    
    fieldsets = (
        ('Información de la Práctica', {
            'fields': ('practica', 'profesor', 'fecha_evaluacion')
        }),
        ('Estadísticas Calculadas', {
            'fields': (
                'total_datos_capturados',
                'tiempo_canalizacion',
                'numero_intentos',
                'intentos_exitosos',
                'precision_porcentaje'
            ),
            'classes': ('collapse',)
        }),
        ('Métricas de Sensores', {
            'fields': (
                'inclinacion_promedio',
                'fuerza_promedio',
                'fuerza_maxima',
                'fuerza_minima'
            ),
            'classes': ('collapse',)
        }),
        ('Evaluación', {
            'fields': (
                'calificacion',
                'observaciones',
                'tecnica_correcta',
                'angulo_adecuado',
                'presion_controlada'
            )
        }),
    )
    
    actions = ['recalcular_estadisticas', 'calcular_calificacion_automatica']
    
    def get_estudiante(self, obj):
        return obj.practica.estudiante.nombre_completo
    get_estudiante.short_description = 'Estudiante'
    
    def recalcular_estadisticas(self, request, queryset):
        """Acción para recalcular estadísticas de resúmenes seleccionados"""
        for resumen in queryset:
            resumen.calcular_estadisticas()
        self.message_user(request, f"{queryset.count()} resúmenes actualizados exitosamente")
    recalcular_estadisticas.short_description = "Recalcular estadísticas"
    
    def calcular_calificacion_automatica(self, request, queryset):
        """Acción para calcular calificación automática"""
        for resumen in queryset:
            resumen.calcular_calificacion_automatica()
        self.message_user(request, f"{queryset.count()} calificaciones calculadas exitosamente")
    calcular_calificacion_automatica.short_description = "Calcular calificación automática"


@admin.register(EncuestaSistema)
class EncuestaSistemaAdmin(admin.ModelAdmin):
    list_display = [
        'estudiante',
        'get_puntuacion_promedio',
        'recomendaria',
        'fecha_respuesta'
    ]
    list_filter = [
        'recomendaria',
        'facilidad_uso',
        'utilidad_sistema',
        'fecha_respuesta'
    ]
    search_fields = [
        'estudiante__nombre_completo',
        'estudiante__codigo_estudiante',
        'aspectos_positivos',
        'aspectos_negativos',
        'sugerencias'
    ]
    readonly_fields = ['fecha_respuesta', 'ip_address']
    
    fieldsets = (
        ('Información', {
            'fields': ('estudiante', 'practica', 'fecha_respuesta', 'ip_address')
        }),
        ('Evaluación Cuantitativa (1-5)', {
            'fields': (
                'facilidad_uso',
                'utilidad_sistema',
                'precision_sensores',
                'interfaz_clara',
                'mejora_aprendizaje'
            )
        }),
        ('Evaluación Cualitativa', {
            'fields': (
                'aspectos_positivos',
                'aspectos_negativos',
                'sugerencias'
            )
        }),
        ('Recomendación', {
            'fields': ('recomendaria',)
        }),
    )
    
    def get_puntuacion_promedio(self, obj):
        return f"{obj.puntuacion_promedio:.2f}"
    get_puntuacion_promedio.short_description = 'Puntuación Promedio'


@admin.register(ReporteGeneral)
class ReporteGeneralAdmin(admin.ModelAdmin):
    list_display = [
        'titulo',
        'get_periodo',
        'total_estudiantes',
        'total_practicas',
        'promedio_precision',
        'fecha_generacion'
    ]
    list_filter = ['fecha_generacion', 'generado_por']
    search_fields = ['titulo']
    readonly_fields = [
        'fecha_generacion',
        'total_estudiantes',
        'total_practicas',
        'total_datos_capturados',
        'promedio_precision',
        'promedio_intentos',
        'promedio_tiempo',
        'promedio_calificacion',
        'promedio_satisfaccion',
        'total_encuestas'
    ]
    
    fieldsets = (
        ('Información del Reporte', {
            'fields': (
                'titulo',
                'fecha_inicio',
                'fecha_fin',
                'generado_por',
                'fecha_generacion'
            )
        }),
        ('Estadísticas Generales', {
            'fields': (
                'total_estudiantes',
                'total_practicas',
                'total_datos_capturados'
            )
        }),
        ('Promedios de Desempeño', {
            'fields': (
                'promedio_precision',
                'promedio_intentos',
                'promedio_tiempo',
                'promedio_calificacion'
            )
        }),
        ('Satisfacción del Sistema', {
            'fields': (
                'promedio_satisfaccion',
                'total_encuestas'
            )
        }),
    )
    
    actions = ['regenerar_estadisticas']
    
    def get_periodo(self, obj):
        return f"{obj.fecha_inicio.strftime('%d/%m/%Y')} - {obj.fecha_fin.strftime('%d/%m/%Y')}"
    get_periodo.short_description = 'Período'
    
    def regenerar_estadisticas(self, request, queryset):
        """Acción para regenerar estadísticas de reportes seleccionados"""
        for reporte in queryset:
            reporte.generar_estadisticas()
        self.message_user(request, f"{queryset.count()} reportes regenerados exitosamente")
    regenerar_estadisticas.short_description = "Regenerar estadísticas"