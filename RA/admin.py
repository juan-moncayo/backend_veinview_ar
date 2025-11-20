from django.contrib import admin
from .models import SesionRA, DatosVisualizacionRA, ConfiguracionRA, EventoRA


@admin.register(SesionRA)
class SesionRAAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'estudiante',
        'get_practica_info',
        'dispositivo_ra',
        'estado',
        'fecha_inicio',
        'tiempo_activo',
        'total_datos_recibidos',
        'latencia_promedio'
    ]
    list_filter = [
        'estado',
        'dispositivo_ra',
        'fecha_inicio',
        'modo_visualizacion'
    ]
    search_fields = [
        'estudiante__nombre_completo',
        'estudiante__codigo_estudiante',
        'session_token',
        'ip_address'
    ]
    readonly_fields = [
        'session_token',
        'fecha_inicio',
        'fecha_ultima_actividad',
        'fecha_fin',
        'ip_address',
        'total_datos_recibidos',
        'latencia_promedio'
    ]
    
    fieldsets = (
        ('Información de la Sesión', {
            'fields': (
                'estudiante',
                'practica',
                'session_token',
                'estado'
            )
        }),
        ('Dispositivo y Conexión', {
            'fields': (
                'dispositivo_ra',
                'ip_address',
                'fecha_inicio',
                'fecha_ultima_actividad',
                'fecha_fin'
            )
        }),
        ('Configuración de Visualización', {
            'fields': (
                'modo_visualizacion',
                'escala_modelo',
                'opacidad'
            )
        }),
        ('Estadísticas', {
            'fields': (
                'total_datos_recibidos',
                'latencia_promedio'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['finalizar_sesiones', 'limpiar_sesiones_inactivas']
    
    def get_practica_info(self, obj):
        """Muestra información de la práctica asociada"""
        if obj.practica:
            return f"Práctica #{obj.practica.id} - {obj.practica.estado}"
        return "Sin práctica"
    get_practica_info.short_description = 'Práctica'
    
    def tiempo_activo(self, obj):
        """Calcula el tiempo activo en formato legible"""
        from django.utils import timezone
        if obj.fecha_fin:
            segundos = int((obj.fecha_fin - obj.fecha_inicio).total_seconds())
        else:
            segundos = int((timezone.now() - obj.fecha_inicio).total_seconds())
        
        minutos = segundos // 60
        segundos_restantes = segundos % 60
        
        if minutos > 60:
            horas = minutos // 60
            minutos_restantes = minutos % 60
            return f"{horas}h {minutos_restantes}m {segundos_restantes}s"
        return f"{minutos}m {segundos_restantes}s"
    tiempo_activo.short_description = 'Tiempo Activo'
    
    def finalizar_sesiones(self, request, queryset):
        """Acción para finalizar sesiones seleccionadas"""
        count = 0
        for sesion in queryset:
            if sesion.estado in ['activa', 'pausada', 'conectando']:
                sesion.finalizar()
                count += 1
        
        self.message_user(
            request,
            f"{count} sesión(es) finalizada(s) exitosamente"
        )
    finalizar_sesiones.short_description = "Finalizar sesiones seleccionadas"
    
    def limpiar_sesiones_inactivas(self, request, queryset):
        """Acción para limpiar sesiones inactivas (más de 1 hora)"""
        from django.utils import timezone
        from datetime import timedelta
        
        limite = timezone.now() - timedelta(hours=1)
        count = 0
        
        for sesion in queryset:
            if sesion.fecha_ultima_actividad < limite and sesion.estado in ['activa', 'pausada']:
                sesion.estado = 'desconectada'
                sesion.fecha_fin = timezone.now()
                sesion.save()
                count += 1
        
        self.message_user(
            request,
            f"{count} sesión(es) inactiva(s) limpiada(s)"
        )
    limpiar_sesiones_inactivas.short_description = "Limpiar sesiones inactivas"


@admin.register(DatosVisualizacionRA)
class DatosVisualizacionRAAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'get_sesion_info',
        'get_dato_info',
        'timestamp_envio',
        'latencia_ms',
        'entregado'
    ]
    list_filter = [
        'entregado',
        'timestamp_envio',
        'sesion__estudiante'
    ]
    search_fields = [
        'sesion__estudiante__nombre_completo',
        'sesion__session_token'
    ]
    readonly_fields = [
        'timestamp_envio',
        'timestamp_recepcion',
        'latencia_ms'
    ]
    
    fieldsets = (
        ('Información', {
            'fields': (
                'sesion',
                'dato_sensor'
            )
        }),
        ('Metadata de Envío', {
            'fields': (
                'timestamp_envio',
                'timestamp_recepcion',
                'latencia_ms',
                'entregado',
                'error_entrega'
            )
        }),
    )
    
    def get_sesion_info(self, obj):
        """Muestra información de la sesión"""
        return f"Sesión #{obj.sesion.id} - {obj.sesion.estudiante.nombre_completo}"
    get_sesion_info.short_description = 'Sesión'
    
    def get_dato_info(self, obj):
        """Muestra información del dato"""
        dato = obj.dato_sensor
        return f"Pitch: {dato.angulo_pitch:.1f}° | Fuerza: {dato.fuerza:.1f}g"
    get_dato_info.short_description = 'Dato'


@admin.register(ConfiguracionRA)
class ConfiguracionRAAdmin(admin.ModelAdmin):
    list_display = [
        'estudiante',
        'mostrar_grid',
        'mostrar_angulos',
        'mostrar_fuerza',
        'audio_feedback',
        'fps_objetivo',
        'fecha_modificacion'
    ]
    list_filter = [
        'mostrar_grid',
        'mostrar_angulos',
        'mostrar_fuerza',
        'audio_feedback',
        'fecha_modificacion'
    ]
    search_fields = [
        'estudiante__nombre_completo',
        'estudiante__codigo_estudiante'
    ]
    readonly_fields = [
        'fecha_creacion',
        'fecha_modificacion'
    ]
    
    fieldsets = (
        ('Estudiante', {
            'fields': ('estudiante',)
        }),
        ('Colores de Visualización', {
            'fields': (
                'color_angulo_correcto',
                'color_angulo_incorrecto',
                'color_fuerza_correcta'
            )
        }),
        ('Opciones de Interfaz', {
            'fields': (
                'mostrar_grid',
                'mostrar_angulos',
                'mostrar_fuerza',
                'mostrar_historial'
            )
        }),
        ('Audio', {
            'fields': (
                'audio_feedback',
                'volumen'
            )
        }),
        ('Rendimiento', {
            'fields': ('fps_objetivo',)
        }),
        ('Fechas', {
            'fields': (
                'fecha_creacion',
                'fecha_modificacion'
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(EventoRA)
class EventoRAAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'get_sesion_info',
        'tipo',
        'descripcion_corta',
        'timestamp'
    ]
    list_filter = [
        'tipo',
        'timestamp',
        'sesion__estudiante'
    ]
    search_fields = [
        'sesion__estudiante__nombre_completo',
        'descripcion'
    ]
    readonly_fields = [
        'timestamp',
        'datos_adicionales'
    ]
    
    fieldsets = (
        ('Información del Evento', {
            'fields': (
                'sesion',
                'tipo',
                'descripcion',
                'timestamp'
            )
        }),
        ('Datos Adicionales', {
            'fields': ('datos_adicionales',),
            'classes': ('collapse',)
        }),
    )
    
    def get_sesion_info(self, obj):
        """Muestra información de la sesión"""
        return f"Sesión #{obj.sesion.id} - {obj.sesion.estudiante.nombre_completo}"
    get_sesion_info.short_description = 'Sesión'
    
    def descripcion_corta(self, obj):
        """Muestra una descripción corta"""
        if len(obj.descripcion) > 50:
            return f"{obj.descripcion[:50]}..."
        return obj.descripcion
    descripcion_corta.short_description = 'Descripción'