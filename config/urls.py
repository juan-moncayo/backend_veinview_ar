from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Apps
    path('api/placa/', include('placa.urls')),
    path('api/estudiantes/', include('estudiantes.urls')),
    path('api/profesor/', include('profesor.urls')), 
    path('api/ra/', include('RA.urls')),  
]