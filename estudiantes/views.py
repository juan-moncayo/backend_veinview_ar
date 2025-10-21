from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Estudiante
from .serializers import EstudianteSerializer, EstudianteCreateSerializer


class EstudianteViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar estudiantes
    GET /api/estudiantes/ - Listar estudiantes
    POST /api/estudiantes/ - Crear estudiante
    GET /api/estudiantes/{id}/ - Ver detalle
    """
    queryset = Estudiante.objects.all()
    serializer_class = EstudianteSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EstudianteCreateSerializer
        return EstudianteSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear estudiante con usuario automático"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Crear usuario automáticamente
        username = serializer.validated_data['codigo_estudiante']
        email = serializer.validated_data['correo']
        nombre = serializer.validated_data['nombre_completo']
        
        # Verificar si el usuario ya existe
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=nombre.split()[0] if nombre else '',
                last_name=' '.join(nombre.split()[1:]) if len(nombre.split()) > 1 else ''
            )
        except Exception as e:
            # Si el usuario ya existe, buscar un estudiante existente
            try:
                estudiante_existente = Estudiante.objects.get(
                    codigo_estudiante=username
                )
                return Response(
                    EstudianteSerializer(estudiante_existente).data,
                    status=status.HTTP_200_OK
                )
            except Estudiante.DoesNotExist:
                return Response(
                    {'error': f'Error creando usuario: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Crear estudiante
        estudiante = Estudiante.objects.create(
            user=user,
            codigo_estudiante=serializer.validated_data['codigo_estudiante'],
            nombre_completo=serializer.validated_data['nombre_completo'],
            correo=serializer.validated_data['correo'],
            programa=serializer.validated_data.get('programa', 'Enfermería'),
            semestre=serializer.validated_data.get('semestre', 1),
            telefono=serializer.validated_data.get('telefono', ''),
            activo=True
        )
        
        return Response(
            EstudianteSerializer(estudiante).data,
            status=status.HTTP_201_CREATED
        )