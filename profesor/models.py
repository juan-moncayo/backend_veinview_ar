from django.db import models
from django.contrib.auth.models import User
from estudiantes.models import Estudiante
from placa.models import PracticaActiva, DatosSensor
from django.db.models import Avg, Max, Min, Count, Q

class ResumenPractica(models.Model):
    """Resumen y calificación de prácticas finalizadas"""
    practica = models.OneToOneField(PracticaActiva, on_delete=models.CASCADE, related_name='resumen')
    profesor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='practicas_evaluadas')
    
    # Estadísticas calculadas automáticamente
    total_datos_capturados = models.IntegerField(default=0)
    inclinacion_promedio = models.FloatField(null=True, blank=True, help_text="Ángulo promedio (°)")
    fuerza_promedio = models.FloatField(null=True, blank=True, help_text="Fuerza promedio (g)")
    fuerza_maxima = models.FloatField(null=True, blank=True, help_text="Fuerza máxima (g)")
    fuerza_minima = models.FloatField(null=True, blank=True, help_text="Fuerza mínima (g)")
    
    # NUEVO: Métricas de desempeño
    numero_intentos = models.IntegerField(default=0, help_text="Total de intentos realizados")
    intentos_exitosos = models.IntegerField(default=0, help_text="Intentos con técnica correcta")
    precision_porcentaje = models.FloatField(default=0.0, help_text="Precisión general (%)")
    tiempo_canalizacion = models.IntegerField(default=0, help_text="Tiempo total de canalización (segundos)")
    
    # Evaluación del profesor
    calificacion = models.FloatField(null=True, blank=True, help_text="Calificación de 0.0 a 5.0")
    observaciones = models.TextField(blank=True)
    
    # Criterios de evaluación
    tecnica_correcta = models.BooleanField(default=False)
    angulo_adecuado = models.BooleanField(default=False)
    presion_controlada = models.BooleanField(default=False)
    
    fecha_evaluacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Resumen de Práctica"
        verbose_name_plural = "Resúmenes de Prácticas"
        ordering = ['-fecha_evaluacion']
    
    def __str__(self):
        return f"Evaluación - {self.practica.estudiante.nombre_completo}"
    
    def calcular_estadisticas(self):
        """Calcula todas las estadísticas de la práctica"""
        datos = DatosSensor.objects.filter(practica=self.practica)
        
        if datos.exists():
            # Estadísticas básicas
            self.total_datos_capturados = datos.count()
            
            # Promedios y rangos
            stats = datos.aggregate(
                avg_pitch=Avg('angulo_pitch'),
                avg_roll=Avg('angulo_roll'),
                avg_fuerza=Avg('fuerza'),
                max_fuerza=Max('fuerza'),
                min_fuerza=Min('fuerza')
            )
            
            self.inclinacion_promedio = stats['avg_pitch']
            self.fuerza_promedio = stats['avg_fuerza']
            self.fuerza_maxima = stats['max_fuerza']
            self.fuerza_minima = stats['min_fuerza']
            
            # Métricas de desempeño
            self.numero_intentos = self.practica.numero_intentos
            self.intentos_exitosos = self.practica.intentos_exitosos
            self.tiempo_canalizacion = self.practica.duracion_total_segundos
            
            # Calcular precisión
            datos_correctos = datos.filter(tecnica_correcta=True).count()
            self.precision_porcentaje = (datos_correctos / self.total_datos_capturados * 100) if self.total_datos_capturados > 0 else 0
            
            # Evaluar criterios automáticamente
            self.angulo_adecuado = 10 <= (self.inclinacion_promedio or 0) <= 30
            self.presion_controlada = 50 <= (self.fuerza_promedio or 0) <= 300
            self.tecnica_correcta = self.angulo_adecuado and self.presion_controlada
            
            self.save()
    
    def calcular_calificacion_automatica(self):
        """Calcula una calificación automática basada en métricas"""
        if not self.total_datos_capturados:
            return 0.0
        
        # Ponderación de criterios (total 5.0)
        calificacion = 0.0
        
        # 1. Precisión (40% = 2.0 puntos)
        calificacion += (self.precision_porcentaje / 100) * 2.0
        
        # 2. Ángulo adecuado (30% = 1.5 puntos)
        if self.angulo_adecuado:
            calificacion += 1.5
        elif 5 <= (self.inclinacion_promedio or 0) <= 35:
            calificacion += 1.0  # Parcial
        
        # 3. Presión controlada (30% = 1.5 puntos)
        if self.presion_controlada:
            calificacion += 1.5
        elif 30 <= (self.fuerza_promedio or 0) <= 400:
            calificacion += 1.0  # Parcial
        
        self.calificacion = round(calificacion, 2)
        self.save(update_fields=['calificacion'])
        return self.calificacion


