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
    # Incluir rutas del router
    path('', include(router.urls)),
    
    # Endpoints adicionales (function-based views)
    path('estadisticas-estudiante/', views.estadisticas_estudiante, name='estadisticas_estudiante'),
    path('metricas-tiempo-real/', views.metricas_tiempo_real, name='metricas_tiempo_real'),
    path('dashboard/', views.dashboard_profesor, name='dashboard_profesor'),
]