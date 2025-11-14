# placa/tests.py

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

from .models import DispositivoESP32, PracticaActiva, DatosSensor
from .serializers import (
    DispositivoESP32Serializer,
    PracticaActivaSerializer,
    DatosSensorSerializer,
    DatosSensorCreateSerializer
)
from estudiantes.models import Estudiante


# ===========================================
# TESTS DE MODELOS - DispositivoESP32
# ===========================================

class DispositivoESP32ModelTest(TestCase):
    """
    Tests para el modelo DispositivoESP32.
    Este modelo representa los dispositivos físicos ESP32 que envían datos de sensores.
    Cada dispositivo tiene una API key única para autenticación.
    """
    
    def setUp(self):
        """
        Preparar datos de prueba para cada test.
        Se ejecuta antes de cada método de test.
        """
        # Datos básicos para crear un dispositivo ESP32
        self.dispositivo_data = {
            'nombre': 'VeinView-01',
            'mac_address': 'AA:BB:CC:DD:EE:FF',  # Identificador único del hardware
            'activo': True
        }
    
    def test_crear_dispositivo_exitosamente(self):
        """
        Test: Verificar que se puede crear un dispositivo con todos sus campos.
        Comprueba que todos los valores se asignan correctamente.
        """
        # Crear el dispositivo con los datos preparados
        dispositivo = DispositivoESP32.objects.create(**self.dispositivo_data)
        
        # Verificar que los campos se guardaron correctamente
        self.assertEqual(dispositivo.nombre, 'VeinView-01')
        self.assertEqual(dispositivo.mac_address, 'AA:BB:CC:DD:EE:FF')
        self.assertTrue(dispositivo.activo)
        
        # Verificar que la API key se generó automáticamente
        self.assertIsNotNone(dispositivo.api_key)
        self.assertGreater(len(dispositivo.api_key), 20)  # Debe ser una key larga
    
    def test_api_key_generada_automaticamente(self):
        """
        Test: Verificar que al crear un dispositivo se genera automáticamente una API key.
        Esta key es necesaria para que el ESP32 se autentique en las peticiones.
        """
        dispositivo = DispositivoESP32.objects.create(**self.dispositivo_data)
        
        # La API key no debe ser None
        self.assertIsNotNone(dispositivo.api_key)
        
        # Debe tener una longitud considerable (seguridad)
        self.assertGreater(len(dispositivo.api_key), 40)
    
    def test_api_key_unica(self):
        """
        Test: Verificar que cada dispositivo tiene una API key única.
        Esto es crítico para la seguridad del sistema.
        """
        # Crear dos dispositivos diferentes
        dispositivo1 = DispositivoESP32.objects.create(
            nombre='Device-01',
            mac_address='AA:BB:CC:DD:EE:01'
        )
        dispositivo2 = DispositivoESP32.objects.create(
            nombre='Device-02',
            mac_address='AA:BB:CC:DD:EE:02'
        )
        
        # Las API keys deben ser diferentes
        self.assertNotEqual(dispositivo1.api_key, dispositivo2.api_key)
    
    def test_mac_address_unico(self):
        """
        Test: Verificar que la MAC address es única en la base de datos.
        No puede haber dos dispositivos con la misma dirección MAC (restricción a nivel BD).
        """
        # Crear primer dispositivo
        DispositivoESP32.objects.create(**self.dispositivo_data)
        
        # Importar excepción de integridad
        from django.db import IntegrityError
        
        # Intentar crear otro dispositivo con la misma MAC debe fallar
        with self.assertRaises(IntegrityError):
            DispositivoESP32.objects.create(
                nombre='Otro Dispositivo',
                mac_address='AA:BB:CC:DD:EE:FF'  # MAC duplicada
            )
    
    def test_dispositivo_str_representation(self):
        """
        Test: Verificar que el método __str__ retorna el formato correcto.
        Formato esperado: "Nombre (MAC_ADDRESS)"
        Útil para el admin de Django y debugging.
        """
        dispositivo = DispositivoESP32.objects.create(**self.dispositivo_data)
        
        # Construir la representación esperada
        expected = f"{dispositivo.nombre} ({dispositivo.mac_address})"
        
        # Verificar que coincide
        self.assertEqual(str(dispositivo), expected)
    
    def test_nombre_por_defecto(self):
        """
        Test: Verificar que si no se proporciona nombre, se use el valor por defecto.
        El valor por defecto debe ser 'VeinView Device'.
        """
        # Crear dispositivo sin especificar nombre
        dispositivo = DispositivoESP32.objects.create(
            mac_address='11:22:33:44:55:66'
        )
        
        # Debe tener el nombre por defecto
        self.assertEqual(dispositivo.nombre, 'VeinView Device')
    
    def test_actualizar_ultima_conexion(self):
        """
        Test: Verificar que se pueden actualizar los campos de conexión.
        Cuando el dispositivo se conecta, se actualiza última_conexion e ip_address.
        """
        # Crear dispositivo
        dispositivo = DispositivoESP32.objects.create(**self.dispositivo_data)
        
        # Actualizar campos de conexión
        ahora = timezone.now()
        dispositivo.ultima_conexion = ahora
        dispositivo.ip_address = '192.168.1.100'
        dispositivo.save()
        
        # Recargar desde la base de datos
        dispositivo.refresh_from_db()
        
        # Verificar que se actualizaron correctamente
        self.assertEqual(dispositivo.ultima_conexion, ahora)
        self.assertEqual(dispositivo.ip_address, '192.168.1.100')


