from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'ra'

router = DefaultRouter()
router.register(r'sesiones', views.SesionRAViewSet, basename='sesiones')
router.register(r'configuraciones', views.ConfiguracionRAViewSet, basename='configuraciones')
router.register(r'eventos', views.EventoRAViewSet, basename='eventos')

urlpatterns = [
    # ========================================
    # 🆕 NUEVOS ENDPOINTS DE CONEXIÓN AUTOMÁTICA
    # ========================================
    path('conectar-automatico/', views.conectar_automatico, name='conectar_automatico'),
    path('practica-actual/', views.practica_actual, name='practica_actual'),
    path('alertas/', views.alertas_ra, name='alertas'),
    
    # ========================================
    # ENDPOINTS EXISTENTES (MANTENIDOS)
    # ========================================
    path('conectar/', views.conectar_ra, name='conectar'),
    path('desconectar/', views.desconectar_ra, name='desconectar'),
    path('stream/', views.stream_datos_ra, name='stream'),
    path('estado-practica/', views.estado_practica_ra, name='estado_practica'),
    path('heartbeat/', views.heartbeat_ra, name='heartbeat'),
    path('eventos/registrar/', views.registrar_evento_ra, name='registrar_evento'),
    
    # ViewSets (administración web)
    path('', include(router.urls)),
]