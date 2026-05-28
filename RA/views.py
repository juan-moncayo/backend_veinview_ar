# RA/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import render
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
    HeartbeatSerializer,
)
from placa.models import PracticaActiva, DatosSensor, DispositivoESP32
# CORREGIDO: usar funciones centralizadas de constants.py
from placa.constants import evaluar_angulo, evaluar_fuerza, RANGOS_RESPUESTA
from estudiantes.models import Estudiante


def get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def verificar_session_token(request):
    """
    Verifica el token de sesión RA desde header o query params.
    Retorna (sesion, None) o (None, Response error).
    """
    token = request.headers.get("X-Session-Token") or request.GET.get("session_token")

    if not token:
        return None, Response(
            {"error": "Session token no proporcionado. "
                      "Use header X-Session-Token o parámetro session_token"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        sesion = SesionRA.objects.select_related("estudiante", "practica").get(
            session_token=token
        )
    except SesionRA.DoesNotExist:
        return None, Response(
            {"error": "Session token inválido"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not sesion.esta_activa():
        return None, Response(
            {"error": "Sesión expirada o inactiva. "
                      "Reconectarse con /api/ra/conectar-automatico/"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Actualizar actividad sin disparar auto_now en campos no deseados
    SesionRA.objects.filter(pk=sesion.pk).update(
        fecha_ultima_actividad=timezone.now()
    )
    return sesion, None


# ── Conexión automática ───────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def conectar_automatico(request):
    """
    Detecta la práctica activa y conecta el dispositivo RA automáticamente.
    POST /api/ra/conectar-automatico/
    Body: {
        "dispositivo_ra": "Meta Quest 3",
        "device_id": "UNIQUE-DEVICE-ID",
        "modo_visualizacion": "overlay",
        "escala_modelo": 1.0,
        "opacidad": 0.8
    }
    """
    dispositivo_ra     = request.data.get("dispositivo_ra", "Meta Quest 3")
    device_id          = request.data.get("device_id", "").strip()
    modo_visualizacion = request.data.get("modo_visualizacion", "overlay")
    escala_modelo      = float(request.data.get("escala_modelo", 1.0))
    opacidad           = float(request.data.get("opacidad", 0.8))

    if not device_id:
        return Response(
            {"error": "device_id es requerido (MAC address o UUID del dispositivo)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    practica_activa = (
        PracticaActiva.objects
        .filter(estado__in=["iniciada", "pausada"])
        .select_related("estudiante", "dispositivo")
        .order_by("-fecha_inicio")
        .first()
    )

    if not practica_activa:
        return Response({
            "status":          "no_practice",
            "message":         "No hay ninguna práctica activa en este momento. "
                               "Espere a que un estudiante inicie una práctica.",
            "practica_activa": False,
            "session_token":   None,
        }, status=status.HTTP_200_OK)

    estudiante = practica_activa.estudiante

    sesion_existente = (
        SesionRA.objects
        .filter(dispositivo_ra__icontains=device_id, estado__in=["activa", "pausada"])
        .first()
    )

    if sesion_existente:
        sesion_existente.practica   = practica_activa
        sesion_existente.estudiante = estudiante
        sesion_existente.estado     = "activa"
        sesion_existente.ip_address = get_client_ip(request)
        sesion_existente.save()
        sesion  = sesion_existente
        mensaje = "Reconectado a práctica activa"
    else:
        SesionRA.objects.filter(
            dispositivo_ra__icontains=device_id,
            estado__in=["conectando", "activa", "pausada"],
        ).update(estado="desconectada", fecha_fin=timezone.now())

        sesion = SesionRA.objects.create(
            estudiante         = estudiante,
            practica           = practica_activa,
            dispositivo_ra     = f"{dispositivo_ra} ({device_id})",
            ip_address         = get_client_ip(request),
            estado             = "activa",
            modo_visualizacion = modo_visualizacion,
            escala_modelo      = escala_modelo,
            opacidad           = opacidad,
        )
        mensaje = "Conectado exitosamente a práctica activa"

        EventoRA.objects.create(
            sesion      = sesion,
            tipo        = "conexion",
            descripcion = f"Conexión automática desde {sesion.dispositivo_ra}",
            datos_adicionales = {
                "ip":           sesion.ip_address,
                "device_id":    device_id,
                "practica_id":  practica_activa.id,
                "estudiante_id": estudiante.id,
            },
        )

    config, _ = ConfiguracionRA.objects.get_or_create(
        estudiante=estudiante,
        defaults={
            "color_angulo_correcto":   "#00FF00",
            "color_angulo_incorrecto": "#FF0000",
            "color_fuerza_correcta":   "#0000FF",
        },
    )

    return Response({
        "status":          "success",
        "message":         mensaje,
        "session_token":   sesion.session_token,
        "sesion_id":       sesion.id,
        "practica_activa": True,
        "practica": {
            "id":                practica_activa.id,
            "estado":            practica_activa.estado,
            "fecha_inicio":      practica_activa.fecha_inicio.isoformat(),
            "duracion_segundos": practica_activa.duracion_total_segundos,
        },
        "estudiante": {
            "id":     estudiante.id,
            "nombre": estudiante.nombre_completo,
            "codigo": estudiante.codigo_estudiante,
        },
        "configuracion": ConfiguracionRASerializer(config).data,
        "endpoints": {
            "alertas":         "/api/ra/alertas/",
            "heartbeat":       "/api/ra/heartbeat/",
            "desconectar":     "/api/ra/desconectar/",
            "practica_actual": "/api/ra/practica-actual/",
        },
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def practica_actual(request):
    """
    Verifica qué práctica está activa actualmente.
    GET /api/ra/practica-actual/
    """
    practica = (
        PracticaActiva.objects
        .filter(estado__in=["iniciada", "pausada"])
        .select_related("estudiante")
        .order_by("-fecha_inicio")
        .first()
    )

    if not practica:
        return Response({
            "practica_activa": False,
            "practica_id":     None,
            "estudiante":      None,
            "estado":          None,
            "message":         "No hay prácticas activas en este momento",
        })

    return Response({
        "practica_activa": True,
        "practica_id":    practica.id,
        "estudiante": {
            "id":     practica.estudiante.id,
            "nombre": practica.estudiante.nombre_completo,
            "codigo": practica.estudiante.codigo_estudiante,
        },
        "estado":            practica.estado,
        "fecha_inicio":      practica.fecha_inicio.isoformat(),
        "duracion_segundos": practica.duracion_total_segundos,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def alertas_ra(request):
    """
    Alertas en tiempo real para el dispositivo RA.
    Dashboard/Unity consulta cada ~1.5s.
    GET /api/ra/alertas/?session_token=xxx

    CORREGIDO: usa evaluar_angulo() y evaluar_fuerza() de constants.py
    → mismos rangos que DatosSensor.save() y el firmware ESP32.
    """
    sesion, error = verificar_session_token(request)
    if error:
        return error

    base_sin_datos = {
        "status":           "ok",
        "timestamp":        int(time.time() * 1000),
        "alertas_activas":  False,
        "alerta_critica":   False,
        "tecnica_correcta": False,
        "fuerza": {
            "activa": False, "valor_actual": 0.0,
            "en_rango_optimo": True, "en_rango_aceptable": True,
            "mensaje": "Esperando datos",
        },
        "angulo": {
            "activa": False, "valor_actual": 0.0,
            "en_rango_optimo": True, "en_rango_aceptable": True,
            "mensaje": "Esperando datos",
        },
        "rangos": RANGOS_RESPUESTA,
    }

    if not sesion.practica or sesion.practica.estado != "iniciada":
        base_sin_datos["status"]  = "no_practice"
        base_sin_datos["message"] = "Sin práctica activa o práctica pausada"
        return Response(base_sin_datos)

    ultimo_dato = (
        DatosSensor.objects
        .filter(practica=sesion.practica)
        .order_by("-timestamp")
        .first()
    )

    if not ultimo_dato:
        return Response(base_sin_datos)

    # Evaluar con funciones centralizadas — mismos rangos que el ESP32 y la BD
    angulo_info = evaluar_angulo(ultimo_dato.angulo_pitch)
    fuerza_info = evaluar_fuerza(ultimo_dato.fuerza)

    alerta_critica  = (not angulo_info["en_rango_aceptable"]) or \
                      (not fuerza_info["en_rango_aceptable"])
    tecnica_correcta = angulo_info["en_rango_optimo"] and fuerza_info["en_rango_optimo"]
    alertas_activas  = angulo_info["activa"] or fuerza_info["activa"]

    return Response({
        "status":           "ok",
        "timestamp":        int(time.time() * 1000),
        "alertas_activas":  alertas_activas,
        "alerta_critica":   alerta_critica,
        "tecnica_correcta": tecnica_correcta,
        "fuerza":           fuerza_info,
        "angulo":           angulo_info,
        "rangos":           RANGOS_RESPUESTA,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def heartbeat_ra(request):
    """
    Mantiene la sesión RA activa.
    POST /api/ra/heartbeat/
    Body: {"session_token": "...", "timestamp": 1234567890, "latencia_cliente": 45.2}
    """
    serializer = HeartbeatSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data["session_token"]

    try:
        sesion = SesionRA.objects.get(session_token=token)
    except SesionRA.DoesNotExist:
        return Response(
            {"status": "error", "error": "Sesión no encontrada",
             "sesion_activa": False},
            status=status.HTTP_404_NOT_FOUND,
        )

    latencia = serializer.validated_data.get("latencia_cliente")
    update_fields = {"fecha_ultima_actividad": timezone.now()}

    if latencia:
        nueva_lat = latencia if sesion.latencia_promedio == 0 \
                    else sesion.latencia_promedio * 0.8 + latencia * 0.2
        update_fields["latencia_promedio"] = nueva_lat
    else:
        nueva_lat = sesion.latencia_promedio

    SesionRA.objects.filter(pk=sesion.pk).update(**update_fields)

    return Response({
        "status":            "ok",
        "sesion_activa":     True,
        "timestamp_servidor": int(time.time() * 1000),
        "latencia_promedio": round(nueva_lat, 2),
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def desconectar_ra(request):
    """Cierra una sesión RA."""
    token = request.data.get("session_token")
    if not token:
        return Response(
            {"error": "session_token es requerido"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        sesion = SesionRA.objects.get(session_token=token)
    except SesionRA.DoesNotExist:
        return Response({"error": "Sesión no encontrada"}, status=status.HTTP_404_NOT_FOUND)

    EventoRA.objects.create(
        sesion      = sesion,
        tipo        = "desconexion",
        descripcion = "Desconexión solicitada por el cliente",
        datos_adicionales = {
            "duracion_segundos": (timezone.now() - sesion.fecha_inicio).total_seconds()
        },
    )
    sesion.finalizar()

    return Response({
        "status":  "ok",
        "message": "Sesión finalizada exitosamente",
        "estadisticas": {
            "duracion_total":        int((sesion.fecha_fin - sesion.fecha_inicio).total_seconds()),
            "total_datos_recibidos": sesion.total_datos_recibidos,
            "latencia_promedio":     round(sesion.latencia_promedio, 2),
        },
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def stream_datos_ra(request):
    """Stream de últimos datos de sensores."""
    sesion, error = verificar_session_token(request)
    if error:
        return error

    if not sesion.practica:
        return Response({
            "status": "no_practice", "datos": [], "practica_activa": False
        })

    limit = min(int(request.GET.get("limit", 10)), 100)
    datos = DatosSensor.objects.filter(
        practica=sesion.practica
    ).order_by("-timestamp")[:limit]

    datos_stream = [
        {
            "timestamp":       int(time.mktime(d.timestamp.timetuple()) * 1000),
            "pitch":           round(d.angulo_pitch, 2),
            "roll":            round(d.angulo_roll, 2),
            "yaw":             round(d.angulo_yaw, 2),
            "fuerza":          round(d.fuerza, 2),
            "presion":         round(d.presion, 2) if d.presion else None,
            "tecnica_correcta": d.tecnica_correcta,
            "dato_id":         d.id,
        }
        for d in datos
    ]

    SesionRA.objects.filter(pk=sesion.pk).update(
        total_datos_recibidos=sesion.total_datos_recibidos + len(datos_stream)
    )

    return Response({
        "status":          "ok",
        "timestamp":       int(time.time() * 1000),
        "datos":           datos_stream,
        "practica_activa": sesion.practica.estado in ("iniciada", "pausada"),
        "estado_practica": sesion.practica.estado,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def estado_practica_ra(request):
    """Estado completo de la práctica con métricas."""
    sesion, error = verificar_session_token(request)
    if error:
        return error

    if not sesion.practica:
        return Response({
            "practica_activa":    False,
            "estudiante_nombre":  sesion.estudiante.nombre_completo,
            "tiempo_transcurrido": 0,
            "numero_intentos":    0,
            "precision_actual":   0.0,
            "ultimo_dato":        None,
            "rangos_optimos":     RANGOS_RESPUESTA,
        })

    practica = sesion.practica

    if practica.estado in ("finalizada", "pausada"):
        tiempo = practica.duracion_total_segundos
    else:
        referencia = practica.fecha_reanudacion or practica.fecha_inicio
        tiempo = int(practica.duracion_total_segundos +
                     (timezone.now() - referencia).total_seconds())

    total    = DatosSensor.objects.filter(practica=practica).count()
    correctos = DatosSensor.objects.filter(practica=practica, tecnica_correcta=True).count()
    precision = round(correctos / total * 100, 2) if total else 0.0

    ultimo = DatosSensor.objects.filter(practica=practica).order_by("-timestamp").first()
    ultimo_dato = {
        "pitch":            round(ultimo.angulo_pitch, 2),
        "roll":             round(ultimo.angulo_roll, 2),
        "yaw":              round(ultimo.angulo_yaw, 2),
        "fuerza":           round(ultimo.fuerza, 2),
        "tecnica_correcta": ultimo.tecnica_correcta,
        "timestamp":        int(time.mktime(ultimo.timestamp.timetuple()) * 1000),
    } if ultimo else None

    return Response({
        "practica_activa":    True,
        "practica_id":        practica.id,
        "estudiante_nombre":  practica.estudiante.nombre_completo,
        "estado":             practica.estado,
        "tiempo_transcurrido": tiempo,
        "numero_intentos":    practica.numero_intentos,
        "precision_actual":   precision,
        "ultimo_dato":        ultimo_dato,
        "rangos_optimos":     RANGOS_RESPUESTA,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def registrar_evento_ra(request):
    """Registra eventos desde el dispositivo RA."""
    sesion, error = verificar_session_token(request)
    if error:
        return error

    evento = EventoRA.objects.create(
        sesion            = sesion,
        tipo              = request.data.get("tipo", "error"),
        descripcion       = request.data.get("descripcion", ""),
        datos_adicionales = request.data.get("datos_adicionales", {}),
    )

    return Response({
        "status":    "ok",
        "evento_id": evento.id,
        "timestamp": int(time.mktime(evento.timestamp.timetuple()) * 1000),
    }, status=status.HTTP_201_CREATED)


# ── ViewSets de administración ────────────────────────────────────────────────

class SesionRAViewSet(viewsets.ModelViewSet):
    queryset           = SesionRA.objects.select_related("estudiante", "practica").all()
    serializer_class   = SesionRASerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def activas(self, request):
        sesiones = self.queryset.filter(estado__in=["activa", "pausada"])
        return Response(self.get_serializer(sesiones, many=True).data)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        sesion = self.get_object()
        sesion.finalizar()
        EventoRA.objects.create(
            sesion      = sesion,
            tipo        = "desconexion",
            descripcion = "Sesión finalizada manualmente desde el panel web",
        )
        return Response({"message": "Sesión finalizada",
                         "sesion": self.get_serializer(sesion).data})


class ConfiguracionRAViewSet(viewsets.ModelViewSet):
    queryset           = ConfiguracionRA.objects.select_related("estudiante").all()
    serializer_class   = ConfiguracionRASerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def por_estudiante(self, request):
        estudiante_id = request.query_params.get("estudiante_id")
        if not estudiante_id:
            return Response({"error": "estudiante_id es requerido"}, status=400)
        config, _ = ConfiguracionRA.objects.get_or_create(
            estudiante_id=estudiante_id,
            defaults={
                "color_angulo_correcto":   "#00FF00",
                "color_angulo_incorrecto": "#FF0000",
                "color_fuerza_correcta":   "#0000FF",
            },
        )
        return Response(self.get_serializer(config).data)


class EventoRAViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = EventoRA.objects.select_related("sesion").all()
    serializer_class   = EventoRASerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs        = super().get_queryset()
        sesion_id = self.request.query_params.get("sesion_id")
        if sesion_id:
            qs = qs.filter(sesion_id=sesion_id)
        return qs.order_by("-timestamp")


# ── Vista del dashboard ───────────────────────────────────────────────────────

def dashboard_view(request):
    return render(request, "dashboard.html")


# ── Endpoint original para compatibilidad ────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def conectar_ra(request):
    """Endpoint original de conexión (mantenido por compatibilidad)."""
    serializer = SesionRACreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        estudiante = Estudiante.objects.get(id=data["estudiante_id"])
    except Estudiante.DoesNotExist:
        return Response({"error": "Estudiante no encontrado"}, status=404)

    practica = None
    if data.get("practica_id"):
        try:
            practica = PracticaActiva.objects.get(id=data["practica_id"])
        except PracticaActiva.DoesNotExist:
            return Response({"error": "Práctica no encontrada"}, status=404)

    SesionRA.objects.filter(
        estudiante=estudiante, estado__in=["conectando", "activa", "pausada"]
    ).update(estado="desconectada", fecha_fin=timezone.now())

    sesion = SesionRA.objects.create(
        estudiante         = estudiante,
        practica           = practica,
        dispositivo_ra     = data["dispositivo_ra"],
        ip_address         = get_client_ip(request),
        estado             = "activa",
        modo_visualizacion = data["modo_visualizacion"],
        escala_modelo      = data["escala_modelo"],
        opacidad           = data["opacidad"],
    )

    config, _ = ConfiguracionRA.objects.get_or_create(
        estudiante=estudiante,
        defaults={
            "color_angulo_correcto":   "#00FF00",
            "color_angulo_incorrecto": "#FF0000",
            "color_fuerza_correcta":   "#0000FF",
        },
    )

    return Response({
        "status":        "success",
        "message":       "Conexión establecida",
        "session_token": sesion.session_token,
        "sesion_id":     sesion.id,
        "estudiante": {
            "id":     estudiante.id,
            "nombre": estudiante.nombre_completo,
            "codigo": estudiante.codigo_estudiante,
        },
        "configuracion": ConfiguracionRASerializer(config).data,
    }, status=status.HTTP_201_CREATED)