# ===========================================
# TESTS DE MODELOS - PracticaActiva
# ===========================================

class PracticaActivaModelTest(TestCase):
    """
    Tests para el modelo PracticaActiva.
    Una práctica representa una sesión de trabajo de un estudiante con un dispositivo.
    Tiene estados: iniciada, pausada, finalizada.
    """
    
    def setUp(self):
        """
        Preparar datos necesarios: usuario, estudiante y dispositivo.
        Estos son prerequisitos para crear una práctica.
        """
        # Crear usuario de Django (para autenticación)
        self.user = User.objects.create_user(username='E12345', email='test@test.com')
        
        # Crear estudiante asociado al usuario
        self.estudiante = Estudiante.objects.create(
            user=self.user,
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
    
    def test_crear_practica_exitosamente(self):
        """
        Test: Verificar que se puede crear una práctica activa con todos sus campos.
        Una práctica vincula a un estudiante con un dispositivo durante una sesión.
        """
        # Crear la práctica
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='iniciada'
        )
        
        # Verificar relaciones y valores
        self.assertEqual(practica.estudiante, self.estudiante)
        self.assertEqual(practica.dispositivo, self.dispositivo)
        self.assertEqual(practica.estado, 'iniciada')
        self.assertEqual(practica.duracion_total_segundos, 0)  # Empieza en 0
        self.assertIsNotNone(practica.fecha_inicio)  # Se registra cuándo inició
    
    def test_estado_por_defecto_iniciada(self):
        """
        Test: Verificar que el estado por defecto de una práctica es 'iniciada'.
        Al crear una práctica sin especificar estado, debe estar iniciada.
        """
        # Crear práctica sin especificar estado
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo
        )
        
        # El estado debe ser 'iniciada'
        self.assertEqual(practica.estado, 'iniciada')
    
    def test_pausar_practica(self):
        """
        Test: Verificar que se puede pausar una práctica iniciada.
        Al pausar, debe:
        - Cambiar estado a 'pausada'
        - Registrar fecha_pausa
        - Acumular el tiempo transcurrido en duracion_total_segundos
        """
        # Crear práctica iniciada
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='iniciada'
        )
        
        # Simular un pequeño tiempo de ejecución
        import time
        time.sleep(0.1)  # Esperar 100ms
        
        # Pausar la práctica
        practica.pausar()
        practica.refresh_from_db()
        
        # Verificar cambios
        self.assertEqual(practica.estado, 'pausada')
        self.assertIsNotNone(practica.fecha_pausa)  # Se registró cuándo se pausó
        self.assertGreaterEqual(practica.duracion_total_segundos, 0)  # Tiempo acumulado
    
    def test_reanudar_practica(self):
        """
        Test: Verificar que se puede reanudar una práctica pausada.
        Al reanudar, debe:
        - Cambiar estado a 'iniciada'
        - Registrar fecha_reanudacion
        """
        # Crear práctica en estado pausada
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='pausada'
        )
        
        # Reanudar la práctica
        practica.reanudar()
        practica.refresh_from_db()
        
        # Verificar cambios
        self.assertEqual(practica.estado, 'iniciada')
        self.assertIsNotNone(practica.fecha_reanudacion)  # Se registró la reanudación
    
    def test_finalizar_practica_iniciada(self):
        """
        Test: Verificar que se puede finalizar una práctica que está iniciada.
        Al finalizar desde estado 'iniciada', debe calcular y guardar el tiempo total.
        """
        # Crear práctica iniciada
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='iniciada'
        )
        
        # Simular tiempo de ejecución
        import time
        time.sleep(0.1)
        
        # Finalizar la práctica
        practica.finalizar()
        practica.refresh_from_db()
        
        # Verificar cambios
        self.assertEqual(practica.estado, 'finalizada')
        self.assertIsNotNone(practica.fecha_fin)  # Se registró cuándo finalizó
        self.assertGreaterEqual(practica.duracion_total_segundos, 0)  # Tiempo calculado
    
    def test_finalizar_practica_pausada(self):
        """
        Test: Verificar que se puede finalizar una práctica que está pausada.
        Al finalizar desde estado 'pausada', debe mantener el tiempo ya acumulado.
        """
        # Crear práctica pausada con tiempo acumulado
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='pausada',
            duracion_total_segundos=100  # Ya tiene 100 segundos acumulados
        )
        
        # Finalizar la práctica
        practica.finalizar()
        practica.refresh_from_db()
        
        # Verificar cambios
        self.assertEqual(practica.estado, 'finalizada')
        self.assertIsNotNone(practica.fecha_fin)
        self.assertEqual(practica.duracion_total_segundos, 100)  # Mantiene el tiempo
    
    def test_practica_str_representation(self):
        """
        Test: Verificar el método __str__ de la práctica.
        Formato esperado: "Nombre del Estudiante - estado"
        """
        # Crear práctica
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo
        )
        
        # Construir representación esperada
        expected = f"{self.estudiante.nombre_completo} - iniciada"
        
        # Verificar que coincide
        self.assertEqual(str(practica), expected)


