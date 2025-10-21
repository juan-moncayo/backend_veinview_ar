from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'placa'

# Router para ViewSets (endpoints REST)
router = DefaultRouter()
router.register(r'dispositivos', views.DispositivoESP32ViewSet, basename='dispositivos')
router.register(r'practicas', views.PracticaActivaViewSet, basename='practicas')
router.register(r'datos-sensores', views.DatosSensorViewSet, basename='datos-sensores')

urlpatterns = [
    # Incluir rutas del router (para el frontend web)
    path('', include(router.urls)),
    
    # Endpoints específicos del ESP32 (NO TOCAR - funcionan bien)
    path('registrar/', views.registrar_dispositivo, name='registrar_dispositivo'),
    path('ping/', views.verificar_conexion, name='verificar_conexion'),
    path('practica-activa/', views.obtener_practica_activa, name='practica_activa'),
    path('datos/', views.enviar_datos_sensores, name='enviar_datos'),
    path('estado/', views.estado_sistema, name='estado_sistema'),
]