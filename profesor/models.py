# profesor/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Max, Min
from estudiantes.models import Estudiante
from placa.models import PracticaActiva, DatosSensor
# CORREGIDO: importar constantes centralizadas
from placa.constants import (
    ANGULO_MIN_OPTIMO, ANGULO_MAX_OPTIMO,
    FUERZA_MIN_OPTIMA, FUERZA_MAX_OPTIMA,
)


class Profesor(models.Model):
    """Modelo de Profesor que extiende User."""
    user           = models.OneToOneField(User, on_delete=models.CASCADE,
                                          related_name="profesor")
    nombre_completo = models.CharField(max_length=200)
    cedula          = models.CharField(max_length=20, unique=True)
    correo          = models.EmailField(unique=True)
    telefono        = models.CharField(max_length=20, blank=True)
    especialidad    = models.CharField(max_length=100, blank=True)
    activo          = models.BooleanField(default=True)
    fecha_registro  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Profesor"
        verbose_name_plural = "Profesores"
        ordering            = ["nombre_completo"]

    def __str__(self):
        return f"{self.nombre_completo} ({self.cedula})"

    def total_estudiantes(self) -> int:
        return self.estudiantes.filter(activo=True).count()

    def practicas_hoy(self) -> int:
        from django.utils import timezone
        hoy = timezone.now().date()
        return PracticaActiva.objects.filter(
            estudiante__profesor=self, fecha_inicio__date=hoy
        ).count()


class ResumenPractica(models.Model):
    """Resumen y calificación de prácticas finalizadas."""
    practica = models.OneToOneField(PracticaActiva, on_delete=models.CASCADE,
                                    related_name="resumen")
    profesor = models.ForeignKey(Profesor, on_delete=models.SET_NULL, null=True,
                                 related_name="practicas_evaluadas")

    total_datos_capturados = models.IntegerField(default=0)
    inclinacion_promedio   = models.FloatField(null=True, blank=True,
                             help_text="Pitch promedio (°)")
    fuerza_promedio        = models.FloatField(null=True, blank=True,
                             help_text="Fuerza promedio (g)")
    fuerza_maxima          = models.FloatField(null=True, blank=True,
                             help_text="Fuerza máxima (g)")
    fuerza_minima          = models.FloatField(null=True, blank=True,
                             help_text="Fuerza mínima (g)")

    numero_intentos      = models.IntegerField(default=0)
    intentos_exitosos    = models.IntegerField(default=0)
    precision_porcentaje = models.FloatField(default=0.0,
                           help_text="Precisión general (%)")
    tiempo_canalizacion  = models.IntegerField(default=0,
                           help_text="Tiempo total en segundos")

    calificacion  = models.FloatField(null=True, blank=True,
                    help_text="Calificación de 0.0 a 5.0")
    observaciones = models.TextField(blank=True)

    # CORREGIDO: criterios evaluados con los mismos rangos que DatosSensor.save()
    tecnica_correcta   = models.BooleanField(default=False)
    angulo_adecuado    = models.BooleanField(default=False)
    presion_controlada = models.BooleanField(default=False)

    fecha_evaluacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Resumen de Práctica"
        verbose_name_plural = "Resúmenes de Prácticas"
        ordering            = ["-fecha_evaluacion"]

    def __str__(self):
        return f"Evaluación - {self.practica.estudiante.nombre_completo}"

    def calcular_estadisticas(self):
        """
        Calcula estadísticas de la práctica desde DatosSensor.
        CORREGIDO: usa constantes de constants.py para angulo_adecuado
        y presion_controlada — mismos rangos que DatosSensor.save().
        """
        datos = DatosSensor.objects.filter(practica=self.practica)
        if not datos.exists():
            return

        self.total_datos_capturados = datos.count()

        stats = datos.aggregate(
            avg_pitch=Avg("angulo_pitch"),
            avg_fuerza=Avg("fuerza"),
            max_fuerza=Max("fuerza"),
            min_fuerza=Min("fuerza"),
        )

        self.inclinacion_promedio = stats["avg_pitch"]
        self.fuerza_promedio      = stats["avg_fuerza"]
        self.fuerza_maxima        = stats["max_fuerza"]
        self.fuerza_minima        = stats["min_fuerza"]

        self.numero_intentos    = self.practica.numero_intentos
        self.intentos_exitosos  = self.practica.intentos_exitosos
        self.tiempo_canalizacion = self.practica.duracion_total_segundos

        correctos = datos.filter(tecnica_correcta=True).count()
        self.precision_porcentaje = round(
            correctos / self.total_datos_capturados * 100, 2
        )

        # Usar constantes centralizadas — coherente con DatosSensor.save()
        pitch  = self.inclinacion_promedio or 0
        fuerza = self.fuerza_promedio or 0

        self.angulo_adecuado    = ANGULO_MIN_OPTIMO <= pitch  <= ANGULO_MAX_OPTIMO
        self.presion_controlada = FUERZA_MIN_OPTIMA <= fuerza <= FUERZA_MAX_OPTIMA
        self.tecnica_correcta   = self.angulo_adecuado and self.presion_controlada

        self.save()

    def calcular_calificacion_automatica(self) -> float:
        """Calificación automática de 0.0 a 5.0."""
        if not self.total_datos_capturados:
            return 0.0

        cal = 0.0
        # Precisión: 40% = 2.0 puntos
        cal += (self.precision_porcentaje / 100) * 2.0
        # Ángulo: 30% = 1.5 puntos
        pitch = self.inclinacion_promedio or 0
        if self.angulo_adecuado:
            cal += 1.5
        elif ANGULO_MIN_OPTIMO - 5 <= pitch <= ANGULO_MAX_OPTIMO + 10:
            cal += 1.0
        # Presión: 30% = 1.5 puntos
        fuerza = self.fuerza_promedio or 0
        if self.presion_controlada:
            cal += 1.5
        elif FUERZA_MIN_OPTIMA - 20 <= fuerza <= FUERZA_MAX_OPTIMA + 100:
            cal += 1.0

        self.calificacion = round(cal, 2)
        self.save(update_fields=["calificacion"])
        return self.calificacion


