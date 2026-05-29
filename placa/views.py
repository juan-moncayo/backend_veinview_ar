from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import logging

from .models import DispositivoESP32, PracticaActiva, DatosSensor
from .serializers import (
    DispositivoESP32Serializer,
    PracticaActivaSerializer,
    DatosSensorSerializer,
    DatosSensorCreateSerializer,
)
from estudiantes.models import Estudiante

logger = logging.getLogger('placa')

INACTIVIDAD_MINUTOS = 5
UMBRAL_RUIDO_GRAMOS = 20.0


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def verificar_api_key(request):
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    if not api_key:
        return None, Response(
            {'error': 'API Key no proporcionada'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    try:
        dispositivo = DispositivoESP32.objects.get(api_key=api_key, activo=True)
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.ip_address      = get_client_ip(request)
        dispositivo.save(update_fields=['ultima_conexion', 'ip_address'])
        return dispositivo, None
    except DispositivoESP32.DoesNotExist:
        return None, Response(
            {'error': 'API Key inválida o dispositivo inactivo'},
            status=status.HTTP_401_UNAUTHORIZED
        )


def _finalizar_por_inactividad(practica):
    """Finaliza la práctica y genera resumen si es de prueba."""
    practica.finalizar()
    logger.info(
        f"⏱️ Práctica #{practica.id} ({practica.tipo}) finalizada por inactividad"
    )
    if practica.tipo == 'prueba':
        try:
            from profesor.models import ResumenPractica
            if not hasattr(practica, 'resumen'):
                resumen = ResumenPractica.objects.create(
                    practica=practica,
                    observaciones='Finalizada automáticamente por inactividad'
                )
                resumen.calcular_estadisticas()
                resumen.calcular_calificacion_automatica()
        except Exception as e:
            logger.error(f"Error generando resumen por inactividad: {e}")


# ============================================================
# ENDPOINT PRINCIPAL — PRÁCTICA DE PRUEBA (ESTUDIANTE / RA)
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def iniciar_practica_prueba(request):
    """
    Inicia una práctica de prueba para el estudiante autenticado.
    Usada desde: dashboard del estudiante y desde RA.

    Validaciones:
    - No puede haber una práctica de examen activa del mismo estudiante.
    - No puede haber una práctica de prueba activa del mismo estudiante.
    - No puede haber una práctica de examen activa en el mismo dispositivo.

    Body: { "dispositivo_id": 1 }   ← opcional, usa el primero disponible si no se envía
    """
    try:
        estudiante = Estudiante.objects.get(user=request.user)
    except Estudiante.DoesNotExist:
        return Response(
            {'error': 'El usuario no tiene perfil de estudiante'},
            status=status.HTTP_403_FORBIDDEN
        )

    # ── 1. Verificar que no haya práctica activa del estudiante ──────────
    practica_activa_estudiante = PracticaActiva.objects.filter(
        estudiante=estudiante,
        estado__in=['iniciada', 'pausada']
    ).first()

    if practica_activa_estudiante:
        if practica_activa_estudiante.tipo == 'examen':
            return Response({
                'error': 'Tienes una práctica de examen activa en este momento. '
                         'El profesor debe finalizarla antes de iniciar una prueba.',
                'practica_activa': PracticaActivaSerializer(practica_activa_estudiante).data,
            }, status=status.HTTP_409_CONFLICT)
        else:
            return Response({
                'error': 'Ya tienes una práctica de prueba activa.',
                'practica_activa': PracticaActivaSerializer(practica_activa_estudiante).data,
            }, status=status.HTTP_409_CONFLICT)

    # ── 2. Obtener dispositivo ───────────────────────────────────────────
    dispositivo_id = request.data.get('dispositivo_id')

    if dispositivo_id:
        try:
            dispositivo = DispositivoESP32.objects.get(id=dispositivo_id, activo=True)
        except DispositivoESP32.DoesNotExist:
            return Response(
                {'error': 'Dispositivo no encontrado o inactivo'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        dispositivo = DispositivoESP32.objects.filter(activo=True).first()
        if not dispositivo:
            return Response(
                {'error': 'No hay dispositivos disponibles'},
                status=status.HTTP_404_NOT_FOUND
            )

    # ── 3. Verificar que no haya examen activo en ese dispositivo ────────
    examen_activo_dispositivo = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado__in=['iniciada', 'pausada'],
        tipo='examen'
    ).first()

    if examen_activo_dispositivo:
        return Response({
            'error': 'El dispositivo está siendo usado en una práctica de examen. '
                     'Espera a que el profesor la finalice.',
            'practica_activa': PracticaActivaSerializer(examen_activo_dispositivo).data,
        }, status=status.HTTP_409_CONFLICT)

    # ── 4. Finalizar cualquier práctica de prueba huérfana en ese dispositivo
    PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado__in=['iniciada', 'pausada'],
        tipo='prueba'
    ).exclude(estudiante=estudiante).update(
        estado='finalizada',
        fecha_fin=timezone.now()
    )

    # ── 5. Crear práctica de prueba ──────────────────────────────────────
    practica = PracticaActiva.objects.create(
        estudiante=estudiante,
        dispositivo=dispositivo,
        estado='iniciada',
        tipo='prueba',
    )

    logger.info(
        f"✅ Práctica de prueba #{practica.id} iniciada — "
        f"Estudiante: {estudiante.nombre_completo}"
    )

    return Response({
        'status':   'ok',
        'message':  'Práctica de prueba iniciada',
        'practica': PracticaActivaSerializer(practica).data,
        'inactividad_minutos': INACTIVIDAD_MINUTOS,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def finalizar_practica_prueba(request):
    """
    Finaliza la práctica de prueba activa del estudiante.
    Usada desde: dashboard del estudiante, RA y por inactividad.

    Body: { "practica_id": 1 }
    """
    try:
        estudiante = Estudiante.objects.get(user=request.user)
    except Estudiante.DoesNotExist:
        return Response(
            {'error': 'El usuario no tiene perfil de estudiante'},
            status=status.HTTP_403_FORBIDDEN
        )

    practica_id = request.data.get('practica_id')

    if practica_id:
        try:
            practica = PracticaActiva.objects.get(
                id=practica_id,
                estudiante=estudiante,
                tipo='prueba'
            )
        except PracticaActiva.DoesNotExist:
            return Response(
                {'error': 'Práctica no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        practica = PracticaActiva.objects.filter(
            estudiante=estudiante,
            tipo='prueba',
            estado__in=['iniciada', 'pausada']
        ).first()

        if not practica:
            return Response(
                {'error': 'No tienes una práctica de prueba activa'},
                status=status.HTTP_404_NOT_FOUND
            )

    practica.finalizar()

    # Generar resumen automático
    try:
        from profesor.models import ResumenPractica
        if not hasattr(practica, 'resumen'):
            resumen = ResumenPractica.objects.create(
                practica=practica,
                observaciones='Práctica de prueba finalizada por el estudiante'
            )
            resumen.calcular_estadisticas()
            resumen.calcular_calificacion_automatica()
    except Exception as e:
        logger.error(f"Error generando resumen: {e}")

    return Response({
        'status':   'ok',
        'message':  'Práctica de prueba finalizada',
        'practica': PracticaActivaSerializer(practica).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estado_practica_estudiante(request):
    """
    Retorna el estado actual de la práctica del estudiante autenticado.
    También verifica inactividad y la finaliza si corresponde.
    Usada por el dashboard del estudiante y RA para polling.

    GET /api/placa/mi-practica/
    """
    try:
        estudiante = Estudiante.objects.get(user=request.user)
    except Estudiante.DoesNotExist:
        return Response(
            {'error': 'El usuario no tiene perfil de estudiante'},
            status=status.HTTP_403_FORBIDDEN
        )

    practica = PracticaActiva.objects.filter(
        estudiante=estudiante,
        estado__in=['iniciada', 'pausada']
    ).first()

    if not practica:
        return Response({
            'practica_activa': False,
            'practica':        None,
        })

    # Verificar inactividad solo en prácticas de prueba
    if practica.tipo == 'prueba' and practica.verificar_inactividad():
        _finalizar_por_inactividad(practica)
        return Response({
            'practica_activa': False,
            'practica':        PracticaActivaSerializer(practica).data,
            'mensaje':         'La práctica fue finalizada por inactividad (5 minutos sin movimiento)',
            'finalizada_por_inactividad': True,
        })

    # Calcular tiempo hasta inactividad
    segundos_inactividad = None
    if practica.tipo == 'prueba':
        referencia = practica.ultima_actividad_sensor or practica.fecha_inicio
        transcurrido = (timezone.now() - referencia).total_seconds()
        segundos_inactividad = max(0, INACTIVIDAD_MINUTOS * 60 - int(transcurrido))

    return Response({
        'practica_activa':      True,
        'practica':             PracticaActivaSerializer(practica).data,
        'segundos_inactividad': segundos_inactividad,
        'puede_enviar_datos':   practica.estado == 'iniciada',
    })


# ============================================================
# ENDPOINTS ESP32 (sin cambios)
# ============================================================

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def registrar_dispositivo(request):
    mac_address = request.data.get('mac_address', '').upper()
    nombre      = request.data.get('nombre', 'VeinView Device')

    if not mac_address:
        return Response(
            {'error': 'mac_address es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    dispositivo, created = DispositivoESP32.objects.get_or_create(
        mac_address=mac_address,
        defaults={'nombre': nombre, 'ip_address': get_client_ip(request)}
    )

    return Response({
        'message':    'Dispositivo registrado' if created else 'Dispositivo ya existe',
        'dispositivo': DispositivoESP32Serializer(dispositivo).data,
        'api_key':    dispositivo.api_key
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def verificar_conexion(request):
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response
    return Response({
        'status':      'ok',
        'dispositivo': dispositivo.nombre,
        'timestamp':   timezone.now().isoformat()
    })


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def obtener_practica_activa(request):
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response

    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante').first()

    if practica_activa:
        # Verificar inactividad en prácticas de prueba
        if practica_activa.tipo == 'prueba' and practica_activa.verificar_inactividad():
            _finalizar_por_inactividad(practica_activa)
            return Response({
                'practica_activa':  False,
                'practica':         None,
                'puede_enviar_datos': False,
                'message': 'Práctica finalizada por inactividad'
            })

        return Response({
            'practica_activa':    True,
            'practica':           PracticaActivaSerializer(practica_activa).data,
            'puede_enviar_datos': practica_activa.estado == 'iniciada',
        })

    return Response({
        'practica_activa':    False,
        'practica':           None,
        'puede_enviar_datos': False,
        'message':            'No hay prácticas activas.'
    })


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def enviar_datos_sensores(request):
    logger.info("🔵 RECIBIENDO DATOS DE SENSORES")

    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response

    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado='iniciada'
    ).first()

    if not practica_activa:
        return Response({
            'error': 'No hay práctica activa o está pausada',
            'puede_enviar_datos': False
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verificar inactividad antes de aceptar datos
    if practica_activa.tipo == 'prueba' and practica_activa.verificar_inactividad():
        _finalizar_por_inactividad(practica_activa)
        return Response({
            'error': 'Práctica finalizada por inactividad',
            'puede_enviar_datos': False
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer = DatosSensorCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Datos inválidos',
            'detalles': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    datos = serializer.validated_data

    try:
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

        total_datos = DatosSensor.objects.filter(practica=practica_activa).count()

        logger.info(
            f"✅ Dato #{dato_sensor.id} — "
            f"Pitch:{dato_sensor.angulo_pitch:.1f}° "
            f"Fuerza:{dato_sensor.fuerza:.1f}g "
            f"Técnica:{dato_sensor.tecnica_correcta} "
            f"Tipo:{practica_activa.tipo}"
        )

        return Response({
            'status':               'ok',
            'dato_id':              dato_sensor.id,
            'practica_id':          practica_activa.id,
            'tipo':                 practica_activa.tipo,
            'tecnica_correcta':     dato_sensor.tecnica_correcta,
            'total_datos_practica': total_datos,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"❌ Error guardando dato: {str(e)}")
        return Response(
            {'error': 'Error al guardar datos', 'detalle': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def estado_sistema(request):
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response

    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante').first()

    total_datos = DatosSensor.objects.filter(
        practica=practica_activa
    ).count() if practica_activa else 0

    return Response({
        'dispositivo': {
            'nombre': dispositivo.nombre,
            'mac':    dispositivo.mac_address,
            'activo': dispositivo.activo
        },
        'practica_activa':      practica_activa is not None,
        'practica':             PracticaActivaSerializer(practica_activa).data if practica_activa else None,
        'total_datos_capturados': total_datos,
        'timestamp':            timezone.now().isoformat()
    })


# ============================================================
# VIEWSETS
# ============================================================

class DispositivoESP32ViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = DispositivoESP32.objects.all()
    serializer_class   = DispositivoESP32Serializer
    permission_classes = [AllowAny]


class PracticaActivaViewSet(viewsets.ModelViewSet):
    queryset = PracticaActiva.objects.select_related(
        'estudiante', 'dispositivo'
    ).all()
    serializer_class   = PracticaActivaSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset      = super().get_queryset()
        estudiante_id = self.request.query_params.get('estudiante')
        if estudiante_id:
            queryset = queryset.filter(estudiante_id=estudiante_id)
        return queryset

    def create(self, request, *args, **kwargs):
        estudiante_id  = request.data.get('estudiante_id')
        dispositivo_id = request.data.get('dispositivo_id')

        if not estudiante_id or not dispositivo_id:
            return Response(
                {'error': 'estudiante_id y dispositivo_id son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            estudiante = Estudiante.objects.get(id=estudiante_id)
        except Estudiante.DoesNotExist:
            return Response({'error': 'Estudiante no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        try:
            dispositivo = DispositivoESP32.objects.get(id=dispositivo_id)
        except DispositivoESP32.DoesNotExist:
            return Response({'error': 'Dispositivo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        practica = PracticaActiva.objects.create(
            estudiante=estudiante,
            dispositivo=dispositivo,
            estado='iniciada',
            tipo='examen',
        )

        logger.info(f"✅ Práctica de examen #{practica.id} creada — {estudiante.nombre_completo}")

        return Response(
            self.get_serializer(practica).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        practica      = self.get_object()
        nuevo_estado  = request.data.get('estado')

        if nuevo_estado not in ['iniciada', 'pausada', 'finalizada']:
            return Response(
                {'error': 'Estado inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        estado_anterior = practica.estado

        if nuevo_estado == 'pausada' and practica.estado == 'iniciada':
            practica.pausar()
        elif nuevo_estado == 'iniciada' and practica.estado == 'pausada':
            practica.reanudar()
        elif nuevo_estado == 'finalizada':
            practica.finalizar()
            self._generar_resumen_automatico(practica, request)
        else:
            practica.estado = nuevo_estado
            practica.save()

        logger.info(f"🔄 Práctica #{practica.id}: {estado_anterior} → {nuevo_estado}")

        return Response(self.get_serializer(practica).data)

    def _generar_resumen_automatico(self, practica, request):
        from profesor.models import ResumenPractica, Profesor
        try:
            profesor = None
            if request.user.is_authenticated:
                try:
                    profesor = Profesor.objects.get(user=request.user)
                except Profesor.DoesNotExist:
                    pass

            if hasattr(practica, 'resumen'):
                practica.resumen.calcular_estadisticas()
                practica.resumen.calcular_calificacion_automatica()
            else:
                resumen = ResumenPractica.objects.create(
                    practica=practica,
                    profesor=profesor,
                    observaciones=''
                )
                resumen.calcular_estadisticas()
                resumen.calcular_calificacion_automatica()
        except Exception as e:
            logger.error(f"❌ Error generando resumen: {e}")


class DatosSensorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = DatosSensor.objects.all()
    serializer_class   = DatosSensorSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset    = DatosSensor.objects.select_related('practica', 'dispositivo').all()
        practica_id = self.request.query_params.get('practica')
        if practica_id:
            queryset = queryset.filter(practica_id=practica_id)
        queryset = queryset.order_by('-timestamp')
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                queryset = queryset[:int(limit)]
            except ValueError:
                pass
        return queryset