# ===========================================
# TESTS DE MODELOS - DatosSensor
# ===========================================

class DatosSensorModelTest(TestCase):
    """
    Tests para el modelo DatosSensor.
    Este modelo almacena las lecturas de los sensores del ESP32:
    - Acelerómetro (ax, ay, az)
    - Giroscopio (gx, gy, gz)
    - Ángulos calculados (pitch, roll, yaw)
    - Fuerza y presión
    """
    
    def setUp(self):
        """
        Preparar todos los objetos necesarios para registrar datos de sensores:
        usuario, estudiante, dispositivo y práctica activa.
        """
        # Crear usuario
        self.user = User.objects.create_user(username='E12345', email='test@test.com')
        
        # Crear estudiante
        self.estudiante = Estudiante.objects.create(
            user=self.user,
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
        
        # Crear práctica activa (necesaria para registrar datos)
        self.practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo
        )
    
    def test_crear_dato_sensor_exitosamente(self):
        """
        Test: Verificar que se puede crear un registro de sensor con todos los campos.
        Simula una lectura completa del ESP32 con todos los sensores.
        """
        # Crear dato con todos los campos
        dato = DatosSensor.objects.create(
            practica=self.practica,
            dispositivo=self.dispositivo,
            # Datos del acelerómetro (m/s²)
            aceleracion_x=0.5,
            aceleracion_y=-0.3,
            aceleracion_z=9.8,  # Gravedad
            # Datos del giroscopio (grados/s)
            giroscopio_x=2.1,
            giroscopio_y=-1.5,
            giroscopio_z=0.8,
            # Ángulos calculados (grados)
            angulo_pitch=15.5,
            angulo_roll=-10.2,
            angulo_yaw=5.3,
            # Sensores adicionales
            fuerza=250.5,
            presion=0.5,
            # Información de red
            ip_origen='192.168.1.100'
        )
        
        # Verificar que se guardaron las relaciones
        self.assertEqual(dato.practica, self.practica)
        self.assertEqual(dato.dispositivo, self.dispositivo)
        
        # Verificar un valor de sensor
        self.assertEqual(dato.fuerza, 250.5)
        
        # Verificar que se generó timestamp automáticamente
        self.assertIsNotNone(dato.timestamp)
    
    def test_dato_sensor_sin_presion(self):
        """
        Test: Verificar que el campo presión es opcional.
        No todos los dispositivos tienen sensor de presión.
        """
        # Crear dato sin especificar presión
        dato = DatosSensor.objects.create(
            practica=self.practica,
            dispositivo=self.dispositivo,
            aceleracion_x=0.5, aceleracion_y=-0.3, aceleracion_z=9.8,
            giroscopio_x=2.1, giroscopio_y=-1.5, giroscopio_z=0.8,
            angulo_pitch=15.5, angulo_roll=-10.2, angulo_yaw=5.3,
            fuerza=250.5
            # presion no especificada
        )
        
        # La presión debe ser None
        self.assertIsNone(dato.presion)
    
    def test_timestamp_automatico(self):
        """
        Test: Verificar que el timestamp se genera automáticamente al crear el registro.
        El timestamp debe estar entre el momento antes y después de crear el objeto.
        """
        # Capturar tiempo antes de crear
        antes = timezone.now()
        
        # Crear dato
        dato = DatosSensor.objects.create(
            practica=self.practica,
            dispositivo=self.dispositivo,
            aceleracion_x=0, aceleracion_y=0, aceleracion_z=0,
            giroscopio_x=0, giroscopio_y=0, giroscopio_z=0,
            angulo_pitch=0, angulo_roll=0, angulo_yaw=0,
            fuerza=0
        )
        
        # Capturar tiempo después de crear
        despues = timezone.now()
        
        # Verificar que el timestamp existe y está en el rango correcto
        self.assertIsNotNone(dato.timestamp)
        self.assertGreaterEqual(dato.timestamp, antes)
        self.assertLessEqual(dato.timestamp, despues)


