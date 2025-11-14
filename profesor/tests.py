# profesor/tests.py

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

from .models import ResumenPractica
from placa.models import DispositivoESP32, PracticaActiva, DatosSensor
from estudiantes.models import Estudiante


# ===========================================
# TESTS DE MODELOS - ResumenPractica
# ===========================================

class ResumenPracticaModelTest(TestCase):
    """
    Tests para el modelo ResumenPractica.
    Este modelo representa la evaluación que un profesor hace de una práctica finalizada.
    Incluye estadísticas calculadas, calificación y observaciones pedagógicas.
    """
    
    def setUp(self):
        """
        Configuración inicial para cada test.
        Se ejecuta ANTES de cada método de test individual.
        Prepara todo el contexto necesario: profesor, estudiante, dispositivo y práctica.
        """
        # Crear profesor (usuario con rol de docente)
        self.profesor = User.objects.create_user(
            username='profesor01',
            email='profesor@test.com',
            password='testpass123'
        )
        
        # Crear usuario para el estudiante
        self.user_estudiante = User.objects.create_user(
            username='E12345',
            email='estudiante@test.com'
        )
        
        # Crear estudiante asociado al usuario
        self.estudiante = Estudiante.objects.create(
            user=self.user_estudiante,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
        
        # Crear dispositivo ESP32
        self.dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-01',
            mac_address='AA:BB:CC:DD:EE:FF'
        )
        
        # Crear práctica finalizada (prerequisito para crear resumen)
        self.practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='finalizada',  # Solo se evalúan prácticas finalizadas
            duracion_total_segundos=300  # 5 minutos
        )
        
        # Crear algunos datos de sensores para tener información estadística
        for i in range(5):
            DatosSensor.objects.create(
                practica=self.practica,
                dispositivo=self.dispositivo,
                aceleracion_x=0.5,
                aceleracion_y=-0.3,
                aceleracion_z=9.8,
                giroscopio_x=2.1,
                giroscopio_y=-1.5,
                giroscopio_z=0.8,
                angulo_pitch=15.5 + i,  # Variación en ángulo
                angulo_roll=-10.2,
                angulo_yaw=5.3,
                fuerza=250.0 + (i * 10)  # Variación en fuerza
            )
    
    def test_crear_resumen_practica_exitosamente(self):
        """
        Test: Verificar que se puede crear un resumen completo con todos los campos.
        Un resumen incluye estadísticas, evaluación cualitativa y calificación.
        """
        # Crear resumen con todos los campos
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            # Estadísticas numéricas
            total_datos_capturados=100,
            inclinacion_promedio=15.5,
            fuerza_promedio=250.5,
            fuerza_maxima=300.0,
            # Evaluación
            calificacion=4.5,
            observaciones='Excelente técnica',
            # Criterios de evaluación (checkboxes)
            tecnica_correcta=True,
            angulo_adecuado=True,
            presion_controlada=True
        )
        
        # Verificar que todos los campos se guardaron correctamente
        self.assertEqual(resumen.practica, self.practica)
        self.assertEqual(resumen.profesor, self.profesor)
        self.assertEqual(resumen.total_datos_capturados, 100)
        self.assertEqual(resumen.inclinacion_promedio, 15.5)
        self.assertEqual(resumen.fuerza_promedio, 250.5)
        self.assertEqual(resumen.calificacion, 4.5)
        self.assertTrue(resumen.tecnica_correcta)
        
        # Verificar que la fecha se generó automáticamente
        self.assertIsNotNone(resumen.fecha_evaluacion)
    
    def test_resumen_str_representation(self):
        """
        Test: Verificar el método __str__ del resumen.
        Formato esperado: "Evaluación - Nombre del Estudiante"
        Útil para el admin de Django y debugging.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        # Construir representación esperada
        expected = f"Evaluación - {self.estudiante.nombre_completo}"
        
        # Verificar que coincide
        self.assertEqual(str(resumen), expected)
    
    def test_relacion_one_to_one_con_practica(self):
        """
        Test: Verificar la relación OneToOne entre ResumenPractica y PracticaActiva.
        Una práctica solo puede tener UN resumen (una evaluación).
        La relación es bidireccional.
        """
        # Crear resumen
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        # Verificar relación directa: resumen -> práctica
        self.assertEqual(resumen.practica, self.practica)
        
        # Verificar relación inversa: práctica -> resumen
        # Django crea automáticamente el atributo 'resumen' en PracticaActiva
        self.assertEqual(self.practica.resumen, resumen)
    
    def test_crear_resumen_sin_calificacion(self):
        """
        Test: Verificar que la calificación es un campo opcional (null=True).
        Un profesor puede crear un resumen sin asignar calificación aún.
        """
        # Crear resumen sin calificación
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            total_datos_capturados=50
        )
        
        # La calificación debe ser None
        self.assertIsNone(resumen.calificacion)
        
        # Pero el resumen debe existir
        self.assertIsNotNone(resumen.id)
    
    def test_crear_resumen_sin_observaciones(self):
        """
        Test: Verificar que observaciones es opcional (blank=True).
        Un resumen puede no tener comentarios textuales.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            total_datos_capturados=50
        )
        
        # Observaciones debe ser string vacío (no None, porque blank=True pero no null=True)
        self.assertEqual(resumen.observaciones, '')
    
    def test_criterios_evaluacion_por_defecto(self):
        """
        Test: Verificar que los criterios de evaluación son False por defecto.
        Los checkboxes (tecnica_correcta, angulo_adecuado, presion_controlada)
        empiezan desmarcados hasta que el profesor los evalúe.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        # Todos los criterios deben ser False por defecto
        self.assertFalse(resumen.tecnica_correcta)
        self.assertFalse(resumen.angulo_adecuado)
        self.assertFalse(resumen.presion_controlada)
    
    def test_total_datos_por_defecto(self):
        """
        Test: Verificar que total_datos_capturados tiene valor por defecto 0.
        Si no se especifica, empieza en cero.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        # Debe ser 0 por defecto
        self.assertEqual(resumen.total_datos_capturados, 0)
    
    def test_calificacion_rango_valido(self):
        """
        Test: Verificar que la calificación puede estar entre 0.0 y 5.0.
        Aunque Django no valida el rango a nivel de modelo (eso se hace en formularios),
        verificamos que acepta valores en este rango.
        """
        # Calificación máxima
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            calificacion=5.0
        )
        self.assertEqual(resumen.calificacion, 5.0)
        
        # Calificación mínima
        resumen.calificacion = 0.0
        resumen.save()
        self.assertEqual(resumen.calificacion, 0.0)
    
    def test_fecha_evaluacion_automatica(self):
        """
        Test: Verificar que fecha_evaluacion se establece automáticamente (auto_now_add=True).
        La fecha debe generarse en el momento de crear el resumen.
        """
        # Capturar tiempo antes de crear
        antes = timezone.now()
        
        # Crear resumen
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        # Capturar tiempo después de crear
        despues = timezone.now()
        
        # Verificar que la fecha existe y está en el rango correcto
        self.assertIsNotNone(resumen.fecha_evaluacion)
        self.assertGreaterEqual(resumen.fecha_evaluacion, antes)
        self.assertLessEqual(resumen.fecha_evaluacion, despues)
    
    def test_profesor_puede_ser_null(self):
        """
        Test: Verificar que el profesor puede ser null (on_delete=SET_NULL).
        Si se elimina al profesor, el resumen no se borra, solo se desvincula.
        Esto preserva el historial de evaluaciones aunque el profesor ya no esté.
        """
        # Crear resumen asociado al profesor
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        # Guardar ID del profesor
        profesor_id = self.profesor.id
        
        # Eliminar al profesor
        self.profesor.delete()
        
        # Recargar el resumen desde la base de datos
        resumen.refresh_from_db()
        
        # El resumen debe existir pero sin profesor asociado
        self.assertIsNone(resumen.profesor)
    
    def test_campos_estadisticos_opcionales(self):
        """
        Test: Verificar que los campos estadísticos son opcionales (null=True, blank=True).
        inclinacion_promedio, fuerza_promedio y fuerza_maxima pueden ser None.
        Útil cuando no hay datos suficientes para calcular estadísticas.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            total_datos_capturados=10
        )
        
        # Todos los campos estadísticos pueden ser None
        self.assertIsNone(resumen.inclinacion_promedio)
        self.assertIsNone(resumen.fuerza_promedio)
        self.assertIsNone(resumen.fuerza_maxima)
    
    def test_actualizar_estadisticas(self):
        """
        Test: Verificar que se pueden actualizar las estadísticas después de crear el resumen.
        Permite calcular estadísticas en dos pasos:
        1. Crear resumen básico
        2. Actualizar con estadísticas calculadas
        """
        # Crear resumen sin estadísticas
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            total_datos_capturados=0
        )
        
        # Actualizar con estadísticas calculadas
        resumen.total_datos_capturados = 5
        resumen.inclinacion_promedio = 17.5
        resumen.fuerza_promedio = 270.0
        resumen.fuerza_maxima = 290.0
        resumen.save()
        
        # Recargar desde la base de datos
        resumen.refresh_from_db()
        
        # Verificar que se actualizaron correctamente
        self.assertEqual(resumen.total_datos_capturados, 5)
        self.assertEqual(resumen.inclinacion_promedio, 17.5)
        self.assertEqual(resumen.fuerza_promedio, 270.0)
        self.assertEqual(resumen.fuerza_maxima, 290.0)
    
    def test_meta_verbose_names(self):
        """
        Test: Verificar los nombres verbosos del modelo (para el admin de Django).
        Estos nombres aparecen en la interfaz administrativa.
        """
        self.assertEqual(ResumenPractica._meta.verbose_name, 'Resumen de Práctica')
        self.assertEqual(ResumenPractica._meta.verbose_name_plural, 'Resúmenes de Prácticas')
    
    def test_ordenamiento_por_fecha_evaluacion(self):
        """
        Test: Verificar que los resúmenes se ordenan por fecha_evaluacion descendente.
        Los más recientes aparecen primero (útil para listados).
        """
        # Crear segunda práctica para tener dos resúmenes
        practica2 = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='finalizada'
        )
        
        # Crear primer resumen con fecha antigua
        resumen1 = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        # Modificar su fecha manualmente para asegurar que sea más antigua
        resumen1.fecha_evaluacion = timezone.now() - timedelta(days=1)
        resumen1.save()
        
        # Crear segundo resumen (más reciente)
        resumen2 = ResumenPractica.objects.create(
            practica=practica2,
            profesor=self.profesor
        )
        
        # Obtener todos los resúmenes (ordenados por defecto)
        resumenes = list(ResumenPractica.objects.all())
        
        # El más reciente debe ser el primero en la lista
        self.assertEqual(resumenes[0].id, resumen2.id)
        self.assertEqual(resumenes[1].id, resumen1.id)


# ===========================================
# TESTS DE LÓGICA DE NEGOCIO
# ===========================================

class ResumenPracticaLogicaNegocioTest(TestCase):
    """
    Tests de lógica de negocio para ResumenPractica.
    Estos tests verifican las reglas de negocio y cálculos que involucran
    múltiples modelos o procesos complejos.
    """
    
    def setUp(self):
        """
        Configuración inicial: crear el contexto mínimo necesario.
        """
        # Crear profesor
        self.profesor = User.objects.create_user(
            username='profesor01',
            email='profesor@test.com'
        )
        
        # Crear usuario y estudiante
        self.user_estudiante = User.objects.create_user(
            username='E12345',
            email='estudiante@test.com'
        )
        self.estudiante = Estudiante.objects.create(
            user=self.user_estudiante,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
        
        # Crear dispositivo
        self.dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-01',
            mac_address='AA:BB:CC:DD:EE:FF'
        )
        
        # Crear práctica finalizada
        self.practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='finalizada'
        )
    
    def test_calcular_estadisticas_desde_datos_sensores(self):
        """
        Test: Simular el cálculo de estadísticas a partir de datos de sensores reales.
        Este es el flujo típico:
        1. La práctica captura datos
        2. Se calculan promedios y máximos
        3. Se crea el resumen con esas estadísticas
        """
        # Crear datos de sensores con valores conocidos
        fuerzas = [100, 150, 200, 250, 300]
        angulos = [10, 15, 20, 25, 30]
        
        for i in range(5):
            DatosSensor.objects.create(
                practica=self.practica,
                dispositivo=self.dispositivo,
                aceleracion_x=0, aceleracion_y=0, aceleracion_z=0,
                giroscopio_x=0, giroscopio_y=0, giroscopio_z=0,
                angulo_pitch=angulos[i],
                angulo_roll=0,
                angulo_yaw=0,
                fuerza=fuerzas[i]
            )
        
        # Calcular estadísticas manualmente (simulando lo que haría el sistema)
        total_datos = DatosSensor.objects.filter(practica=self.practica).count()
        fuerza_promedio = sum(fuerzas) / len(fuerzas)  # 200.0
        fuerza_maxima = max(fuerzas)  # 300.0
        angulo_promedio = sum(angulos) / len(angulos)  # 20.0
        
        # Crear resumen con las estadísticas calculadas
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            total_datos_capturados=total_datos,
            fuerza_promedio=fuerza_promedio,
            fuerza_maxima=fuerza_maxima,
            inclinacion_promedio=angulo_promedio
        )
        
        # Verificar que las estadísticas son correctas
        self.assertEqual(resumen.total_datos_capturados, 5)
        self.assertEqual(resumen.fuerza_promedio, 200.0)
        self.assertEqual(resumen.fuerza_maxima, 300.0)
        self.assertEqual(resumen.inclinacion_promedio, 20.0)
    
    def test_evaluar_criterios_tecnica_correcta(self):
        """
        Test: Simular evaluación positiva de una práctica.
        Cuando la técnica es correcta, todos los criterios son True y la calificación es alta.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            fuerza_promedio=250.0,  # Fuerza adecuada
            inclinacion_promedio=15.0,  # Ángulo correcto
            # Criterios de evaluación positivos
            tecnica_correcta=True,
            angulo_adecuado=True,
            presion_controlada=True,
            calificacion=5.0  # Calificación máxima
        )
        
        # Verificar que todos los criterios son positivos
        self.assertTrue(resumen.tecnica_correcta)
        self.assertTrue(resumen.angulo_adecuado)
        self.assertTrue(resumen.presion_controlada)
        self.assertEqual(resumen.calificacion, 5.0)
    
    def test_evaluar_criterios_tecnica_incorrecta(self):
        """
        Test: Simular evaluación negativa de una práctica.
        Cuando la técnica es incorrecta (fuerza excesiva, ángulo inadecuado),
        los criterios son False y la calificación es baja.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            fuerza_promedio=500.0,  # Fuerza excesiva (mala)
            inclinacion_promedio=45.0,  # Ángulo inadecuado (muy inclinado)
            # Criterios de evaluación negativos
            tecnica_correcta=False,
            angulo_adecuado=False,
            presion_controlada=False,
            calificacion=2.0  # Calificación baja
        )
        
        # Verificar que todos los criterios son negativos
        self.assertFalse(resumen.tecnica_correcta)
        self.assertFalse(resumen.angulo_adecuado)
        self.assertFalse(resumen.presion_controlada)
        
        # Verificar que la calificación es baja
        self.assertLess(resumen.calificacion, 3.0)
    
    def test_estudiante_puede_tener_multiples_resumenes(self):
        """
        Test: Verificar que un estudiante puede tener múltiples prácticas evaluadas.
        Un estudiante puede realizar varias prácticas a lo largo del semestre,
        cada una con su propia evaluación.
        """
        # Crear segunda práctica para el mismo estudiante
        practica2 = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='finalizada'
        )
        
        # Crear resúmenes para ambas prácticas
        resumen1 = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            calificacion=4.0
        )
        
        resumen2 = ResumenPractica.objects.create(
            practica=practica2,
            profesor=self.profesor,
            calificacion=4.5  # Mejoró en la segunda práctica
        )
        
        # Verificar que el estudiante tiene 2 prácticas evaluadas
        resumenes_estudiante = ResumenPractica.objects.filter(
            practica__estudiante=self.estudiante
        )
        self.assertEqual(resumenes_estudiante.count(), 2)
    
    def test_profesor_puede_evaluar_multiples_practicas(self):
        """
        Test: Verificar que un profesor puede evaluar prácticas de múltiples estudiantes.
        Un profesor evalúa a varios estudiantes durante el semestre.
        """
        # Crear otro estudiante
        user2 = User.objects.create_user(username='E67890', email='otro@test.com')
        estudiante2 = Estudiante.objects.create(
            user=user2,
            codigo_estudiante='E67890',
            nombre_completo='María López',
            correo='maria@test.com',
            semestre=3
        )
        
        # Crear práctica para el segundo estudiante
        practica2 = PracticaActiva.objects.create(
            estudiante=estudiante2,
            dispositivo=self.dispositivo,
            estado='finalizada'
        )
        
        # El mismo profesor evalúa ambas prácticas
        resumen1 = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor
        )
        
        resumen2 = ResumenPractica.objects.create(
            practica=practica2,
            profesor=self.profesor
        )
        
        # Verificar que el profesor evaluó 2 prácticas
        evaluaciones_profesor = ResumenPractica.objects.filter(
            profesor=self.profesor
        )
        self.assertEqual(evaluaciones_profesor.count(), 2)


# ===========================================
# TESTS DE INTEGRACIÓN
# ===========================================

class ResumenPracticaIntegracionTest(TestCase):
    """
    Tests de integración para ResumenPractica.
    Estos tests verifican el flujo completo desde el inicio de una práctica
    hasta su evaluación final por el profesor.
    """
    
    def test_flujo_completo_practica_con_evaluacion(self):
        """
        Test: Flujo completo desde que se inicia una práctica hasta que es evaluada.
        Este test simula el proceso real:
        1. Crear entidades (profesor, estudiante, dispositivo)
        2. Iniciar práctica
        3. Capturar datos de sensores
        4. Finalizar práctica
        5. Calcular estadísticas
        6. Crear resumen con evaluación
        7. Verificar resultados
        """
        
        # ========== PASO 1: CREAR ENTIDADES NECESARIAS ==========
        # Crear profesor
        profesor = User.objects.create_user(
            username='profesor01',
            email='profesor@test.com'
        )
        
        # Crear usuario y estudiante
        user_estudiante = User.objects.create_user(
            username='E12345',
            email='estudiante@test.com'
        )
        estudiante = Estudiante.objects.create(
            user=user_estudiante,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
        
        # Crear dispositivo
        dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-01',
            mac_address='AA:BB:CC:DD:EE:FF'
        )
        
        # ========== PASO 2: INICIAR PRÁCTICA ==========
        practica = PracticaActiva.objects.create(
            estudiante=estudiante,
            dispositivo=dispositivo,
            estado='iniciada'
        )
        
        # Verificar que la práctica está iniciada
        self.assertEqual(practica.estado, 'iniciada')
        
        # ========== PASO 3: CAPTURAR DATOS DE SENSORES ==========
        # Simular captura de 10 lecturas de sensores durante la práctica
        for i in range(10):
            DatosSensor.objects.create(
                practica=practica,
                dispositivo=dispositivo,
                aceleracion_x=0.5, aceleracion_y=-0.3, aceleracion_z=9.8,
                giroscopio_x=2.1, giroscopio_y=-1.5, giroscopio_z=0.8,
                angulo_pitch=15.0 + i,  # Variación gradual: 15, 16, 17...
                angulo_roll=-10.0,
                angulo_yaw=5.0,
                fuerza=200.0 + (i * 5)  # Variación gradual: 200, 205, 210...
            )
        
        # ========== PASO 4: FINALIZAR PRÁCTICA ==========
        practica.finalizar()
        
        # Verificar que la práctica está finalizada
        self.assertEqual(practica.estado, 'finalizada')
        
        # ========== PASO 5: CALCULAR ESTADÍSTICAS ==========
        # Obtener todos los datos capturados
        datos = DatosSensor.objects.filter(practica=practica)
        
        # Calcular estadísticas
        total_datos = datos.count()
        fuerza_promedio = sum([d.fuerza for d in datos]) / total_datos
        fuerza_maxima = max([d.fuerza for d in datos])
        angulo_promedio = sum([d.angulo_pitch for d in datos]) / total_datos
        
        # ========== PASO 6: CREAR RESUMEN CON EVALUACIÓN ==========
        resumen = ResumenPractica.objects.create(
            practica=practica,
            profesor=profesor,
            # Estadísticas calculadas
            total_datos_capturados=total_datos,
            fuerza_promedio=fuerza_promedio,
            fuerza_maxima=fuerza_maxima,
            inclinacion_promedio=angulo_promedio,
            # Evaluación del profesor
            calificacion=4.5,
            observaciones='Buena técnica, mejorar control de presión',
            tecnica_correcta=True,
            angulo_adecuado=True,
            presion_controlada=True
        )
        
        # ========== PASO 7: VERIFICACIONES FINALES ==========
        # Verificar estadísticas
        self.assertEqual(resumen.total_datos_capturados, 10)
        
        # Verificar cálculos (con tolerancia para decimales)
        # Fuerza promedio: (200+205+210+215+220+225+230+235+240+245) / 10 = 222.5
        self.assertAlmostEqual(resumen.fuerza_promedio, 222.5, places=1)
        
        # Fuerza máxima: 245
        self.assertEqual(resumen.fuerza_maxima, 245.0)
        
        # Ángulo promedio: (15+16+17+18+19+20+21+22+23+24) / 10 = 19.5
        self.assertAlmostEqual(resumen.inclinacion_promedio, 19.5, places=1)
        
        # Verificar evaluación
        self.assertEqual(resumen.calificacion, 4.5)
        self.assertTrue(resumen.tecnica_correcta)
        
        # Verificar relaciones
        self.assertEqual(resumen.practica.estudiante, estudiante)
        self.assertEqual(resumen.profesor, profesor)


# ===========================================
# TESTS DE CASOS ESPECIALES
# ===========================================

class ResumenPracticaCasosEspecialesTest(TestCase):
    """
    Tests de casos especiales y edge cases.
    Situaciones poco comunes pero que deben manejarse correctamente.
    """
    
    def setUp(self):
        """
        Configuración básica para los tests de casos especiales.
        """
        # Crear profesor
        self.profesor = User.objects.create_user(
            username='profesor01',
            email='profesor@test.com'
        )
        
        # Crear usuario y estudiante
        user_estudiante = User.objects.create_user(
            username='E12345',
            email='estudiante@test.com'
        )
        self.estudiante = Estudiante.objects.create(
            user=user_estudiante,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
        
        # Crear dispositivo
        dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-01',
            mac_address='AA:BB:CC:DD:EE:FF'
        )
        
        # Crear práctica finalizada
        self.practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=dispositivo,
            estado='finalizada'
        )
    
    def test_resumen_sin_datos_capturados(self):
        """
        Test: Resumen de práctica sin datos capturados (caso extremo).
        Puede ocurrir si hubo problemas técnicos durante la práctica.
        El resumen debe poder crearse incluso sin estadísticas.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            total_datos_capturados=0,
            observaciones='No se capturaron datos debido a problemas técnicos'
        )
        
        # Verificar que el resumen existe
        self.assertEqual(resumen.total_datos_capturados, 0)
        
        # Las estadísticas deben ser None (no hay datos para calcular)
        self.assertIsNone(resumen.fuerza_promedio)
    
    def test_resumen_con_calificacion_minima(self):
        """
        Test: Resumen con calificación mínima (0.0).
        Caso de una práctica con técnica completamente incorrecta.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            calificacion=0.0,
            observaciones='Técnica totalmente incorrecta, requiere repetir la práctica'
        )
        
        # Verificar que acepta calificación 0
        self.assertEqual(resumen.calificacion, 0.0)
    
    def test_resumen_con_calificacion_maxima(self):
        """
        Test: Resumen con calificación máxima (5.0).
        Caso de una práctica perfecta en todos los aspectos.
        """
        resumen = ResumenPractica.objects.create(
            practica=self.practica,
            profesor=self.profesor,
            calificacion=5.0,
            observaciones='Técnica perfecta, excelente control',
            # Todos los criterios cumplidos
            tecnica_correcta=True,
            angulo_adecuado=True,
            presion_controlada=True
        )
        
        # Verificar calificación máxima
        self.assertEqual(resumen.calificacion, 5.0)
        
        # Verificar que todos los criterios son positivos
        self.assertTrue(all([
            resumen.tecnica_correcta,
            resumen.angulo_adecuado,
            resumen.presion_controlada
        ]))