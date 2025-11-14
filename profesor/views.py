from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Count, Q, Max, Min
from datetime import timedelta

from .models import ResumenPractica, EncuestaSistema, ReporteGeneral
from .serializers import (
    ResumenPracticaSerializer,
    ResumenPracticaCreateSerializer,
    EncuestaSistemaSerializer,
    EncuestaSistemaCreateSerializer,
    ReporteGeneralSerializer,
    ReporteGeneralCreateSerializer,
    EstadisticasEstudianteSerializer,
    MetricasTiempoRealSerializer,
    DashboardProfesorSerializer
)
from placa.models import PracticaActiva, DatosSensor, DispositivoESP32
from estudiantes.models import Estudiante


class ResumenPracticaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar resúmenes de prácticas
    GET /api/profesor/resumenes/ - Listar todos los resúmenes
    POST /api/profesor/resumenes/ - Crear resumen (calcula automáticamente)
    GET /api/profesor/resumenes/{id}/ - Ver detalle
    PATCH /api/profesor/resumenes/{id}/ - Actualizar calificación/observaciones
    """
    queryset = ResumenPractica.objects.select_related(
        'practica__estudiante', 'profesor'
    ).all()
    serializer_class = ResumenPracticaSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ResumenPracticaCreateSerializer
        return ResumenPracticaSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear resumen con cálculo automático de estadísticas"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        practica_id = serializer.validated_data['practica_id']
        practica = PracticaActiva.objects.get(id=practica_id)
        
        # Crear resumen
        resumen = ResumenPractica.objects.create(
            practica=practica,
            profesor=request.user if request.user.is_authenticated else None,
            observaciones=serializer.validated_data.get('observaciones', '')
        )
        
        # Calcular estadísticas automáticamente
        if serializer.validated_data.get('calcular_automatico', True):
            resumen.calcular_estadisticas()
            resumen.calcular_calificacion_automatica()
        
        return Response(
            ResumenPracticaSerializer(resumen).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def recalcular(self, request, pk=None):
        """Recalcular estadísticas de un resumen"""
        resumen = self.get_object()
        resumen.calcular_estadisticas()
        resumen.calcular_calificacion_automatica()
        
        return Response({
            'message': 'Estadísticas recalculadas exitosamente',
            'resumen': ResumenPracticaSerializer(resumen).data
        })
    
    @action(detail=False, methods=['get'])
    def por_estudiante(self, request):
        """Obtener resúmenes filtrados por estudiante"""
        estudiante_id = request.query_params.get('estudiante_id')
        
        if not estudiante_id:
            return Response(
                {'error': 'estudiante_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resumenes = self.queryset.filter(
            practica__estudiante_id=estudiante_id
        ).order_by('-fecha_evaluacion')
        
        serializer = self.get_serializer(resumenes, many=True)
        return Response(serializer.data)


class EncuestaSistemaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para encuestas del sistema
    GET /api/profesor/encuestas/ - Listar todas las encuestas
    POST /api/profesor/encuestas/ - Crear nueva encuesta
    GET /api/profesor/encuestas/{id}/ - Ver detalle
    GET /api/profesor/encuestas/estadisticas/ - Estadísticas de encuestas
    """
    queryset = EncuestaSistema.objects.select_related('estudiante', 'practica').all()
    serializer_class = EncuestaSistemaSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EncuestaSistemaCreateSerializer
        return EncuestaSistemaSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear nueva encuesta"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        estudiante = Estudiante.objects.get(id=data['estudiante_id'])
        practica = None
        if data.get('practica_id'):
            practica = PracticaActiva.objects.get(id=data['practica_id'])
        
        # Obtener IP
        ip_address = self.get_client_ip(request)
        
        # Crear encuesta
        encuesta = EncuestaSistema.objects.create(
            estudiante=estudiante,
            practica=practica,
            facilidad_uso=data['facilidad_uso'],
            utilidad_sistema=data['utilidad_sistema'],
            precision_sensores=data['precision_sensores'],
            interfaz_clara=data['interfaz_clara'],
            mejora_aprendizaje=data['mejora_aprendizaje'],
            aspectos_positivos=data.get('aspectos_positivos', ''),
            aspectos_negativos=data.get('aspectos_negativos', ''),
            sugerencias=data.get('sugerencias', ''),
            recomendaria=data.get('recomendaria', True),
            ip_address=ip_address
        )
        
        return Response(
            EncuestaSistemaSerializer(encuesta).data,
            status=status.HTTP_201_CREATED
        )
    
    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas generales de encuestas"""
        encuestas = self.queryset.all()
        
        if not encuestas.exists():
            return Response({
                'total_encuestas': 0,
                'mensaje': 'No hay encuestas disponibles'
            })
        
        # Calcular promedios
        stats = encuestas.aggregate(
            avg_facilidad=Avg('facilidad_uso'),
            avg_utilidad=Avg('utilidad_sistema'),
            avg_precision=Avg('precision_sensores'),
            avg_interfaz=Avg('interfaz_clara'),
            avg_aprendizaje=Avg('mejora_aprendizaje')
        )
        
        # Calcular puntuación promedio general
        puntuacion_promedio = sum(stats.values()) / len(stats)
        
        # Contar recomendaciones
        total_encuestas = encuestas.count()
        recomendaciones = encuestas.filter(recomendaria=True).count()
        porcentaje_recomendacion = (recomendaciones / total_encuestas * 100) if total_encuestas > 0 else 0
        
        return Response({
            'total_encuestas': total_encuestas,
            'promedios': {
                'facilidad_uso': round(stats['avg_facilidad'], 2),
                'utilidad_sistema': round(stats['avg_utilidad'], 2),
                'precision_sensores': round(stats['avg_precision'], 2),
                'interfaz_clara': round(stats['avg_interfaz'], 2),
                'mejora_aprendizaje': round(stats['avg_aprendizaje'], 2),
                'general': round(puntuacion_promedio, 2)
            },
            'recomendaciones': {
                'total': recomendaciones,
                'porcentaje': round(porcentaje_recomendacion, 2)
            }
        })
    
    @action(detail=False, methods=['get'])
    def recientes(self, request):
        """Obtener encuestas recientes (últimos 30 días)"""
        fecha_limite = timezone.now() - timedelta(days=30)
        encuestas = self.queryset.filter(fecha_respuesta__gte=fecha_limite)
        serializer = self.get_serializer(encuestas, many=True)
        return Response(serializer.data)


class ReporteGeneralViewSet(viewsets.ModelViewSet):
    """
    ViewSet para reportes generales del sistema
    GET /api/profesor/reportes/ - Listar reportes
    POST /api/profesor/reportes/ - Generar nuevo reporte
    GET /api/profesor/reportes/{id}/ - Ver detalle de reporte
    """
    queryset = ReporteGeneral.objects.select_related('generado_por').all()
    serializer_class = ReporteGeneralSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReporteGeneralCreateSerializer
        return ReporteGeneralSerializer
    
    def create(self, request, *args, **kwargs):
        """Generar nuevo reporte con estadísticas"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Crear reporte
        reporte = ReporteGeneral.objects.create(
            titulo=serializer.validated_data.get('titulo', 'Reporte de Desempeño'),
            fecha_inicio=serializer.validated_data['fecha_inicio'],
            fecha_fin=serializer.validated_data['fecha_fin'],
            generado_por=request.user if request.user.is_authenticated else None
        )
        
        # Generar estadísticas
        reporte.generar_estadisticas()
        
        return Response(
            ReporteGeneralSerializer(reporte).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def regenerar(self, request, pk=None):
        """Regenerar estadísticas de un reporte existente"""
        reporte = self.get_object()
        reporte.generar_estadisticas()
        
        return Response({
            'message': 'Reporte regenerado exitosamente',
            'reporte': ReporteGeneralSerializer(reporte).data
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def estadisticas_estudiante(request):
    """
    Obtener estadísticas completas de un estudiante específico
    GET /api/profesor/estadisticas-estudiante/?estudiante_id=1
    """
    estudiante_id = request.query_params.get('estudiante_id')
    
    if not estudiante_id:
        return Response(
            {'error': 'estudiante_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        estudiante = Estudiante.objects.get(id=estudiante_id)
    except Estudiante.DoesNotExist:
        return Response(
            {'error': 'Estudiante no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Obtener todas las prácticas del estudiante
    practicas = PracticaActiva.objects.filter(estudiante=estudiante)
    practicas_finalizadas = practicas.filter(estado='finalizada')
    
    if not practicas_finalizadas.exists():
        return Response({
            'estudiante_id': estudiante.id,
            'estudiante_nombre': estudiante.nombre_completo,
            'estudiante_codigo': estudiante.codigo_estudiante,
            'total_practicas': 0,
            'mensaje': 'Este estudiante no tiene prácticas finalizadas'
        })
    
    # Calcular estadísticas
    stats = practicas_finalizadas.aggregate(
        avg_precision=Avg('precision_promedio'),
        avg_intentos=Avg('numero_intentos'),
        avg_tiempo=Avg('duracion_total_segundos')
    )
    
    # Promedio de calificaciones
    resumenes = ResumenPractica.objects.filter(
        practica__in=practicas_finalizadas,
        calificacion__isnull=False
    )
    promedio_calificacion = resumenes.aggregate(
        avg_cal=Avg('calificacion')
    )['avg_cal'] or 0.0
    
    # Mejor práctica
    mejor_practica = practicas_finalizadas.order_by('-precision_promedio').first()
    mejor_practica_data = {
        'id': mejor_practica.id,
        'fecha': mejor_practica.fecha_inicio.strftime('%Y-%m-%d %H:%M'),
        'precision': mejor_practica.precision_promedio,
        'intentos': mejor_practica.numero_intentos
    }
    
    # Última práctica
    ultima_practica = practicas_finalizadas.order_by('-fecha_inicio').first()
    ultima_practica_data = {
        'id': ultima_practica.id,
        'fecha': ultima_practica.fecha_inicio.strftime('%Y-%m-%d %H:%M'),
        'precision': ultima_practica.precision_promedio,
        'intentos': ultima_practica.numero_intentos
    }
    
    data = {
        'estudiante_id': estudiante.id,
        'estudiante_nombre': estudiante.nombre_completo,
        'estudiante_codigo': estudiante.codigo_estudiante,
        'total_practicas': practicas.count(),
        'practicas_finalizadas': practicas_finalizadas.count(),
        'promedio_precision': round(stats['avg_precision'] or 0, 2),
        'promedio_intentos': round(stats['avg_intentos'] or 0, 2),
        'promedio_tiempo_minutos': round((stats['avg_tiempo'] or 0) / 60, 2),
        'promedio_calificacion': round(promedio_calificacion, 2),
        'mejor_practica': mejor_practica_data,
        'ultima_practica': ultima_practica_data
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def metricas_tiempo_real(request):
    """
    Obtener métricas en tiempo real de una práctica activa
    GET /api/profesor/metricas-tiempo-real/?practica_id=1
    """
    practica_id = request.query_params.get('practica_id')
    
    if not practica_id:
        return Response(
            {'error': 'practica_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        practica = PracticaActiva.objects.select_related('estudiante').get(id=practica_id)
    except PracticaActiva.DoesNotExist:
        return Response(
            {'error': 'Práctica no encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    
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
    
    # Últimos 10 datos
    ultimos_datos = DatosSensor.objects.filter(
        practica=practica
    ).order_by('-timestamp')[:10].values(
        'angulo_pitch', 'angulo_roll', 'fuerza', 'timestamp'
    )
    
    # Datos más recientes
    ultimo_dato = ultimos_datos.first() if ultimos_datos else None
    
    data = {
        'practica_id': practica.id,
        'estudiante_nombre': practica.estudiante.nombre_completo,
        'estado': practica.estado,
        'tiempo_transcurrido': tiempo_transcurrido,
        'numero_intentos': practica.numero_intentos,
        'precision_actual': round(precision_actual, 2),
        'ultimos_datos': list(ultimos_datos),
        'angulo_actual': ultimo_dato['angulo_pitch'] if ultimo_dato else 0,
        'fuerza_actual': ultimo_dato['fuerza'] if ultimo_dato else 0
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_profesor(request):
    """
    Dashboard completo para el profesor con todas las métricas
    GET /api/profesor/dashboard/
    """
    hoy = timezone.now().date()
    inicio_dia = timezone.make_aware(timezone.datetime.combine(hoy, timezone.datetime.min.time()))
    fin_dia = timezone.make_aware(timezone.datetime.combine(hoy, timezone.datetime.max.time()))
    
    # Estadísticas del día
    practicas_hoy = PracticaActiva.objects.filter(
        fecha_inicio__range=[inicio_dia, fin_dia]
    )
    
    practicas_activas = PracticaActiva.objects.filter(
        estado__in=['iniciada', 'pausada']
    ).select_related('estudiante', 'dispositivo')
    
    practicas_finalizadas_hoy = practicas_hoy.filter(estado='finalizada')
    
    # Promedios del día
    promedio_precision_hoy = practicas_finalizadas_hoy.aggregate(
        avg=Avg('precision_promedio')
    )['avg'] or 0.0
    
    resumenes_hoy = ResumenPractica.objects.filter(
        practica__in=practicas_finalizadas_hoy,
        calificacion__isnull=False
    )
    promedio_calificacion_hoy = resumenes_hoy.aggregate(
        avg=Avg('calificacion')
    )['avg'] or 0.0
    
    # Prácticas activas
    practicas_activas_data = []
    for practica in practicas_activas:
        practicas_activas_data.append({
            'id': practica.id,
            'estudiante': practica.estudiante.nombre_completo,
            'estado': practica.estado,
            'tiempo_transcurrido': practica.duracion_total_segundos,
            'dispositivo': practica.dispositivo.nombre
        })
    
    # Últimas prácticas finalizadas
    ultimas_finalizadas = PracticaActiva.objects.filter(
        estado='finalizada'
    ).select_related('estudiante').order_by('-fecha_fin')[:5]
    
    ultimas_finalizadas_data = []
    for practica in ultimas_finalizadas:
        resumen = ResumenPractica.objects.filter(practica=practica).first()
        ultimas_finalizadas_data.append({
            'id': practica.id,
            'estudiante': practica.estudiante.nombre_completo,
            'fecha': practica.fecha_fin.strftime('%Y-%m-%d %H:%M'),
            'precision': practica.precision_promedio,
            'calificacion': resumen.calificacion if resumen else None
        })
    
    # Estudiantes con mejor desempeño (últimos 7 días)
    hace_7_dias = timezone.now() - timedelta(days=7)
    mejores_estudiantes = PracticaActiva.objects.filter(
        fecha_inicio__gte=hace_7_dias,
        estado='finalizada'
    ).values(
        'estudiante__id',
        'estudiante__nombre_completo'
    ).annotate(
        avg_precision=Avg('precision_promedio')
    ).order_by('-avg_precision')[:5]
    
    mejores_estudiantes_data = [
        {
            'id': e['estudiante__id'],
            'nombre': e['estudiante__nombre_completo'],
            'precision_promedio': round(e['avg_precision'], 2)
        }
        for e in mejores_estudiantes
    ]
    
    # Encuestas del mes
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    encuestas_mes = EncuestaSistema.objects.filter(fecha_respuesta__gte=inicio_mes)
    
    promedio_satisfaccion = 0.0
    if encuestas_mes.exists():
        promedio_satisfaccion = sum(e.puntuacion_promedio for e in encuestas_mes) / encuestas_mes.count()
    
    data = {
        'total_estudiantes_activos': Estudiante.objects.filter(activo=True).count(),
        'total_practicas_hoy': practicas_hoy.count(),
        'practicas_en_curso': practicas_activas.count(),
        'promedio_precision_hoy': round(promedio_precision_hoy, 2),
        'promedio_calificacion_hoy': round(promedio_calificacion_hoy, 2),
        'practicas_activas': practicas_activas_data,
        'ultimas_practicas_finalizadas': ultimas_finalizadas_data,
        'estudiantes_mejor_desempeno': mejores_estudiantes_data,
        'promedio_satisfaccion_reciente': round(promedio_satisfaccion, 2),
        'total_encuestas_mes': encuestas_mes.count()
    }
    
    return Response(data)