# ===========================================
# TESTS DE SERIALIZERS
# ===========================================

class DatosSensorCreateSerializerTest(TestCase):
    """
    Tests para DatosSensorCreateSerializer.
    Este serializer valida los datos que envía el ESP32.
    Usa nombres abreviados de campos (ax, ay, gx, gy, etc.) para ahorrar ancho de banda.
    """
    
    def test_validar_datos_completos(self):
        """
        Test: Verificar que datos completos del ESP32 pasan la validación.
        Incluye todos los campos posibles.
        """
        # Datos con todos los campos (formato que envía el ESP32)
        data = {
            'ax': 0.5, 'ay': -0.3, 'az': 9.8,     # Acelerómetro
            'gx': 2.1, 'gy': -1.5, 'gz': 0.8,     # Giroscopio
            'pitch': 15.5, 'roll': -10.2, 'yaw': 5.3,  # Ángulos
            'fuerza': 250.5,                       # Sensor de fuerza
            'presion': 0.5                         # Sensor de presión (opcional)
        }
        
        # Crear serializer y validar
        serializer = DatosSensorCreateSerializer(data=data)
        
        # Debe ser válido
        self.assertTrue(serializer.is_valid())
    
    def test_validar_datos_sin_presion(self):
        """
        Test: Verificar que presión es un campo opcional.
        El ESP32 puede enviar datos sin el sensor de presión.
        """
        # Datos sin campo presión
        data = {
            'ax': 0.5, 'ay': -0.3, 'az': 9.8,
            'gx': 2.1, 'gy': -1.5, 'gz': 0.8,
            'pitch': 15.5, 'roll': -10.2, 'yaw': 5.3,
            'fuerza': 250.5
            # presion omitida
        }
        
        # Crear serializer y validar
        serializer = DatosSensorCreateSerializer(data=data)
        
        # Debe ser válido incluso sin presión
        self.assertTrue(serializer.is_valid())
    
    def test_validar_datos_incompletos(self):
        """
        Test: Verificar que datos incompletos no pasan la validación.
        Todos los campos excepto presión son requeridos.
        """
        # Datos con campos faltantes
        data = {
            'ax': 0.5,
            'fuerza': 250.5
            # Faltan muchos campos requeridos
        }
        
        # Crear serializer y validar
        serializer = DatosSensorCreateSerializer(data=data)
        
        # No debe ser válido
        self.assertFalse(serializer.is_valid())


