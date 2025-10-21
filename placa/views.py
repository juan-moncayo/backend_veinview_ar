from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import DispositivoESP32, PracticaActiva, DatosSensor
from .serializers import (
    DispositivoESP32Serializer,
    PracticaActivaSerializer,
    DatosSensorSerializer,
    DatosSensorCreateSerializer
)


def get_client_ip(request):
    """Obtiene la IP real del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def verificar_api_key(request):
    """Verifica la API Key del ESP32"""
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    
    if not api_key:
        return None, Response(
            {'error': 'API Key no proporcionada. Use header X-API-Key o parámetro api_key'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        dispositivo = DispositivoESP32.objects.get(api_key=api_key, activo=True)
        # Actualizar última conexión
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.ip_address = get_client_ip(request)
        dispositivo.save(update_fields=['ultima_conexion', 'ip_address'])
        return dispositivo, None
    except DispositivoESP32.DoesNotExist:
        return None, Response(
            {'error': 'API Key inválida o dispositivo inactivo'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def registrar_dispositivo(request):
    """
    Endpoint para registrar un nuevo ESP32
    POST /api/placa/registrar/
    Body: {"mac_address": "AA:BB:CC:DD:EE:FF", "nombre": "VeinView-01"}
    """
    mac_address = request.data.get('mac_address', '').upper()
    nombre = request.data.get('nombre', 'VeinView Device')
    
    if not mac_address:
        return Response(
            {'error': 'mac_address es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verificar si ya existe
    dispositivo, created = DispositivoESP32.objects.get_or_create(
        mac_address=mac_address,
        defaults={
            'nombre': nombre,
            'ip_address': get_client_ip(request)
        }
    )
    
    if created:
        return Response({
            'message': 'Dispositivo registrado exitosamente',
            'dispositivo': DispositivoESP32Serializer(dispositivo).data,
            'api_key': dispositivo.api_key
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'message': 'Dispositivo ya existe',
            'dispositivo': DispositivoESP32Serializer(dispositivo).data,
            'api_key': dispositivo.api_key
        }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def verificar_conexion(request):
    """
    Endpoint para verificar conexión del ESP32
    GET /api/placa/ping/?api_key=xxx
    o Header: X-API-Key: xxx
    """
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response
    
    return Response({
        'status': 'ok',
        'message': 'Conexión exitosa',
        'dispositivo': dispositivo.nombre,
        'timestamp': timezone.now().isoformat()
    })


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def obtener_practica_activa(request):
    """
    Endpoint para verificar si hay una práctica activa
    GET /api/placa/practica-activa/?api_key=xxx
    Retorna la práctica activa (iniciada o pausada) si existe
    """
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response
    
    # Buscar práctica activa (no finalizada)
    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante').first()
    
    if practica_activa:
        return Response({
            'practica_activa': True,
            'practica': PracticaActivaSerializer(practica_activa).data,
            'puede_enviar_datos': practica_activa.estado == 'iniciada'
        })
    else:
        return Response({
            'practica_activa': False,
            'practica': None,
            'puede_enviar_datos': False,
            'message': 'No hay prácticas activas. Espere a que el profesor inicie una práctica.'
        })


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def enviar_datos_sensores(request):
    """
    Endpoint para recibir datos de sensores del ESP32
    POST /api/placa/datos/
    Headers: X-API-Key: xxx
    Body: {
        "ax": 0.5, "ay": -0.3, "az": 9.8,
        "gx": 2.1, "gy": -1.5, "gz": 0.8,
        "pitch": 15.5, "roll": -10.2, "yaw": 5.3,
        "fuerza": 250.5, "presion": 0.5
    }
    """
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response
    
    # Verificar que haya una práctica activa
    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado='iniciada'  # Solo aceptar datos si está iniciada (no pausada)
    ).first()
    
    if not practica_activa:
        return Response({
            'error': 'No hay práctica activa o está pausada',
            'puede_enviar_datos': False
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validar datos
    serializer = DatosSensorCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Datos inválidos',
            'detalles': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Guardar datos
    datos = serializer.validated_data
    dato_sensor = DatosSensor.objects.create(
        practica=practica_activa,
        dispositivo=dispositivo,
        aceleracion_x=datos['ax'],
        aceleracion_y=datos['ay'],
        aceleracion_z=datos['az'],
        giroscopio_x=datos['gx'],
        giroscopio_y=datos['gy'],
        giroscopio_z=datos['gz'],
        angulo_pitch=datos['pitch'],
        angulo_roll=datos['roll'],
        angulo_yaw=datos['yaw'],
        fuerza=datos['fuerza'],
        presion=datos.get('presion'),
        ip_origen=get_client_ip(request)
    )
    
    return Response({
        'status': 'ok',
        'message': 'Datos guardados exitosamente',
        'dato_id': dato_sensor.id,
        'practica_id': practica_activa.id,
        'estudiante': practica_activa.estudiante.nombre_completo
    }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def estado_sistema(request):
    """
    Endpoint de estado completo del sistema
    GET /api/placa/estado/?api_key=xxx
    """
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response
    
    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante').first()
    
    if practica_activa:
        total_datos = DatosSensor.objects.filter(practica=practica_activa).count()
    else:
        total_datos = 0
    
    return Response({
        'dispositivo': {
            'nombre': dispositivo.nombre,
            'mac': dispositivo.mac_address,
            'activo': dispositivo.activo
        },
        'practica_activa': practica_activa is not None,
        'practica': PracticaActivaSerializer(practica_activa).data if practica_activa else None,
        'total_datos_capturados': total_datos,
        'timestamp': timezone.now().isoformat()
    })


# ============================================
# AGREGAR AL FINAL DE TU placa/views.py ACTUAL
# NO BORRES NADA DE LO QUE YA TIENES
# ============================================

from rest_framework import viewsets
from estudiantes.models import Estudiante
from estudiantes.serializers import EstudianteSerializer

# ViewSet para listar dispositivos ESP32
class DispositivoESP32ViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para listar dispositivos ESP32
    GET /api/placa/dispositivos/
    """
    queryset = DispositivoESP32.objects.all()
    serializer_class = DispositivoESP32Serializer
    permission_classes = [AllowAny]


