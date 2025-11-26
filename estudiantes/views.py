from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Estudiante
from .serializers import (
    EstudianteSerializer,
    EstudianteCreateSerializer,
    EstudianteUpdateSerializer
)
from profesor.models import Profesor


class EstudianteViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar estudiantes
    GET /api/estudiantes/ - Listar estudiantes
    POST /api/estudiantes/ - Crear estudiante
    GET /api/estudiantes/{id}/ - Ver detalle
    PATCH /api/estudiantes/{id}/ - Actualizar estudiante
    DELETE /api/estudiantes/{id}/ - Eliminar estudiante
    """
    queryset = Estudiante.objects.select_related('profesor', 'user').all()
    serializer_class = EstudianteSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EstudianteCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EstudianteUpdateSerializer
        return EstudianteSerializer
    
    def get_queryset(self):
        """Filtrar estudiantes por profesor si se proporciona el parámetro"""
        queryset = super().get_queryset()
        profesor_id = self.request.query_params.get('profesor_id')
        
        if profesor_id:
            queryset = queryset.filter(profesor_id=profesor_id)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Crear estudiante con usuario automático y asignarlo a un profesor"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Obtener profesor
        profesor_id = serializer.validated_data['profesor_id']
        try:
            profesor = Profesor.objects.get(id=profesor_id)
        except Profesor.DoesNotExist:
            return Response(
                {'error': 'Profesor no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
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
            profesor=profesor,
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
    
    def partial_update(self, request, *args, **kwargs):
        """Actualizar estudiante (PATCH)"""
        estudiante = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={'estudiante': estudiante}
        )
        serializer.is_valid(raise_exception=True)
        
        # Actualizar campos
        for field, value in serializer.validated_data.items():
            setattr(estudiante, field, value)
        
        estudiante.save()
        
        return Response(
            EstudianteSerializer(estudiante).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def por_profesor(self, request):
        """
        Obtener estudiantes de un profesor específico
        GET /api/estudiantes/por_profesor/?profesor_id=1
        """
        profesor_id = request.query_params.get('profesor_id')
        
        if not profesor_id:
            return Response(
                {'error': 'profesor_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profesor = Profesor.objects.get(id=profesor_id)
        except Profesor.DoesNotExist:
            return Response(
                {'error': 'Profesor no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        estudiantes = self.queryset.filter(profesor=profesor, activo=True)
        serializer = self.get_serializer(estudiantes, many=True)
        
        return Response({
            'profesor': {
                'id': profesor.id,
                'nombre': profesor.nombre_completo
            },
            'total_estudiantes': estudiantes.count(),
            'estudiantes': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """
        Obtener estadísticas de un estudiante
        GET /api/estudiantes/{id}/estadisticas/
        """
        estudiante = self.get_object()
        from placa.models import PracticaActiva
        
        practicas = PracticaActiva.objects.filter(estudiante=estudiante)
        practicas_finalizadas = practicas.filter(estado='finalizada')
        
        if not practicas_finalizadas.exists():
            return Response({
                'estudiante': EstudianteSerializer(estudiante).data,
                'total_practicas': 0,
                'practicas_finalizadas': 0,
                'mensaje': 'Este estudiante no tiene prácticas finalizadas'
            })
        
        from django.db.models import Avg
        stats = practicas_finalizadas.aggregate(
            avg_precision=Avg('precision_promedio'),
            avg_intentos=Avg('numero_intentos'),
            avg_tiempo=Avg('duracion_total_segundos')
        )
        
        return Response({
            'estudiante': EstudianteSerializer(estudiante).data,
            'total_practicas': practicas.count(),
            'practicas_finalizadas': practicas_finalizadas.count(),
            'promedio_precision': round(stats['avg_precision'] or 0, 2),
            'promedio_intentos': round(stats['avg_intentos'] or 0, 2),
            'promedio_tiempo_minutos': round((stats['avg_tiempo'] or 0) / 60, 2)
        })