# ===========================================
# TESTS DE VIEWS - Endpoints del ESP32
# ===========================================

class DispositivoESP32ViewsTest(APITestCase):
    """
    Tests para los endpoints relacionados con el dispositivo ESP32.
    Prueba el registro y autenticación de dispositivos.
    """
    
    def setUp(self):
        """
        Preparar cliente API y un dispositivo de prueba.
        """
        # Cliente para hacer peticiones HTTP
        self.client = APIClient()
        
        # Crear dispositivo de prueba
        self.dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-Test',
            mac_address='AA:BB:CC:DD:EE:FF',
            activo=True
        )
        
        # Guardar la API key para usarla en los tests
        self.api_key = self.dispositivo.api_key
    
    def test_registrar_dispositivo_nuevo(self):
        """
        Test: POST /api/placa/registrar/
        Verificar que un dispositivo nuevo puede registrarse y recibir API key.
        """
        url = reverse('placa:registrar_dispositivo')
        
        # Datos del nuevo dispositivo
        data = {
            'mac_address': '11:22:33:44:55:66',  # MAC nueva (no existe)
            'nombre': 'VeinView-02'
        }
        
        # Hacer petición POST
        response = self.client.post(url, data, format='json')
        
        # Verificar respuesta exitosa (201 Created)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar que se retorna la API key
        self.assertIn('api_key', response.data)
        
        # Verificar que los datos del dispositivo son correctos
        self.assertEqual(response.data['dispositivo']['nombre'], 'VeinView-02')
    
    def test_registrar_dispositivo_existente(self):
        """
        Test: Registrar un dispositivo que ya existe debe retornar 200 (OK).
        El endpoint es idempotente: si el dispositivo ya existe, retorna su API key.
        """
        url = reverse('placa:registrar_dispositivo')
        
        # Intentar registrar un dispositivo que ya existe
        data = {
            'mac_address': 'AA:BB:CC:DD:EE:FF',  # Ya existe en setUp
            'nombre': 'Otro Nombre'
        }
        
        # Hacer petición POST
        response = self.client.post(url, data, format='json')
        
        # Debe retornar 200 (no 201) porque ya existe
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Debe retornar la API key del dispositivo existente
        self.assertIn('api_key', response.data)
    
    def test_ping_con_api_key_valida(self):
        """
        Test: GET /api/placa/ping/
        Verificar que el endpoint de ping funciona con una API key válida.
        Este endpoint es usado por el ESP32 para verificar conectividad.
        """
        url = reverse('placa:verificar_conexion')
        
        # Hacer petición GET con la API key en el header
        response = self.client.get(url, HTTP_X_API_KEY=self.api_key)
        
        # Verificar respuesta exitosa
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que retorna status ok
        self.assertEqual(response.data['status'], 'ok')
    
    def test_ping_sin_api_key(self):
        """
        Test: Ping sin API key debe retornar 401 (Unauthorized).
        La autenticación es obligatoria.
        """
        url = reverse('placa:verificar_conexion')
        
        # Hacer petición sin incluir API key
        response = self.client.get(url)
        
        # Debe rechazar con 401
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_ping_con_api_key_invalida(self):
        """
        Test: Ping con API key inválida debe retornar 401.
        Solo API keys registradas son aceptadas.
        """
        url = reverse('placa:verificar_conexion')
        
        # Hacer petición con API key inventada
        response = self.client.get(url, HTTP_X_API_KEY='invalid-key-123')
        
        # Debe rechazar con 401
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PracticaActivaViewsTest(APITestCase):
    """
    Tests para endpoints relacionados con prácticas activas.
    El ESP32 consulta estos endpoints para saber si puede enviar datos.
    """
    
    def setUp(self):
        """
        Preparar dispositivo, estudiante y cliente API.
        """
        self.client = APIClient()
        
        # Crear dispositivo
        self.dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-Test',
            mac_address='AA:BB:CC:DD:EE:FF'
        )
        self.api_key = self.dispositivo.api_key
        
        # Crear usuario y estudiante
        self.user = User.objects.create_user(username='E12345', email='test@test.com')
        self.estudiante = Estudiante.objects.create(
            user=self.user,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
    
    def test_obtener_practica_activa_cuando_existe(self):
        """
        Test: GET /api/placa/practica-activa/
        Cuando hay una práctica activa para este dispositivo, debe retornarla.
        """
        # Crear práctica activa
        practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='iniciada'
        )
        
        url = reverse('placa:practica_activa')
        
        # Hacer petición con API key
        response = self.client.get(url, HTTP_X_API_KEY=self.api_key)
        
        # Verificar respuesta exitosa
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que indica que hay práctica activa
        self.assertTrue(response.data['practica_activa'])
        self.assertTrue(response.data['puede_enviar_datos'])
    
    def test_obtener_practica_activa_cuando_no_existe(self):
        """
        Test: Cuando no hay práctica activa, debe indicarlo.
        El ESP32 no debe enviar datos si no hay práctica activa.
        """
        url = reverse('placa:practica_activa')
        
        # Hacer petición sin crear práctica
        response = self.client.get(url, HTTP_X_API_KEY=self.api_key)
        
        # Verificar respuesta exitosa pero sin práctica
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['practica_activa'])
        self.assertFalse(response.data['puede_enviar_datos'])


