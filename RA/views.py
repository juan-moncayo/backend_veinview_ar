from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta
import time

from .models import SesionRA, DatosVisualizacionRA, ConfiguracionRA, EventoRA
from .serializers import (
    SesionRASerializer,
    SesionRACreateSerializer,
    DatosVisualizacionRASerializer,
    ConfiguracionRASerializer,
    EventoRASerializer,
    DatosSensorRASerializer,
    StreamDatosRASerializer,
    EstadoPracticaRASerializer,
    RespuestaConexionRASerializer,
    HeartbeatSerializer
)
from placa.models import PracticaActiva, DatosSensor, DispositivoESP32
from estudiantes.models import Estudiante


def get_client_ip(request):
    """Obtiene la IP real del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def verificar_session_token(request):
    """
    Verifica el token de sesión RA desde header o query params
    Retorna (sesion, error_response)
    """
    session_token = request.headers.get('X-Session-Token') or request.GET.get('session_token')
    
    if not session_token:
        return None, Response(
            {'error': 'Session token no proporcionado. Use header X-Session-Token o parámetro session_token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        sesion = SesionRA.objects.select_related('estudiante', 'practica').get(
            session_token=session_token
        )
        
        # Verificar si la sesión está activa
        if not sesion.esta_activa():
            return None, Response(
                {'error': 'Sesión expirada o inactiva'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Actualizar última actividad
        sesion.fecha_ultima_actividad = timezone.now()
        sesion.save(update_fields=['fecha_ultima_actividad'])
        
        return sesion, None
        
    except SesionRA.DoesNotExist:
        return None, Response(
            {'error': 'Session token inválido'},
            status=status.HTTP_401_UNAUTHORIZED
        )


# ==========================================
# ENDPOINTS PRINCIPALES PARA UNREAL ENGINE
# ==========================================

@api_view(['POST'])
@permission_classes([AllowAny])
def conectar_ra(request):
    """
    Endpoint para iniciar una sesión RA desde Unreal Engine
    
    POST /api/ra/conectar/
    Body: {
        "estudiante_id": 1,
        "practica_id": 2,  // Opcional
        "dispositivo_ra": "HoloLens 2",
        "modo_visualizacion": "overlay",
        "escala_modelo": 1.0,
        "opacidad": 0.8
    }
    
    Response: {
        "status": "success",
        "message": "Conexión establecida",
        "session_token": "xxx",
        "sesion_id": 1,
        "estudiante": {...},
        "configuracion": {...},
        "endpoints": {...}
    }
    """
    serializer = SesionRACreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    estudiante = Estudiante.objects.get(id=data['estudiante_id'])
    
    # Verificar si hay práctica activa
    practica = None
    if data.get('practica_id'):
        practica = PracticaActiva.objects.get(id=data['practica_id'])
    
    # Finalizar sesiones anteriores del mismo estudiante
    SesionRA.objects.filter(
        estudiante=estudiante,
        estado__in=['conectando', 'activa', 'pausada']
    ).update(estado='desconectada', fecha_fin=timezone.now())
    
    # Crear nueva sesión
    sesion = SesionRA.objects.create(
        estudiante=estudiante,
        practica=practica,
        dispositivo_ra=data['dispositivo_ra'],
        ip_address=get_client_ip(request),
        estado='activa',
        modo_visualizacion=data['modo_visualizacion'],
        escala_modelo=data['escala_modelo'],
        opacidad=data['opacidad']
    )
    
    # Registrar evento de conexión
    EventoRA.objects.create(
        sesion=sesion,
        tipo='conexion',
        descripcion=f'Conexión establecida desde {sesion.dispositivo_ra}',
        datos_adicionales={
            'ip': sesion.ip_address,
            'dispositivo': sesion.dispositivo_ra
        }
    )
    
    # Obtener o crear configuración del estudiante
    config, created = ConfiguracionRA.objects.get_or_create(
        estudiante=estudiante,
        defaults={
            'color_angulo_correcto': '#00FF00',
            'color_angulo_incorrecto': '#FF0000',
            'color_fuerza_correcta': '#0000FF',
        }
    )
    
    # Preparar respuesta
    response_data = {
        'status': 'success',
        'message': 'Conexión establecida exitosamente',
        'session_token': sesion.session_token,
        'sesion_id': sesion.id,
        'estudiante': {
            'id': estudiante.id,
            'nombre': estudiante.nombre_completo,
            'codigo': estudiante.codigo_estudiante
        },
        'configuracion': ConfiguracionRASerializer(config).data,
        'endpoints': {
            'stream': '/api/ra/stream/',
            'estado_practica': '/api/ra/estado-practica/',
            'heartbeat': '/api/ra/heartbeat/',
            'desconectar': '/api/ra/desconectar/',
            'eventos': '/api/ra/eventos/'
        }
    }
    
    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def stream_datos_ra(request):
    """
    Endpoint para obtener datos en tiempo real para Unreal Engine
    
    GET /api/ra/stream/?session_token=xxx&limit=10
    
    Headers: X-Session-Token: xxx
    
    Response: {
        "status": "ok",
        "timestamp": 1234567890,
        "datos": [
            {
                "timestamp": 1234567890,
                "pitch": 15.5,
                "roll": -10.2,
                "yaw": 5.3,
                "fuerza": 250.5,
                "presion": 0.5,
                "tecnica_correcta": true,
                "dato_id": 123
            }
        ],
        "practica_activa": true,
        "estado_practica": "iniciada"
    }
    """
    sesion, error_response = verificar_session_token(request)
    if error_response:
        return error_response
    
    # Obtener límite de datos
    limit = int(request.GET.get('limit', 10))
    limit = min(limit, 100)  # Máximo 100 datos por request
    
    # Verificar si hay práctica activa
    if not sesion.practica:
        return Response({
            'status': 'no_practice',
            'message': 'No hay práctica activa asociada a esta sesión',
            'datos': [],
            'practica_activa': False
        })
    
    # Obtener últimos datos de la práctica
    datos = DatosSensor.objects.filter(
        practica=sesion.practica
    ).order_by('-timestamp')[:limit]
    
    # Convertir a formato optimizado para Unreal
    datos_stream = []
    for dato in datos:
        datos_stream.append({
            'timestamp': int(time.mktime(dato.timestamp.timetuple()) * 1000),
            'pitch': round(dato.angulo_pitch, 2),
            'roll': round(dato.angulo_roll, 2),
            'yaw': round(dato.angulo_yaw, 2),
            'fuerza': round(dato.fuerza, 2),
            'presion': round(dato.presion, 2) if dato.presion else None,
            'tecnica_correcta': dato.tecnica_correcta,
            'dato_id': dato.id
        })
        
        # Registrar que se envió este dato
        DatosVisualizacionRA.objects.create(
            sesion=sesion,
            dato_sensor=dato,
            entregado=True
        )
    
    # Actualizar contador de datos enviados
    sesion.total_datos_recibidos += len(datos_stream)
    sesion.save(update_fields=['total_datos_recibidos'])
    
    return Response({
        'status': 'ok',
        'timestamp': int(time.time() * 1000),
        'datos': datos_stream,
        'practica_activa': sesion.practica.estado in ['iniciada', 'pausada'],
        'estado_practica': sesion.practica.estado
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def estado_practica_ra(request):
    """
    Endpoint para obtener el estado completo de la práctica actual
    
    GET /api/ra/estado-practica/?session_token=xxx
    
    Response: {
        "practica_activa": true,
        "practica_id": 1,
        "estudiante_nombre": "Juan Pérez",
        "estado": "iniciada",
        "tiempo_transcurrido": 1234,
        "numero_intentos": 5,
        "precision_actual": 85.5,
        "ultimo_dato": {...},
        "rangos_optimos": {
            "pitch": {"min": 10, "max": 30},
            "fuerza": {"min": 50, "max": 300}
        }
    }
    """
    sesion, error_response = verificar_session_token(request)
    if error_response:
        return error_response
    
    if not sesion.practica:
        return Response({
            'practica_activa': False,
            'practica_id': None,
            'estudiante_nombre': sesion.estudiante.nombre_completo,
            'estado': None,
            'tiempo_transcurrido': 0,
            'numero_intentos': 0,
            'precision_actual': 0.0,
            'ultimo_dato': None,
            'rangos_optimos': {
                'pitch': {'min': 10, 'max': 30},
                'roll': {'min': -15, 'max': 15},
                'fuerza': {'min': 50, 'max': 300}
            }
        })
    
    practica = sesion.practica
    
    # Calcular tiempo transcurrido
    if practica.estado == 'finalizada':
        tiempo_transcurrido = practica.duracion_total_segundos
    elif practica.estado == 'pausada':
        tiempo_transcurrido = practica.duracion_total_segundos
    else:  # iniciada
        ahora = timezone.now()
        if practica.fecha_reanudacion:
            tiempo_actual = (ahora - practica.fecha_reanudacion).total_seconds()
        else:
            tiempo_actual = (ahora - practica.fecha_inicio).total_seconds()
        tiempo_transcurrido = int(practica.duracion_total_segundos + tiempo_actual)
    
    # Calcular precisión actual
    datos_totales = DatosSensor.objects.filter(practica=practica).count()
    datos_correctos = DatosSensor.objects.filter(
        practica=practica,
        tecnica_correcta=True
    ).count()
    precision_actual = (datos_correctos / datos_totales * 100) if datos_totales > 0 else 0
    
    # Obtener último dato
    ultimo_dato_obj = DatosSensor.objects.filter(practica=practica).order_by('-timestamp').first()
    ultimo_dato = None
    if ultimo_dato_obj:
        ultimo_dato = {
            'pitch': round(ultimo_dato_obj.angulo_pitch, 2),
            'roll': round(ultimo_dato_obj.angulo_roll, 2),
            'yaw': round(ultimo_dato_obj.angulo_yaw, 2),
            'fuerza': round(ultimo_dato_obj.fuerza, 2),
            'tecnica_correcta': ultimo_dato_obj.tecnica_correcta,
            'timestamp': int(time.mktime(ultimo_dato_obj.timestamp.timetuple()) * 1000)
        }
    
    return Response({
        'practica_activa': True,
        'practica_id': practica.id,
        'estudiante_nombre': practica.estudiante.nombre_completo,
        'estado': practica.estado,
        'tiempo_transcurrido': tiempo_transcurrido,
        'numero_intentos': practica.numero_intentos,
        'precision_actual': round(precision_actual, 2),
        'ultimo_dato': ultimo_dato,
        'rangos_optimos': {
            'pitch': {'min': 10, 'max': 30},
            'roll': {'min': -15, 'max': 15},
            'fuerza': {'min': 50, 'max': 300}
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def heartbeat_ra(request):
    """
    Endpoint para mantener la sesión activa (heartbeat)
    Unreal Engine debe llamar a este endpoint cada 10-15 segundos
    
    POST /api/ra/heartbeat/
    Body: {
        "session_token": "xxx",
        "timestamp": 1234567890,
        "latencia_cliente": 45.5  // Opcional, en ms
    }
    
    Response: {
        "status": "ok",
        "sesion_activa": true,
        "timestamp_servidor": 1234567890
    }
    """
    serializer = HeartbeatSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    session_token = serializer.validated_data['session_token']
    
    try:
        sesion = SesionRA.objects.get(session_token=session_token)
        
        # Actualizar última actividad
        sesion.fecha_ultima_actividad = timezone.now()
        
        # Actualizar latencia promedio si se proporciona
        if serializer.validated_data.get('latencia_cliente'):
            latencia_nueva = serializer.validated_data['latencia_cliente']
            if sesion.latencia_promedio == 0:
                sesion.latencia_promedio = latencia_nueva
            else:
                # Promedio móvil
                sesion.latencia_promedio = (sesion.latencia_promedio * 0.8 + latencia_nueva * 0.2)
        
        sesion.save(update_fields=['fecha_ultima_actividad', 'latencia_promedio'])
        
        return Response({
            'status': 'ok',
            'sesion_activa': True,
            'timestamp_servidor': int(time.time() * 1000),
            'latencia_promedio': round(sesion.latencia_promedio, 2)
        })
        
    except SesionRA.DoesNotExist:
        return Response({
            'status': 'error',
            'error': 'Sesión no encontrada',
            'sesion_activa': False
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def desconectar_ra(request):
    """
    Endpoint para cerrar una sesión RA
    
    POST /api/ra/desconectar/
    Body: {
        "session_token": "xxx"
    }
    
    Response: {
        "status": "ok",
        "message": "Sesión finalizada",
        "estadisticas": {...}
    }
    """
    session_token = request.data.get('session_token')
    
    if not session_token:
        return Response(
            {'error': 'session_token es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        sesion = SesionRA.objects.get(session_token=session_token)
        
        # Registrar evento de desconexión
        EventoRA.objects.create(
            sesion=sesion,
            tipo='desconexion',
            descripcion='Desconexión solicitada por el cliente',
            datos_adicionales={
                'duracion_segundos': (timezone.now() - sesion.fecha_inicio).total_seconds()
            }
        )
        
        # Finalizar sesión
        sesion.finalizar()
        
        # Estadísticas de la sesión
        estadisticas = {
            'duracion_total': int((sesion.fecha_fin - sesion.fecha_inicio).total_seconds()),
            'total_datos_recibidos': sesion.total_datos_recibidos,
            'latencia_promedio': round(sesion.latencia_promedio, 2)
        }
        
        return Response({
            'status': 'ok',
            'message': 'Sesión finalizada exitosamente',
            'estadisticas': estadisticas
        })
        
    except SesionRA.DoesNotExist:
        return Response(
            {'error': 'Sesión no encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def registrar_evento_ra(request):
    """
    Endpoint para registrar eventos desde Unreal Engine
    
    POST /api/ra/eventos/
    Body: {
        "session_token": "xxx",
        "tipo": "calibracion",
        "descripcion": "Usuario calibró el sistema",
        "datos_adicionales": {...}
    }
    """
    sesion, error_response = verificar_session_token(request)
    if error_response:
        return error_response
    
    tipo = request.data.get('tipo', 'error')
    descripcion = request.data.get('descripcion', '')
    datos_adicionales = request.data.get('datos_adicionales', {})
    
    evento = EventoRA.objects.create(
        sesion=sesion,
        tipo=tipo,
        descripcion=descripcion,
        datos_adicionales=datos_adicionales
    )
    
    return Response({
        'status': 'ok',
        'evento_id': evento.id,
        'timestamp': int(time.mktime(evento.timestamp.timetuple()) * 1000)
    }, status=status.HTTP_201_CREATED)


# ==========================================
# VIEWSETS PARA ADMINISTRACIÓN WEB
# ==========================================

class SesionRAViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar sesiones RA desde el panel web
    """
    queryset = SesionRA.objects.select_related('estudiante', 'practica').all()
    serializer_class = SesionRASerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def activas(self, request):
        """Obtener todas las sesiones activas"""
        sesiones_activas = self.queryset.filter(
            estado__in=['activa', 'pausada']
        )
        serializer = self.get_serializer(sesiones_activas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Finalizar una sesión manualmente"""
        sesion = self.get_object()
        sesion.finalizar()
        
        EventoRA.objects.create(
            sesion=sesion,
            tipo='desconexion',
            descripcion='Sesión finalizada manualmente desde el panel web'
        )
        
        return Response({
            'message': 'Sesión finalizada',
            'sesion': self.get_serializer(sesion).data
        })


class ConfiguracionRAViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar configuraciones RA
    """
    queryset = ConfiguracionRA.objects.select_related('estudiante').all()
    serializer_class = ConfiguracionRASerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def por_estudiante(self, request):
        """Obtener configuración de un estudiante específico"""
        estudiante_id = request.query_params.get('estudiante_id')
        
        if not estudiante_id:
            return Response(
                {'error': 'estudiante_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        config, created = ConfiguracionRA.objects.get_or_create(
            estudiante_id=estudiante_id,
            defaults={
                'color_angulo_correcto': '#00FF00',
                'color_angulo_incorrecto': '#FF0000',
                'color_fuerza_correcta': '#0000FF',
            }
        )
        
        return Response(self.get_serializer(config).data)


class EventoRAViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver eventos RA (solo lectura)
    """
    queryset = EventoRA.objects.select_related('sesion').all()
    serializer_class = EventoRASerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = EventoRA.objects.all()
        sesion_id = self.request.query_params.get('sesion_id')
        
        if sesion_id:
            queryset = queryset.filter(sesion_id=sesion_id)
        
        return queryset.order_by('-timestamp')