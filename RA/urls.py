from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'ra'

# Router para ViewSets (administración web)
router = DefaultRouter()
router.register(r'sesiones', views.SesionRAViewSet, basename='sesiones')
router.register(r'configuraciones', views.ConfiguracionRAViewSet, basename='configuraciones')
router.register(r'eventos', views.EventoRAViewSet, basename='eventos')

urlpatterns = [
    # ========================================
    # ENDPOINTS PRINCIPALES PARA UNREAL ENGINE
    # ========================================
    
    # Conexión y desconexión
    path('conectar/', views.conectar_ra, name='conectar'),
    path('desconectar/', views.desconectar_ra, name='desconectar'),
    
    # Stream de datos en tiempo real
    path('stream/', views.stream_datos_ra, name='stream'),
    
    # Estado de la práctica
    path('estado-practica/', views.estado_practica_ra, name='estado_practica'),
    
    # Heartbeat (mantener sesión activa)
    path('heartbeat/', views.heartbeat_ra, name='heartbeat'),
    
    # Registro de eventos
    path('eventos/registrar/', views.registrar_evento_ra, name='registrar_evento'),
    
    # ========================================
    # ENDPOINTS DE ADMINISTRACIÓN WEB
    # ========================================
    
    # Incluir rutas del router (ViewSets)
    path('', include(router.urls)),
]