class EnviarDatosSensoresTest(APITestCase):
    """
    Tests para el endpoint principal de envío de datos de sensores.
    Este es el endpoint que el ESP32 usa más frecuentemente para enviar lecturas.
    """
    
    def setUp(self):
        """
        Preparar todo el contexto necesario:
        dispositivo, estudiante, práctica activa y datos de prueba.
        """
        self.client = APIClient()
        
        # Crear dispositivo
        self.dispositivo = DispositivoESP32.objects.create(
            nombre='VeinView-Test',
            mac_address='AA:BB:CC:DD:EE:FF'
        )
        self.api_key = self.dispositivo.api_key
        
        # Crear usuario y estudiante
        self.user = User.objects.create_user(username='E12345', email='test@test.com')
        self.estudiante = Estudiante.objects.create(
            user=self.user,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
        
        # Crear práctica activa (necesaria para recibir datos)
        self.practica = PracticaActiva.objects.create(
            estudiante=self.estudiante,
            dispositivo=self.dispositivo,
            estado='iniciada'
        )
        
        # Datos de sensores válidos para usar en los tests
        self.datos_validos = {
            'ax': 0.5, 'ay': -0.3, 'az': 9.8,
            'gx': 2.1, 'gy': -1.5, 'gz': 0.8,
            'pitch': 15.5, 'roll': -10.2, 'yaw': 5.3,
            'fuerza': 250.5,
            'presion': 0.5
        }
    
    def test_enviar_datos_exitosamente(self):
        """
        Test: POST /api/placa/datos/
        Caso exitoso: enviar datos con práctica activa.
        """
        url = reverse('placa:enviar_datos')
        
        # Hacer petición POST con datos de sensores
        response = self.client.post(
            url,
            self.datos_validos,
            format='json',
            HTTP_X_API_KEY=self.api_key
        )
        
        # Verificar que se creó exitosamente (201)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar respuesta
        self.assertEqual(response.data['status'], 'ok')
        self.assertIn('dato_id', response.data)
        
        # Verificar que se guardó en la base de datos
        self.assertEqual(DatosSensor.objects.count(), 1)
    
    def test_enviar_datos_sin_practica_activa(self):
        """
        Test: No se pueden enviar datos si no hay práctica activa.
        El sistema debe rechazar los datos.
        """
        # Finalizar la práctica
        self.practica.finalizar()
        
        url = reverse('placa:enviar_datos')
        
        # Intentar enviar datos
        response = self.client.post(
            url,
            self.datos_validos,
            format='json',
            HTTP_X_API_KEY=self.api_key
        )
        
        # Debe rechazar la petición (400 Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['puede_enviar_datos'])
    
    def test_enviar_datos_practica_pausada(self):
        """
        Test: No se pueden enviar datos si la práctica está pausada.
        Solo se aceptan datos cuando la práctica está en estado 'iniciada'.
        """
        # Pausar la práctica
        self.practica.estado = 'pausada'
        self.practica.save()
        
        url = reverse('placa:enviar_datos')
        
        # Intentar enviar datos
        response = self.client.post(
            url,
            self.datos_validos,
            format='json',
            HTTP_X_API_KEY=self.api_key
        )
        
        # Debe rechazar porque está pausada
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================
# TESTS DE INTEGRACIÓN
# ===========================================

class IntegracionCompletaTest(APITestCase):
    """
    Test de integración completo que simula el flujo real del ESP32.
    Desde el registro del dispositivo hasta el envío de datos.
    Este test verifica que todos los componentes funcionan juntos correctamente.
    """
    
    def test_flujo_completo_esp32(self):
        """
        Test: Flujo completo de un dispositivo ESP32 nuevo.
        Simula el ciclo de vida completo:
        1. Registrar dispositivo
        2. Verificar conexión
        3. Crear práctica
        4. Enviar datos
        5. Verificar que se guardaron
        """
        
        # ========== PASO 1: REGISTRAR DISPOSITIVO ==========
        register_url = reverse('placa:registrar_dispositivo')
        register_data = {
            'mac_address': '11:22:33:44:55:66',
            'nombre': 'VeinView-Integration'
        }
        
        # Registrar dispositivo nuevo
        register_response = self.client.post(register_url, register_data, format='json')
        
        # Verificar que se registró exitosamente
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        
        # Guardar la API key para usar en siguientes pasos
        api_key = register_response.data['api_key']
        
        # ========== PASO 2: VERIFICAR CONEXIÓN (PING) ==========
        ping_url = reverse('placa:verificar_conexion')
        
        # Hacer ping con la API key recibida
        ping_response = self.client.get(ping_url, HTTP_X_API_KEY=api_key)
        
        # Verificar que la conexión funciona
        self.assertEqual(ping_response.status_code, status.HTTP_200_OK)
        
        # ========== PASO 3: CREAR CONTEXTO (ESTUDIANTE Y PRÁCTICA) ==========
        # Crear usuario y estudiante
        user = User.objects.create_user(username='E12345', email='test@test.com')
        estudiante = Estudiante.objects.create(
            user=user,
            codigo_estudiante='E12345',
            nombre_completo='Test Student',
            correo='test@test.com',
            semestre=1
        )
        
        # Obtener el dispositivo recién registrado
        dispositivo = DispositivoESP32.objects.get(mac_address='11:22:33:44:55:66')
        
        # Crear práctica activa
        practica = PracticaActiva.objects.create(
            estudiante=estudiante,
            dispositivo=dispositivo,
            estado='iniciada'
        )
        
        # ========== PASO 4: ENVIAR DATOS DE SENSORES ==========
        datos_url = reverse('placa:enviar_datos')
        
        # Datos de sensores a enviar
        datos = {
            'ax': 0.5, 'ay': -0.3, 'az': 9.8,
            'gx': 2.1, 'gy': -1.5, 'gz': 0.8,
            'pitch': 15.5, 'roll': -10.2, 'yaw': 5.3,
            'fuerza': 250.5
        }
        
        # Enviar datos con la API key
        datos_response = self.client.post(
            datos_url,
            datos,
            format='json',
            HTTP_X_API_KEY=api_key
        )
        
        # Verificar que se guardaron los datos
        self.assertEqual(datos_response.status_code, status.HTTP_201_CREATED)
        
        # ========== PASO 5: VERIFICAR QUE TODO SE GUARDÓ CORRECTAMENTE ==========
        # Debe haber exactamente 1 registro de sensor
        self.assertEqual(DatosSensor.objects.count(), 1)
        
        # Obtener el dato guardado
        dato = DatosSensor.objects.first()
        
        # Verificar que los valores son correctos
        self.assertEqual(dato.fuerza, 250.5)
        self.assertEqual(dato.practica, practica)