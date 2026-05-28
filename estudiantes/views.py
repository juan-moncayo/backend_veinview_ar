from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Estudiante
from .serializers import (
    EstudianteSerializer,
    EstudianteCreateSerializer,
    EstudianteUpdateSerializer,
)
from profesor.models import Profesor


class EstudianteViewSet(viewsets.ModelViewSet):
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
        queryset = super().get_queryset()
        profesor_id = self.request.query_params.get('profesor_id')
        if profesor_id:
            queryset = queryset.filter(profesor_id=profesor_id)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                nombre_completo__icontains=search
            ) | queryset.filter(
                codigo_estudiante__icontains=search
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Determinar profesor
        profesor = None

        if request.user.is_authenticated:
            try:
                profesor = Profesor.objects.get(user=request.user)
            except Profesor.DoesNotExist:
                pass

        if profesor is None:
            profesor_id = serializer.validated_data.get('profesor_id')
            if profesor_id:
                try:
                    profesor = Profesor.objects.get(id=profesor_id)
                except Profesor.DoesNotExist:
                    return Response(
                        {'error': f'Profesor con ID {profesor_id} no encontrado'},
                        status=status.HTTP_404_NOT_FOUND
                    )

        if profesor is None:
            return Response(
                {
                    'error': (
                        'No se pudo determinar el profesor. '
                        'Asegúrate de estar autenticado como profesor o envía profesor_id.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        codigo = serializer.validated_data['codigo_estudiante']
        correo = serializer.validated_data['correo']
        nombre = serializer.validated_data['nombre_completo']

        # Crear o recuperar usuario — siempre sincronizar contraseña
        try:
            user, created = User.objects.get_or_create(
                username=correo,
                defaults={
                    'email': correo,
                    'first_name': nombre.split()[0] if nombre else '',
                    'last_name': ' '.join(nombre.split()[1:]) if len(nombre.split()) > 1 else '',
                }
            )
            # Siempre actualizar la contraseña para que coincida con el código actual
            user.set_password(codigo)
            user.save()
        except Exception as e:
            return Response(
                {'error': f'Error creando usuario: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Si el estudiante ya existe para ese usuario, devolverlo
        try:
            estudiante_existente = Estudiante.objects.get(user=user)
            return Response(
                EstudianteSerializer(estudiante_existente).data,
                status=status.HTTP_200_OK
            )
        except Estudiante.DoesNotExist:
            pass

        # Crear estudiante
        estudiante = Estudiante.objects.create(
            user=user,
            profesor=profesor,
            codigo_estudiante=codigo,
            nombre_completo=nombre,
            correo=correo,
            programa=serializer.validated_data.get('programa', 'Enfermería'),
            semestre=serializer.validated_data.get('semestre', 1),
            telefono=serializer.validated_data.get('telefono', ''),
            activo=True,
        )

        return Response(
            EstudianteSerializer(estudiante).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        estudiante = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={'estudiante': estudiante}
        )
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(estudiante, field, value)
        estudiante.save()

        return Response(
            EstudianteSerializer(estudiante).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_perfil(self, request):
        try:
            estudiante = Estudiante.objects.select_related('profesor', 'user').get(
                user=request.user
            )
        except Estudiante.DoesNotExist:
            return Response(
                {'error': 'El usuario autenticado no tiene perfil de estudiante'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(EstudianteSerializer(estudiante).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mis_practicas(self, request):
        try:
            estudiante = Estudiante.objects.get(user=request.user)
        except Estudiante.DoesNotExist:
            return Response(
                {'error': 'El usuario autenticado no tiene perfil de estudiante'},
                status=status.HTTP_404_NOT_FOUND
            )

        from placa.models import PracticaActiva
        from placa.serializers import PracticaActivaSerializer

        # Devolver TODAS las prácticas, no solo las finalizadas
        practicas = PracticaActiva.objects.filter(
            estudiante=estudiante
        ).order_by('fecha_inicio')

        serializer = PracticaActivaSerializer(practicas, many=True)

        return Response({
            'estudiante_id': estudiante.id,
            'total_practicas': practicas.count(),
            'practicas': serializer.data,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def cambiar_password(self, request):
        try:
            estudiante = Estudiante.objects.get(user=request.user)
        except Estudiante.DoesNotExist:
            return Response(
                {'error': 'El usuario autenticado no tiene perfil de estudiante'},
                status=status.HTTP_404_NOT_FOUND
            )

        password_actual = request.data.get('password_actual')
        password_nueva = request.data.get('password_nueva')

        if not password_actual or not password_nueva:
            return Response(
                {'error': 'Se requieren password_actual y password_nueva'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not request.user.check_password(password_actual):
            return Response(
                {'error': 'La contraseña actual es incorrecta'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(password_nueva) < 6:
            return Response(
                {'error': 'La nueva contraseña debe tener al menos 6 caracteres'},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.set_password(password_nueva)
        request.user.save()

        return Response(
            {'mensaje': 'Contraseña actualizada correctamente'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def por_profesor(self, request):
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
        serializer = EstudianteSerializer(estudiantes, many=True)

        return Response({
            'profesor': {
                'id': profesor.id,
                'nombre': profesor.nombre_completo,
            },
            'total_estudiantes': estudiantes.count(),
            'estudiantes': serializer.data,
        })

    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        estudiante = self.get_object()
        from placa.models import PracticaActiva

        practicas = PracticaActiva.objects.filter(estudiante=estudiante)
        practicas_finalizadas = practicas.filter(estado='finalizada')

        if not practicas_finalizadas.exists():
            return Response({
                'estudiante': EstudianteSerializer(estudiante).data,
                'total_practicas': 0,
                'practicas_finalizadas': 0,
                'mensaje': 'Este estudiante no tiene prácticas finalizadas',
            })

        from django.db.models import Avg
        stats = practicas_finalizadas.aggregate(
            avg_precision=Avg('precision_promedio'),
            avg_intentos=Avg('numero_intentos'),
            avg_tiempo=Avg('duracion_total_segundos'),
        )

        return Response({
            'estudiante': EstudianteSerializer(estudiante).data,
            'total_practicas': practicas.count(),
            'practicas_finalizadas': practicas_finalizadas.count(),
            'promedio_precision': round(stats['avg_precision'] or 0, 2),
            'promedio_intentos': round(stats['avg_intentos'] or 0, 2),
            'promedio_tiempo_minutos': round((stats['avg_tiempo'] or 0) / 60, 2),
        })