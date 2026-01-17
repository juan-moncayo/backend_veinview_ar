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
        """
        Crear estudiante y asignar automáticamente al profesor autenticado
        """
        print("=" * 80)
        print("🔵 INICIO - Crear Estudiante")
        print("=" * 80)
        
        # 🔍 DEBUG: Información del request
        print(f"📋 Request User: {request.user}")
        print(f"📋 Is Authenticated: {request.user.is_authenticated}")
        print(f"📋 Username: {request.user.username if request.user.is_authenticated else 'AnonymousUser'}")
        print(f"📋 Headers: {dict(request.headers)}")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # ✅ OBTENER PROFESOR AUTENTICADO
        profesor = None
        
        # CASO 1: Usuario autenticado
        if request.user.is_authenticated:
            print(f"✅ Usuario autenticado: {request.user.username}")
            
            try:
                profesor = Profesor.objects.get(user=request.user)
                print(f"✅ Profesor encontrado: {profesor.nombre_completo} (ID: {profesor.id})")
            except Profesor.DoesNotExist:
                print(f"⚠️ Usuario '{request.user.username}' no tiene perfil de Profesor")
                
                # Intentar con profesor_id del request
                profesor_id = serializer.validated_data.get('profesor_id')
                if profesor_id:
                    print(f"🔄 Intentando con profesor_id del request: {profesor_id}")
                    try:
                        profesor = Profesor.objects.get(id=profesor_id)
                        print(f"✅ Profesor obtenido por ID: {profesor.nombre_completo}")
                    except Profesor.DoesNotExist:
                        print(f"❌ Profesor con ID {profesor_id} no existe")
                        return Response(
                            {'error': f'Profesor con ID {profesor_id} no encontrado'},
                            status=status.HTTP_404_NOT_FOUND
                        )
        else:
            # CASO 2: Usuario NO autenticado
            print("⚠️ Usuario NO autenticado (AnonymousUser)")
            
            profesor_id = serializer.validated_data.get('profesor_id')
            if profesor_id:
                print(f"🔄 Intentando con profesor_id del request: {profesor_id}")
                try:
                    profesor = Profesor.objects.get(id=profesor_id)
                    print(f"✅ Profesor obtenido por ID: {profesor.nombre_completo}")
                except Profesor.DoesNotExist:
                    print(f"❌ Profesor con ID {profesor_id} no existe")
                    return Response(
                        {'error': f'Profesor con ID {profesor_id} no encontrado'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                print("❌ No hay profesor_id en el request")
        
        # ⚠️ Validación final
        if not profesor:
            print("=" * 80)
            print("❌ ERROR FINAL: No se pudo determinar el profesor")
            print("=" * 80)
            return Response(
                {
                    'error': 'No se pudo determinar el profesor. Asegúrate de estar autenticado como profesor.',
                    'debug': {
                        'is_authenticated': request.user.is_authenticated,
                        'username': request.user.username if request.user.is_authenticated else None,
                        'tiene_profesor_id': 'profesor_id' in serializer.validated_data
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"✅ PROFESOR ASIGNADO: {profesor.nombre_completo} (ID: {profesor.id})")
        
        # Crear usuario automáticamente
        username = serializer.validated_data['codigo_estudiante']
        email = serializer.validated_data['correo']
        nombre = serializer.validated_data['nombre_completo']
        
        print(f"📝 Creando usuario: {username}")
        
        # Verificar si el usuario ya existe
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=nombre.split()[0] if nombre else '',
                last_name=' '.join(nombre.split()[1:]) if len(nombre.split()) > 1 else ''
            )
            print(f"✅ Usuario creado: {username}")
        except Exception as e:
            print(f"⚠️ Error creando usuario: {str(e)}")
            # Si el usuario ya existe, buscar un estudiante existente
            try:
                estudiante_existente = Estudiante.objects.get(
                    codigo_estudiante=username
                )
                print(f"⚠️ Estudiante ya existe: {username}")
                print("=" * 80)
                return Response(
                    EstudianteSerializer(estudiante_existente).data,
                    status=status.HTTP_200_OK
                )
            except Estudiante.DoesNotExist:
                print(f"❌ Usuario existe pero estudiante no: {username}")
                print("=" * 80)
                return Response(
                    {'error': f'Error creando usuario: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # ✅ Crear estudiante con profesor asignado
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
        
        print(f"✅ Estudiante creado exitosamente:")
        print(f"   ID: {estudiante.id}")
        print(f"   Nombre: {estudiante.nombre_completo}")
        print(f"   Código: {estudiante.codigo_estudiante}")
        print(f"   Profesor: {profesor.nombre_completo}")
        print("=" * 80)
        
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