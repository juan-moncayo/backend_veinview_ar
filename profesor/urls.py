from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'profesor'

# Router para ViewSets
router = DefaultRouter()
router.register(r'resumenes', views.ResumenPracticaViewSet, basename='resumenes')
router.register(r'encuestas', views.EncuestaSistemaViewSet, basename='encuestas')
router.register(r'reportes', views.ReporteGeneralViewSet, basename='reportes')

urlpatterns = [
    # ✅ NUEVOS: Endpoints de autenticación
    path('login/', views.login_profesor, name='login'),
    path('registro/', views.registro_profesor, name='registro'),
    path('perfil/', views.perfil_profesor, name='perfil'),
    path('perfil/actualizar/', views.actualizar_perfil_profesor, name='actualizar_perfil'),
    path('mis-estudiantes/', views.mis_estudiantes, name='mis_estudiantes'),
    
    # Endpoints de estadísticas y dashboard
    path('dashboard/', views.dashboard_profesor, name='dashboard_profesor'),
    path('estadisticas-estudiante/', views.estadisticas_estudiante, name='estadisticas_estudiante'),
    path('metricas-tiempo-real/', views.metricas_tiempo_real, name='metricas_tiempo_real'),
    
    # Incluir rutas del router
    path('', include(router.urls)),
]