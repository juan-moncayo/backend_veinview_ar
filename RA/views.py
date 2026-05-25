from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta
import time
from django.shortcuts import render

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
# NUEVO: ENDPOINTS DE CONEXIÓN AUTOMÁTICA
# ==========================================

@api_view(['POST'])
@permission_classes([AllowAny])
def conectar_automatico(request):
    """
    🆕 Endpoint para conexión automática desde Unity
    Detecta la práctica activa automáticamente y conecta el dispositivo RA
    
    POST /api/ra/conectar-automatico/
    Body: {
        "dispositivo_ra": "Meta Quest 3",
        "device_id": "UNIQUE-DEVICE-ID-12345",  // MAC address o identificador único
        "modo_visualizacion": "overlay",
        "escala_modelo": 1.0,
        "opacidad": 0.8
    }
    
    Response: {
        "status": "success",
        "message": "Conectado a práctica activa",
        "session_token": "xxx",
        "sesion_id": 1,
        "practica_activa": true,
        "practica": {...},
        "estudiante": {...},
        "configuracion": {...}
    }
    """
    dispositivo_ra = request.data.get('dispositivo_ra', 'Meta Quest 3')
    device_id = request.data.get('device_id')
    modo_visualizacion = request.data.get('modo_visualizacion', 'overlay')
    escala_modelo = request.data.get('escala_modelo', 1.0)
    opacidad = request.data.get('opacidad', 0.8)
    
    if not device_id:
        return Response(
            {'error': 'device_id es requerido (MAC address o identificador único del dispositivo)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # 1. Buscar práctica activa en el sistema (iniciada o pausada)
    practica_activa = PracticaActiva.objects.filter(
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante', 'dispositivo').order_by('-fecha_inicio').first()
    
    if not practica_activa:
        return Response({
            'status': 'no_practice',
            'message': 'No hay ninguna práctica activa en este momento. Espere a que un estudiante inicie una práctica.',
            'practica_activa': False,
            'session_token': None
        }, status=status.HTTP_200_OK)
    
    estudiante = practica_activa.estudiante
    
    # 2. Verificar si ya existe una sesión activa para este dispositivo
    sesion_existente = SesionRA.objects.filter(
        dispositivo_ra__icontains=device_id,
        estado__in=['activa', 'pausada']
    ).first()
    
    if sesion_existente:
        # Actualizar la sesión existente con la práctica actual
        sesion_existente.practica = practica_activa
        sesion_existente.estudiante = estudiante
        sesion_existente.estado = 'activa'
        sesion_existente.fecha_ultima_actividad = timezone.now()
        sesion_existente.ip_address = get_client_ip(request)
        sesion_existente.save()
        
        sesion = sesion_existente
        mensaje = 'Reconectado a práctica activa'
    else:
        # 3. Finalizar otras sesiones del mismo dispositivo
        SesionRA.objects.filter(
            dispositivo_ra__icontains=device_id,
            estado__in=['conectando', 'activa', 'pausada']
        ).update(estado='desconectada', fecha_fin=timezone.now())
        
        # 4. Crear nueva sesión RA
        sesion = SesionRA.objects.create(
            estudiante=estudiante,
            practica=practica_activa,
            dispositivo_ra=f"{dispositivo_ra} ({device_id})",
            ip_address=get_client_ip(request),
            estado='activa',
            modo_visualizacion=modo_visualizacion,
            escala_modelo=escala_modelo,
            opacidad=opacidad
        )
        
        mensaje = 'Conectado exitosamente a práctica activa'
        
        # Registrar evento de conexión
        EventoRA.objects.create(
            sesion=sesion,
            tipo='conexion',
            descripcion=f'Conexión automática desde {sesion.dispositivo_ra}',
            datos_adicionales={
                'ip': sesion.ip_address,
                'device_id': device_id,
                'practica_id': practica_activa.id,
                'estudiante_id': estudiante.id
            }
        )
    
    # 5. Obtener o crear configuración del estudiante
    config, created = ConfiguracionRA.objects.get_or_create(
        estudiante=estudiante,
        defaults={
            'color_angulo_correcto': '#00FF00',
            'color_angulo_incorrecto': '#FF0000',
            'color_fuerza_correcta': '#0000FF',
        }
    )
    
    # 6. Preparar respuesta
    response_data = {
        'status': 'success',
        'message': mensaje,
        'session_token': sesion.session_token,
        'sesion_id': sesion.id,
        'practica_activa': True,
        'practica': {
            'id': practica_activa.id,
            'estado': practica_activa.estado,
            'fecha_inicio': practica_activa.fecha_inicio.isoformat(),
            'duracion_segundos': practica_activa.duracion_total_segundos
        },
        'estudiante': {
            'id': estudiante.id,
            'nombre': estudiante.nombre_completo,
            'codigo': estudiante.codigo_estudiante
        },
        'configuracion': ConfiguracionRASerializer(config).data,
        'endpoints': {
            'alertas': '/api/ra/alertas/',
            'heartbeat': '/api/ra/heartbeat/',
            'desconectar': '/api/ra/desconectar/',
            'practica_actual': '/api/ra/practica-actual/'
        }
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def practica_actual(request):
    """
    🆕 Endpoint para verificar qué práctica está activa actualmente
    
    GET /api/ra/practica-actual/
    
    Response: {
        "practica_activa": true,
        "practica_id": 5,
        "estudiante": {...},
        "estado": "iniciada",
        "cambio_detectado": false
    }
    """
    practica_activa = PracticaActiva.objects.filter(
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante').order_by('-fecha_inicio').first()
    
    if not practica_activa:
        return Response({
            'practica_activa': False,
            'practica_id': None,
            'estudiante': None,
            'estado': None,
            'message': 'No hay prácticas activas en este momento'
        })
    
    return Response({
        'practica_activa': True,
        'practica_id': practica_activa.id,
        'estudiante': {
            'id': practica_activa.estudiante.id,
            'nombre': practica_activa.estudiante.nombre_completo,
            'codigo': practica_activa.estudiante.codigo_estudiante
        },
        'estado': practica_activa.estado,
        'fecha_inicio': practica_activa.fecha_inicio.isoformat(),
        'duracion_segundos': practica_activa.duracion_total_segundos
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def alertas_ra(request):
    """
    🆕 Endpoint mejorado para obtener alertas en tiempo real
    Unity consulta este endpoint cada 0.5 segundos
    
    GET /api/ra/alertas/?session_token=xxx
    
    Response: {
        "status": "ok",
        "timestamp": 1234567890,
        "alertas_activas": true,
        "alerta_critica": false,
        "tecnica_correcta": false,
        "fuerza": {
            "activa": true,
            "valor_actual": 350.5,
            "en_rango_optimo": false,
            "en_rango_aceptable": false,
            "mensaje": "Fuerza muy alta"
        },
        "angulo": {
            "activa": true,
            "valor_actual": 45.2,
            "en_rango_optimo": false,
            "en_rango_aceptable": true,
            "mensaje": "Ángulo ligeramente alto"
        },
        "rangos": {
            "angulo_optimo": {"min": 10, "max": 30},
            "fuerza_optima": {"min": 50, "max": 300}
        }
    }
    """
    sesion, error_response = verificar_session_token(request)
    if error_response:
        return error_response
    
    # Verificar si hay práctica activa
    if not sesion.practica or sesion.practica.estado != 'iniciada':
        return Response({
            'status': 'no_practice',
            'message': 'No hay práctica activa o está pausada',
            'timestamp': int(time.time() * 1000),
            'alertas_activas': False,
            'alerta_critica': False,
            'tecnica_correcta': False,
            'fuerza': {
                'activa': False,
                'valor_actual': 0.0,
                'en_rango_optimo': True,
                'en_rango_aceptable': True,
                'mensaje': 'Sin datos'
            },
            'angulo': {
                'activa': False,
                'valor_actual': 0.0,
                'en_rango_optimo': True,
                'en_rango_aceptable': True,
                'mensaje': 'Sin datos'
            },
            'rangos': {
                'angulo_optimo': {'min': 10, 'max': 30},
                'fuerza_optima': {'min': 50, 'max': 300}
            }
        })
    
    # Obtener el dato más reciente
    ultimo_dato = DatosSensor.objects.filter(
        practica=sesion.practica
    ).order_by('-timestamp').first()
    
    if not ultimo_dato:
        return Response({
            'status': 'ok',
            'message': 'Esperando datos de sensores...',
            'timestamp': int(time.time() * 1000),
            'alertas_activas': False,
            'alerta_critica': False,
            'tecnica_correcta': False,
            'fuerza': {
                'activa': False,
                'valor_actual': 0.0,
                'en_rango_optimo': True,
                'en_rango_aceptable': True,
                'mensaje': 'Esperando datos'
            },
            'angulo': {
                'activa': False,
                'valor_actual': 0.0,
                'en_rango_optimo': True,
                'en_rango_aceptable': True,
                'mensaje': 'Esperando datos'
            },
            'rangos': {
                'angulo_optimo': {'min': 10, 'max': 30},
                'fuerza_optima': {'min': 50, 'max': 300}
            }
        })
    
    # Rangos de validación
    ANGULO_MIN_OPTIMO = 10
    ANGULO_MAX_OPTIMO = 30
    ANGULO_MIN_ACEPTABLE = 5
    ANGULO_MAX_ACEPTABLE = 40
    
    FUERZA_MIN_OPTIMA = 50
    FUERZA_MAX_OPTIMA = 300
    FUERZA_MIN_ACEPTABLE = 30
    FUERZA_MAX_ACEPTABLE = 400
    
    # Evaluar ángulo
    angulo_actual = ultimo_dato.angulo_pitch
    angulo_en_rango_optimo = ANGULO_MIN_OPTIMO <= angulo_actual <= ANGULO_MAX_OPTIMO
    angulo_en_rango_aceptable = ANGULO_MIN_ACEPTABLE <= angulo_actual <= ANGULO_MAX_ACEPTABLE
    
    if angulo_en_rango_optimo:
        angulo_mensaje = "Ángulo correcto"
        angulo_alerta = False
    elif angulo_en_rango_aceptable:
        if angulo_actual < ANGULO_MIN_OPTIMO:
            angulo_mensaje = "Ángulo bajo - Ajustar ligeramente"
        else:
            angulo_mensaje = "Ángulo alto - Ajustar ligeramente"
        angulo_alerta = True
    else:
        if angulo_actual < ANGULO_MIN_ACEPTABLE:
            angulo_mensaje = "⚠️ ÁNGULO MUY BAJO"
        else:
            angulo_mensaje = "⚠️ ÁNGULO MUY ALTO"
        angulo_alerta = True
    
    # Evaluar fuerza
    fuerza_actual = ultimo_dato.fuerza
    fuerza_en_rango_optimo = FUERZA_MIN_OPTIMA <= fuerza_actual <= FUERZA_MAX_OPTIMA
    fuerza_en_rango_aceptable = FUERZA_MIN_ACEPTABLE <= fuerza_actual <= FUERZA_MAX_ACEPTABLE
    
    if fuerza_en_rango_optimo:
        fuerza_mensaje = "Fuerza correcta"
        fuerza_alerta = False
    elif fuerza_en_rango_aceptable:
        if fuerza_actual < FUERZA_MIN_OPTIMA:
            fuerza_mensaje = "Fuerza baja - Presionar más"
        else:
            fuerza_mensaje = "Fuerza alta - Reducir presión"
        fuerza_alerta = True
    else:
        if fuerza_actual < FUERZA_MIN_ACEPTABLE:
            fuerza_mensaje = "⚠️ FUERZA MUY BAJA"
        else:
            fuerza_mensaje = "⚠️ FUERZA MUY ALTA"
        fuerza_alerta = True
    
    # Determinar si hay alertas críticas
    alerta_critica = (
        (not angulo_en_rango_aceptable) or 
        (not fuerza_en_rango_aceptable)
    )
    
    # Técnica correcta = ambos en rango óptimo
    tecnica_correcta = angulo_en_rango_optimo and fuerza_en_rango_optimo
    
    alertas_activas = angulo_alerta or fuerza_alerta
    
    return Response({
        'status': 'ok',
        'timestamp': int(time.time() * 1000),
        'alertas_activas': alertas_activas,
        'alerta_critica': alerta_critica,
        'tecnica_correcta': tecnica_correcta,
        'fuerza': {
            'activa': fuerza_alerta,
            'valor_actual': round(fuerza_actual, 2),
            'en_rango_optimo': fuerza_en_rango_optimo,
            'en_rango_aceptable': fuerza_en_rango_aceptable,
            'mensaje': fuerza_mensaje
        },
        'angulo': {
            'activa': angulo_alerta,
            'valor_actual': round(angulo_actual, 2),
            'en_rango_optimo': angulo_en_rango_optimo,
            'en_rango_aceptable': angulo_en_rango_aceptable,
            'mensaje': angulo_mensaje
        },
        'rangos': {
            'angulo_optimo': {'min': ANGULO_MIN_OPTIMO, 'max': ANGULO_MAX_OPTIMO},
            'fuerza_optima': {'min': FUERZA_MIN_OPTIMA, 'max': FUERZA_MAX_OPTIMA}
        }
    })


# ==========================================
# ENDPOINTS EXISTENTES (MANTENIDOS)
# ==========================================

@api_view(['POST'])
@permission_classes([AllowAny])
def conectar_ra(request):
    """
    Endpoint ORIGINAL para iniciar una sesión RA desde Unreal Engine
    (MANTENIDO para compatibilidad)
    """
    serializer = SesionRACreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    estudiante = Estudiante.objects.get(id=data['estudiante_id'])
    
    practica = None
    if data.get('practica_id'):
        practica = PracticaActiva.objects.get(id=data['practica_id'])
    
    SesionRA.objects.filter(
        estudiante=estudiante,
        estado__in=['conectando', 'activa', 'pausada']
    ).update(estado='desconectada', fecha_fin=timezone.now())
    
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
    
    EventoRA.objects.create(
        sesion=sesion,
        tipo='conexion',
        descripcion=f'Conexión establecida desde {sesion.dispositivo_ra}',
        datos_adicionales={
            'ip': sesion.ip_address,
            'dispositivo': sesion.dispositivo_ra
        }
    )
    
    config, created = ConfiguracionRA.objects.get_or_create(
        estudiante=estudiante,
        defaults={
            'color_angulo_correcto': '#00FF00',
            'color_angulo_incorrecto': '#FF0000',
            'color_fuerza_correcta': '#0000FF',
        }
    )
    
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
    """Endpoint para obtener datos en tiempo real para Unreal Engine"""
    sesion, error_response = verificar_session_token(request)
    if error_response:
        return error_response
    
    limit = int(request.GET.get('limit', 10))
    limit = min(limit, 100)
    
    if not sesion.practica:
        return Response({
            'status': 'no_practice',
            'message': 'No hay práctica activa asociada a esta sesión',
            'datos': [],
            'practica_activa': False
        })
    
    datos = DatosSensor.objects.filter(
        practica=sesion.practica
    ).order_by('-timestamp')[:limit]
    
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
        
        DatosVisualizacionRA.objects.create(
            sesion=sesion,
            dato_sensor=dato,
            entregado=True
        )
    
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
    """Endpoint para obtener el estado completo de la práctica actual"""
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
    
    if practica.estado == 'finalizada':
        tiempo_transcurrido = practica.duracion_total_segundos
    elif practica.estado == 'pausada':
        tiempo_transcurrido = practica.duracion_total_segundos
    else:
        ahora = timezone.now()
        if practica.fecha_reanudacion:
            tiempo_actual = (ahora - practica.fecha_reanudacion).total_seconds()
        else:
            tiempo_actual = (ahora - practica.fecha_inicio).total_seconds()
        tiempo_transcurrido = int(practica.duracion_total_segundos + tiempo_actual)
    
    datos_totales = DatosSensor.objects.filter(practica=practica).count()
    datos_correctos = DatosSensor.objects.filter(
        practica=practica,
        tecnica_correcta=True
    ).count()
    precision_actual = (datos_correctos / datos_totales * 100) if datos_totales > 0 else 0
    
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
            'pitch': {'min': -30, 'max': 30},
            'roll': {'min': -30, 'max': 30},
            'fuerza': {'min': 50, 'max': 300}
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def heartbeat_ra(request):
    """Endpoint para mantener la sesión activa (heartbeat)"""
    serializer = HeartbeatSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    session_token = serializer.validated_data['session_token']
    
    try:
        sesion = SesionRA.objects.get(session_token=session_token)
        
        sesion.fecha_ultima_actividad = timezone.now()
        
        if serializer.validated_data.get('latencia_cliente'):
            latencia_nueva = serializer.validated_data['latencia_cliente']
            if sesion.latencia_promedio == 0:
                sesion.latencia_promedio = latencia_nueva
            else:
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
    """Endpoint para cerrar una sesión RA"""
    session_token = request.data.get('session_token')
    
    if not session_token:
        return Response(
            {'error': 'session_token es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        sesion = SesionRA.objects.get(session_token=session_token)
        
        EventoRA.objects.create(
            sesion=sesion,
            tipo='desconexion',
            descripcion='Desconexión solicitada por el cliente',
            datos_adicionales={
                'duracion_segundos': (timezone.now() - sesion.fecha_inicio).total_seconds()
            }
        )
        
        sesion.finalizar()
        
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
    """Endpoint para registrar eventos desde Unreal Engine"""
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
    """ViewSet para gestionar sesiones RA desde el panel web"""
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
    """ViewSet para gestionar configuraciones RA"""
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
    """ViewSet para ver eventos RA (solo lectura)"""
    queryset = EventoRA.objects.select_related('sesion').all()
    serializer_class = EventoRASerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = EventoRA.objects.all()
        sesion_id = self.request.query_params.get('sesion_id')
        
        if sesion_id:
            queryset = queryset.filter(sesion_id=sesion_id)
        
        return queryset.order_by('-timestamp')

    def dashboard_view(request):
    return render(request, 'dashboard.html')