# ViewSet para gestionar prácticas
class PracticaActivaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para crear y actualizar prácticas
    GET /api/placa/practicas/
    POST /api/placa/practicas/
    PATCH /api/placa/practicas/{id}/
    """
    queryset = PracticaActiva.objects.select_related('estudiante', 'dispositivo').all()
    serializer_class = PracticaActivaSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Crear nueva práctica"""
        estudiante_id = request.data.get('estudiante_id')
        dispositivo_id = request.data.get('dispositivo_id')
        
        if not estudiante_id or not dispositivo_id:
            return Response(
                {'error': 'estudiante_id y dispositivo_id son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            estudiante = Estudiante.objects.get(id=estudiante_id)
            dispositivo = DispositivoESP32.objects.get(id=dispositivo_id)
        except Estudiante.DoesNotExist:
            return Response(
                {'error': 'Estudiante no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DispositivoESP32.DoesNotExist:
            return Response(
                {'error': 'Dispositivo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Crear práctica
        practica = PracticaActiva.objects.create(
            estudiante=estudiante,
            dispositivo=dispositivo,
            estado='iniciada'
        )
        
        serializer = self.get_serializer(practica)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def partial_update(self, request, *args, **kwargs):
        """Actualizar estado de práctica (PATCH)"""
        practica = self.get_object()
        nuevo_estado = request.data.get('estado')
        
        if nuevo_estado not in ['iniciada', 'pausada', 'finalizada']:
            return Response(
                {'error': 'Estado inválido. Use: iniciada, pausada o finalizada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Actualizar estado usando el método del modelo
        if nuevo_estado == 'pausada' and practica.estado == 'iniciada':
            practica.pausar()
        elif nuevo_estado == 'iniciada' and practica.estado == 'pausada':
            practica.reanudar()
        elif nuevo_estado == 'finalizada':
            practica.finalizar()
        else:
            practica.estado = nuevo_estado
            practica.save()
        
        serializer = self.get_serializer(practica)
        return Response(serializer.data)


# ViewSet para listar datos de sensores
class DatosSensorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para listar datos de sensores
    GET /api/placa/datos-sensores/?practica=1&limit=10
    """
    queryset = DatosSensor.objects.all()
    serializer_class = DatosSensorSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = DatosSensor.objects.select_related('practica', 'dispositivo').all()
        practica_id = self.request.query_params.get('practica', None)
        
        if practica_id:
            queryset = queryset.filter(practica_id=practica_id)
        
        # Ordenar por timestamp descendente
        queryset = queryset.order_by('-timestamp')
        
        # Limitar resultados
        limit = self.request.query_params.get('limit', None)
        if limit:
            try:
                queryset = queryset[:int(limit)]
            except ValueError:
                pass
        
        return queryset