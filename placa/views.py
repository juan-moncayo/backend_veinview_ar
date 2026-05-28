# placa/views.py
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import logging

from .models import DispositivoESP32, PracticaActiva, DatosSensor
from .serializers import (
    DispositivoESP32Serializer,
    PracticaActivaSerializer,
    DatosSensorSerializer,
    DatosSensorCreateSerializer
)
from estudiantes.models import Estudiante

logger = logging.getLogger('placa')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def verificar_api_key(request):
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')

    if not api_key:
        return None, Response(
            {'error': 'API Key no proporcionada. Use header X-API-Key o parámetro api_key'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        dispositivo = DispositivoESP32.objects.get(api_key=api_key, activo=True)
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
    mac_address = request.data.get('mac_address', '').upper()
    nombre = request.data.get('nombre', 'VeinView Device')

    if not mac_address:
        return Response(
            {'error': 'mac_address es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )

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
    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        return error_response

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
            'message': 'No hay prácticas activas.'
        })


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def enviar_datos_sensores(request):
    logger.info("=" * 80)
    logger.info("🔵 RECIBIENDO DATOS DE SENSORES")
    logger.info(f"📥 IP Cliente: {get_client_ip(request)}")

    dispositivo, error_response = verificar_api_key(request)
    if error_response:
        logger.error(f"❌ Error en API Key")
        return error_response

    logger.info(f"✅ Dispositivo: {dispositivo.nombre}")

    practica_activa = PracticaActiva.objects.filter(
        dispositivo=dispositivo,
        estado='iniciada'
    ).first()

    if not practica_activa:
        logger.warning(f"⚠️ No hay práctica activa para {dispositivo.nombre}")
        return Response({
            'error': 'No hay práctica activa o está pausada',
            'puede_enviar_datos': False
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer = DatosSensorCreateSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"❌ Datos inválidos: {serializer.errors}")
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

        logger.info(f"✅ Dato #{dato_sensor.id} guardado — "
                    f"Pitch:{dato_sensor.angulo_pitch:.1f}° "
                    f"Fuerza:{dato_sensor.fuerza:.1f}g "
                    f"Técnica:{dato_sensor.tecnica_correcta} "
                    f"Total:{total_datos}")

        return Response({
            'status': 'ok',
            'message': 'Datos guardados exitosamente',
            'dato_id': dato_sensor.id,
            'practica_id': practica_activa.id,
            'estudiante': practica_activa.estudiante.nombre_completo,
            'tecnica_correcta': dato_sensor.tecnica_correcta,
            'total_datos_practica': total_datos
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"❌ Error guardando dato: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Error al guardar datos',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            'mac': dispositivo.mac_address,
            'activo': dispositivo.activo
        },
        'practica_activa': practica_activa is not None,
        'practica': PracticaActivaSerializer(practica_activa).data if practica_activa else None,
        'total_datos_capturados': total_datos,
        'timestamp': timezone.now().isoformat()
    })


# ============================================
# VIEWSETS PARA GESTIÓN WEB
# ============================================

class DispositivoESP32ViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DispositivoESP32.objects.all()
    serializer_class = DispositivoESP32Serializer
    permission_classes = [AllowAny]


class PracticaActivaViewSet(viewsets.ModelViewSet):
    queryset = PracticaActiva.objects.select_related('estudiante', 'dispositivo').all()
    serializer_class = PracticaActivaSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        estudiante_id = request.data.get('estudiante_id')
        dispositivo_id = request.data.get('dispositivo_id')

        if not estudiante_id or not dispositivo_id:
            return Response(
                {'error': 'estudiante_id y dispositivo_id son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            estudiante = Estudiante.objects.get(id=estudiante_id)
        except Estudiante.DoesNotExist:
            return Response(
                {'error': 'Estudiante no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            dispositivo = DispositivoESP32.objects.get(id=dispositivo_id)
        except DispositivoESP32.DoesNotExist:
            return Response(
                {'error': 'Dispositivo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        practica = PracticaActiva.objects.create(
            estudiante=estudiante,
            dispositivo=dispositivo,
            estado='iniciada'
        )

        logger.info(f"✅ Práctica #{practica.id} creada — "
                    f"Estudiante: {estudiante.nombre_completo}")

        return Response(
            self.get_serializer(practica).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        practica = self.get_object()
        nuevo_estado = request.data.get('estado')

        if nuevo_estado not in ['iniciada', 'pausada', 'finalizada']:
            return Response(
                {'error': 'Estado inválido. Use: iniciada, pausada o finalizada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        estado_anterior = practica.estado

        if nuevo_estado == 'pausada' and practica.estado == 'iniciada':
            practica.pausar()

        elif nuevo_estado == 'iniciada' and practica.estado == 'pausada':
            practica.reanudar()

        elif nuevo_estado == 'finalizada':
            practica.finalizar()
            # Generar resumen automáticamente al finalizar
            self._generar_resumen_automatico(practica, request)

        else:
            practica.estado = nuevo_estado
            practica.save()

        logger.info(
            f"🔄 Práctica #{practica.id}: {estado_anterior} → {nuevo_estado}"
        )

        return Response(self.get_serializer(practica).data)

    def _generar_resumen_automatico(self, practica, request):
        """Genera o recalcula el resumen automáticamente al finalizar una práctica."""
        from profesor.models import ResumenPractica, Profesor

        try:
            profesor = None
            if request.user.is_authenticated:
                try:
                    profesor = Profesor.objects.get(user=request.user)
                except Profesor.DoesNotExist:
                    pass

            # Si ya tiene resumen, recalcular con los rangos actuales
            if hasattr(practica, 'resumen'):
                resumen = practica.resumen
                resumen.calcular_estadisticas()
                resumen.calcular_calificacion_automatica()
                logger.info(
                    f"✅ Resumen recalculado — Práctica #{practica.id} "
                    f"— {resumen.precision_porcentaje:.1f}% "
                    f"— {resumen.calificacion}/5"
                )
            else:
                resumen = ResumenPractica.objects.create(
                    practica=practica,
                    profesor=profesor,
                    observaciones=''
                )
                resumen.calcular_estadisticas()
                resumen.calcular_calificacion_automatica()
                logger.info(
                    f"✅ Resumen creado — Práctica #{practica.id} "
                    f"— {resumen.precision_porcentaje:.1f}% "
                    f"— {resumen.calificacion}/5"
                )

        except Exception as e:
            logger.error(
                f"❌ Error generando resumen para práctica #{practica.id}: {str(e)}"
            )


class DatosSensorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DatosSensor.objects.all()
    serializer_class = DatosSensorSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = DatosSensor.objects.select_related(
            'practica', 'dispositivo'
        ).all()

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