class EncuestaSistema(models.Model):
    """Encuestas de evaluación del sistema por estudiantes."""
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE,
                                   related_name="encuestas")
    practica   = models.ForeignKey(PracticaActiva, on_delete=models.CASCADE,
                                   related_name="encuestas", null=True, blank=True)

    facilidad_uso      = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    utilidad_sistema   = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    precision_sensores = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    interfaz_clara     = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    mejora_aprendizaje = models.IntegerField(choices=[(i, i) for i in range(1, 6)])

    aspectos_positivos = models.TextField(blank=True)
    aspectos_negativos = models.TextField(blank=True)
    sugerencias        = models.TextField(blank=True)
    recomendaria       = models.BooleanField(default=True)

    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name        = "Encuesta del Sistema"
        verbose_name_plural = "Encuestas del Sistema"
        ordering            = ["-fecha_respuesta"]

    def __str__(self):
        return f"Encuesta - {self.estudiante.nombre_completo} - {self.fecha_respuesta.date()}"

    @property
    def puntuacion_promedio(self) -> float:
        return (
            self.facilidad_uso + self.utilidad_sistema + self.precision_sensores
            + self.interfaz_clara + self.mejora_aprendizaje
        ) / 5


class ReporteGeneral(models.Model):
    """Reportes generales del sistema con métricas agregadas."""
    profesor        = models.ForeignKey(Profesor, on_delete=models.CASCADE,
                                        related_name="reportes_generados")
    titulo          = models.CharField(max_length=200, default="Reporte de Desempeño")
    fecha_inicio    = models.DateTimeField()
    fecha_fin       = models.DateTimeField()

    total_estudiantes     = models.IntegerField(default=0)
    total_practicas       = models.IntegerField(default=0)
    total_datos_capturados = models.IntegerField(default=0)

    promedio_precision    = models.FloatField(default=0.0)
    promedio_intentos     = models.FloatField(default=0.0)
    promedio_tiempo       = models.FloatField(default=0.0, help_text="Minutos")
    promedio_calificacion = models.FloatField(default=0.0)
    promedio_satisfaccion = models.FloatField(default=0.0)
    total_encuestas       = models.IntegerField(default=0)

    fecha_generacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Reporte General"
        verbose_name_plural = "Reportes Generales"
        ordering            = ["-fecha_generacion"]

    def __str__(self):
        return f"{self.titulo} - {self.fecha_inicio.date()} a {self.fecha_fin.date()}"

    def generar_estadisticas(self):
        practicas = PracticaActiva.objects.filter(
            estudiante__profesor=self.profesor,
            fecha_inicio__gte=self.fecha_inicio,
            fecha_inicio__lte=self.fecha_fin,
            estado="finalizada",
        )

        self.total_practicas   = practicas.count()
        self.total_estudiantes = practicas.values("estudiante").distinct().count()

        if self.total_practicas > 0:
            stats = practicas.aggregate(
                avg_precision=Avg("precision_promedio"),
                avg_intentos=Avg("numero_intentos"),
                avg_tiempo=Avg("duracion_total_segundos"),
            )
            self.promedio_precision = round(stats["avg_precision"] or 0, 2)
            self.promedio_intentos  = round(stats["avg_intentos"]  or 0, 2)
            self.promedio_tiempo    = round((stats["avg_tiempo"] or 0) / 60, 2)

            self.total_datos_capturados = DatosSensor.objects.filter(
                practica__in=practicas
            ).count()

            resumenes = ResumenPractica.objects.filter(
                practica__in=practicas, calificacion__isnull=False
            )
            if resumenes.exists():
                self.promedio_calificacion = round(
                    resumenes.aggregate(avg=Avg("calificacion"))["avg"] or 0, 2
                )

            encuestas = EncuestaSistema.objects.filter(practica__in=practicas)
            self.total_encuestas = encuestas.count()
            if self.total_encuestas:
                self.promedio_satisfaccion = round(
                    sum(e.puntuacion_promedio for e in encuestas) / self.total_encuestas, 2
                )

        self.save()