class EncuestaSistema(models.Model):
    """Encuestas de evaluación del sistema por estudiantes"""
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='encuestas')
    practica = models.ForeignKey(PracticaActiva, on_delete=models.CASCADE, related_name='encuestas', null=True, blank=True)
    
    # Preguntas de satisfacción (1-5)
    facilidad_uso = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text="¿Qué tan fácil fue usar el sistema? (1=Muy difícil, 5=Muy fácil)"
    )
    utilidad_sistema = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text="¿Qué tan útil fue el sistema para tu práctica? (1=Nada útil, 5=Muy útil)"
    )
    precision_sensores = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text="¿Qué tan precisos consideras los sensores? (1=Nada precisos, 5=Muy precisos)"
    )
    interfaz_clara = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text="¿Qué tan clara fue la interfaz? (1=Muy confusa, 5=Muy clara)"
    )
    mejora_aprendizaje = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text="¿El sistema mejoró tu aprendizaje? (1=Nada, 5=Mucho)"
    )
    
    # Preguntas abiertas
    aspectos_positivos = models.TextField(blank=True, help_text="¿Qué te gustó del sistema?")
    aspectos_negativos = models.TextField(blank=True, help_text="¿Qué no te gustó del sistema?")
    sugerencias = models.TextField(blank=True, help_text="Sugerencias de mejora")
    
    # Recomendación
    recomendaria = models.BooleanField(default=True, help_text="¿Recomendarías este sistema?")
    
    # Metadata
    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Encuesta del Sistema"
        verbose_name_plural = "Encuestas del Sistema"
        ordering = ['-fecha_respuesta']
    
    def __str__(self):
        return f"Encuesta - {self.estudiante.nombre_completo} - {self.fecha_respuesta.strftime('%Y-%m-%d')}"
    
    @property
    def puntuacion_promedio(self):
        """Calcula el promedio de las puntuaciones"""
        return (
            self.facilidad_uso +
            self.utilidad_sistema +
            self.precision_sensores +
            self.interfaz_clara +
            self.mejora_aprendizaje
        ) / 5


class ReporteGeneral(models.Model):
    """Reportes generales del sistema con métricas agregadas"""
    titulo = models.CharField(max_length=200, default="Reporte de Desempeño")
    fecha_inicio = models.DateTimeField(help_text="Inicio del período del reporte")
    fecha_fin = models.DateTimeField(help_text="Fin del período del reporte")
    generado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reportes_generados')
    
    # Estadísticas generales
    total_estudiantes = models.IntegerField(default=0)
    total_practicas = models.IntegerField(default=0)
    total_datos_capturados = models.IntegerField(default=0)
    
    # Promedios generales
    promedio_precision = models.FloatField(default=0.0, help_text="Precisión promedio general (%)")
    promedio_intentos = models.FloatField(default=0.0, help_text="Promedio de intentos por estudiante")
    promedio_tiempo = models.FloatField(default=0.0, help_text="Tiempo promedio de práctica (minutos)")
    promedio_calificacion = models.FloatField(default=0.0, help_text="Calificación promedio")
    
    # Encuestas
    promedio_satisfaccion = models.FloatField(default=0.0, help_text="Satisfacción promedio (1-5)")
    total_encuestas = models.IntegerField(default=0)
    
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Reporte General"
        verbose_name_plural = "Reportes Generales"
        ordering = ['-fecha_generacion']
    
    def __str__(self):
        return f"{self.titulo} - {self.fecha_inicio.strftime('%Y-%m-%d')} a {self.fecha_fin.strftime('%Y-%m-%d')}"
    
    def generar_estadisticas(self):
        """Genera todas las estadísticas del reporte"""
        # Filtrar prácticas en el período
        practicas = PracticaActiva.objects.filter(
            fecha_inicio__gte=self.fecha_inicio,
            fecha_inicio__lte=self.fecha_fin,
            estado='finalizada'
        )
        
        self.total_practicas = practicas.count()
        self.total_estudiantes = practicas.values('estudiante').distinct().count()
        
        if self.total_practicas > 0:
            # Promedios de métricas
            stats = practicas.aggregate(
                avg_precision=Avg('precision_promedio'),
                avg_intentos=Avg('numero_intentos'),
                avg_tiempo=Avg('duracion_total_segundos')
            )
            
            self.promedio_precision = stats['avg_precision'] or 0.0
            self.promedio_intentos = stats['avg_intentos'] or 0.0
            self.promedio_tiempo = (stats['avg_tiempo'] or 0) / 60  # Convertir a minutos
            
            # Total de datos
            self.total_datos_capturados = DatosSensor.objects.filter(
                practica__in=practicas
            ).count()
            
            # Promedio de calificaciones
            resumenes = ResumenPractica.objects.filter(
                practica__in=practicas,
                calificacion__isnull=False
            )
            if resumenes.exists():
                self.promedio_calificacion = resumenes.aggregate(
                    avg_cal=Avg('calificacion')
                )['avg_cal'] or 0.0
            
            # Encuestas
            encuestas = EncuestaSistema.objects.filter(
                practica__in=practicas
            )
            self.total_encuestas = encuestas.count()
            if self.total_encuestas > 0:
                self.promedio_satisfaccion = sum(
                    e.puntuacion_promedio for e in encuestas
                ) / self.total_encuestas
        
        self.save()