from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'estudiantes'

router = DefaultRouter()
router.register(r'', views.EstudianteViewSet, basename='estudiante')

urlpatterns = [
    path('', include(router.urls)),
]