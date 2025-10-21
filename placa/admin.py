from django.contrib import admin
from .models import DispositivoESP32, PracticaActiva, DatosSensor

@admin.register(DispositivoESP32)
class DispositivoESP32Admin(admin.ModelAdmin):
    list_display = ['nombre', 'mac_address', 'activo', 'ultima_conexion', 'ip_address']
    list_filter = ['activo', 'fecha_registro']
    search_fields = ['nombre', 'mac_address', 'api_key']
    readonly_fields = ['api_key', 'fecha_registro', 'ultima_conexion']
    
    fieldsets = (
        ('Información del Dispositivo', {
            'fields': ('nombre', 'mac_address', 'activo')
        }),
        ('Seguridad', {
            'fields': ('api_key',),
            'classes': ('collapse',)
        }),
        ('Conexión', {
            'fields': ('ip_address', 'ultima_conexion', 'fecha_registro')
        }),
    )


@admin.register(PracticaActiva)
class PracticaActivaAdmin(admin.ModelAdmin):
    list_display = ['estudiante', 'dispositivo', 'estado', 'fecha_inicio', 'duracion_total_segundos']
    list_filter = ['estado', 'fecha_inicio']
    search_fields = ['estudiante__nombre_completo', 'estudiante__codigo_estudiante']
    readonly_fields = ['fecha_inicio', 'fecha_pausa', 'fecha_reanudacion', 'fecha_fin']
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.estado == 'finalizada':
            return [f.name for f in obj._meta.fields]
        return self.readonly_fields


@admin.register(DatosSensor)
class DatosSensorAdmin(admin.ModelAdmin):
    list_display = ['practica', 'timestamp', 'angulo_pitch', 'angulo_roll', 'fuerza']
    list_filter = ['timestamp', 'practica__estudiante']
    search_fields = ['practica__estudiante__nombre_completo']
    readonly_fields = ['timestamp', 'ip_origen']
    
    fieldsets = (
        ('Práctica', {
            'fields': ('practica', 'dispositivo')
        }),
        ('MPU6050 - Aceleración', {
            'fields': ('aceleracion_x', 'aceleracion_y', 'aceleracion_z')
        }),
        ('MPU6050 - Giroscopio', {
            'fields': ('giroscopio_x', 'giroscopio_y', 'giroscopio_z')
        }),
        ('MPU6050 - Ángulos', {
            'fields': ('angulo_pitch', 'angulo_roll', 'angulo_yaw')
        }),
        ('Celda de Carga', {
            'fields': ('fuerza', 'presion')
        }),
        ('Metadata', {
            'fields': ('timestamp', 'ip_origen')
        }),
    )