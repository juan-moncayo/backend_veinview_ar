# estudiantes/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from .models import Estudiante
from .serializers import EstudianteSerializer, EstudianteCreateSerializer


# ===========================================
# TESTS DE MODELOS
# ===========================================

class EstudianteModelTest(TestCase):
    """
    Suite de tests para verificar el comportamiento del modelo Estudiante.
    Hereda de TestCase que proporciona funcionalidades para testing en Django.
    """
    
    def setUp(self):
        """
        Método que se ejecuta ANTES de cada test individual.
        Prepara los datos necesarios (fixtures) para las pruebas.
        """
        # Crear un usuario de Django que será asociado al estudiante
        self.user = User.objects.create_user(
            username='E12345',
            email='estudiante@test.com',
            password='testpass123'
        )
        
        # Diccionario con datos válidos de estudiante para usar en los tests
        self.estudiante_data = {
            'user': self.user,
            'codigo_estudiante': 'E12345',
            'nombre_completo': 'Juan Pérez García',
            'correo': 'juan.perez@test.com',
            'programa': 'Enfermería',
            'semestre': 5,
            'telefono': '3001234567',
            'activo': True
        }
    
    def test_crear_estudiante_exitosamente(self):
        """
        Verifica que se pueda crear un estudiante con datos válidos.
        Comprueba que los campos se guarden correctamente.
        """
        # Crear el estudiante usando los datos preparados
        estudiante = Estudiante.objects.create(**self.estudiante_data)
        
        # Verificar que los datos se guardaron correctamente
        self.assertEqual(estudiante.codigo_estudiante, 'E12345')
        self.assertEqual(estudiante.nombre_completo, 'Juan Pérez García')
        self.assertTrue(estudiante.activo)
    
    def test_estudiante_str_representation(self):
        """
        Verifica que el método __str__ del modelo retorne el formato esperado.
        Esto es útil para representaciones en admin y debugging.
        """
        estudiante = Estudiante.objects.create(**self.estudiante_data)
        # El método __str__ debe retornar: "CODIGO - NOMBRE"
        self.assertEqual(str(estudiante), "E12345 - Juan Pérez García")
    
    def test_codigo_estudiante_unico(self):
        """
        Verifica que el campo codigo_estudiante sea único en la base de datos.
        Debe lanzar IntegrityError al intentar crear un duplicado.
        """
        # Crear primer estudiante
        Estudiante.objects.create(**self.estudiante_data)
        
        # Crear segundo usuario para el intento de duplicado
        user2 = User.objects.create_user(username='E99999', email='otro@test.com')
        
        # Intentar crear otro estudiante con el mismo código debe fallar
        with self.assertRaises(IntegrityError):
            Estudiante.objects.create(
                user=user2,
                codigo_estudiante='E12345',  # Código duplicado
                nombre_completo='Otro Estudiante',
                correo='otro.estudiante@test.com',
                semestre=3
            )
    
    def test_correo_unico(self):
        """
        Verifica que el campo correo sea único en la base de datos.
        Dos estudiantes no pueden tener el mismo correo electrónico.
        """
        # Crear primer estudiante
        Estudiante.objects.create(**self.estudiante_data)
        
        # Crear segundo usuario
        user2 = User.objects.create_user(username='E67890', email='diferente@test.com')
        
        # Intentar crear estudiante con correo duplicado debe fallar
        with self.assertRaises(IntegrityError):
            Estudiante.objects.create(
                user=user2,
                codigo_estudiante='E67890',
                nombre_completo='María López',
                correo='juan.perez@test.com',  # Correo duplicado
                semestre=4
            )
    
    def test_programa_por_defecto(self):
        """
        Verifica que el campo 'programa' tenga un valor por defecto.
        Si no se proporciona, debe usar 'Enfermería'.
        """
        # Crear copia de datos y eliminar el campo programa
        data = self.estudiante_data.copy()
        del data['programa']
        
        # Crear estudiante sin especificar programa
        estudiante = Estudiante.objects.create(**data)
        
        # Verificar que se asignó el valor por defecto
        self.assertEqual(estudiante.programa, 'Enfermería')
    
    def test_estudiante_activo_por_defecto(self):
        """
        Verifica que el campo 'activo' sea True por defecto.
        Los estudiantes deben estar activos al ser creados.
        """
        # Crear datos sin el campo activo
        data = self.estudiante_data.copy()
        del data['activo']
        
        # Crear estudiante
        estudiante = Estudiante.objects.create(**data)
        
        # Verificar que está activo por defecto
        self.assertTrue(estudiante.activo)


# ===========================================
# TESTS DE SERIALIZERS
# ===========================================

class EstudianteSerializerTest(TestCase):
    """
    Tests para el serializador de lectura EstudianteSerializer.
    Verifica que los datos se serialicen correctamente.
    """
    
    def setUp(self):
        """
        Prepara un estudiante en la base de datos para los tests.
        """
        # Crear usuario y estudiante de prueba
        self.user = User.objects.create_user(username='E12345', email='estudiante@test.com')
        self.estudiante = Estudiante.objects.create(
            user=self.user,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            programa='Enfermería',
            semestre=5
        )
    
    def test_serializar_estudiante(self):
        """
        Verifica que el serializer convierta correctamente el modelo a JSON.
        Todos los campos esperados deben estar presentes.
        """
        # Serializar el estudiante
        serializer = EstudianteSerializer(self.estudiante)
        data = serializer.data
        
        # Verificar que los campos se serializaron correctamente
        self.assertEqual(data['codigo_estudiante'], 'E12345')
        self.assertEqual(data['nombre_completo'], 'Juan Pérez')
        self.assertIn('fecha_registro', data)  # Campo automático debe estar presente
    
    def test_campos_read_only(self):
        """
        Verifica que los campos de solo lectura estén configurados correctamente.
        fecha_registro no debe ser editable.
        """
        serializer = EstudianteSerializer(self.estudiante)
        
        # Verificar que fecha_registro existe y es de solo lectura
        self.assertIn('fecha_registro', serializer.fields)
        self.assertTrue(serializer.fields['fecha_registro'].read_only)


class EstudianteCreateSerializerTest(TestCase):
    """
    Tests para el serializador de creación EstudianteCreateSerializer.
    Verifica validaciones y creación de estudiantes.
    """
    
    def test_validar_datos_completos(self):
        """
        Verifica que datos completos y válidos pasen la validación.
        """
        # Datos completos con todos los campos opcionales
        data = {
            'codigo_estudiante': 'E67890',
            'nombre_completo': 'María López',
            'correo': 'maria@test.com',
            'programa': 'Medicina',
            'semestre': 3,
            'telefono': '3001234567'
        }
        
        # Crear serializer y validar
        serializer = EstudianteCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validar_datos_minimos(self):
        """
        Verifica que solo los campos requeridos sean suficientes.
        codigo_estudiante, nombre_completo y correo son obligatorios.
        """
        # Solo campos requeridos
        data = {
            'codigo_estudiante': 'E11111',
            'nombre_completo': 'Carlos Ruiz',
            'correo': 'carlos@test.com'
        }
        
        # Debe ser válido con solo los campos mínimos
        serializer = EstudianteCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validar_codigo_duplicado(self):
        """
        Verifica que no se permita crear estudiante con código duplicado.
        La validación debe detectar códigos ya existentes.
        """
        # Crear primer estudiante
        user = User.objects.create_user(username='E12345', email='test@test.com')
        Estudiante.objects.create(
            user=user,
            codigo_estudiante='E12345',
            nombre_completo='Existente',
            correo='existente@test.com',
            semestre=1
        )
        
        # Intentar crear otro con el mismo código
        data = {
            'codigo_estudiante': 'E12345',  # Duplicado
            'nombre_completo': 'Nuevo',
            'correo': 'nuevo@test.com'
        }
        
        # No debe ser válido
        serializer = EstudianteCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('codigo_estudiante', serializer.errors)
    
    def test_validar_correo_duplicado(self):
        """
        Verifica que no se permita crear estudiante con correo duplicado.
        Cada correo debe ser único en el sistema.
        """
        # Crear primer estudiante
        user = User.objects.create_user(username='E12345', email='test@test.com')
        Estudiante.objects.create(
            user=user,
            codigo_estudiante='E12345',
            nombre_completo='Existente',
            correo='existente@test.com',
            semestre=1
        )
        
        # Intentar crear otro con el mismo correo
        data = {
            'codigo_estudiante': 'E99999',
            'nombre_completo': 'Nuevo',
            'correo': 'existente@test.com'  # Correo duplicado
        }
        
        # No debe ser válido
        serializer = EstudianteCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('correo', serializer.errors)
    
    def test_validar_correo_invalido(self):
        """
        Verifica que se valide el formato del correo electrónico.
        Correos mal formados deben ser rechazados.
        """
        # Datos con correo inválido
        data = {
            'codigo_estudiante': 'E99999',
            'nombre_completo': 'Test',
            'correo': 'correo-invalido'  # Sin @ ni dominio
        }
        
        # No debe ser válido
        serializer = EstudianteCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('correo', serializer.errors)


# ===========================================
# TESTS DE VIEWS (API)
# ===========================================

class EstudianteViewSetTest(APITestCase):
    """
    Tests para el ViewSet de la API REST de estudiantes.
    Verifica endpoints CRUD: Listar, Crear, Obtener, Actualizar, Eliminar.
    """
    
    def setUp(self):
        """
        Configura el cliente API y datos de prueba para cada test.
        """
        # Cliente para hacer peticiones HTTP a la API
        self.client = APIClient()
        
        # Crear usuario y estudiante de prueba
        self.user = User.objects.create_user(username='E12345', email='test@test.com')
        self.estudiante = Estudiante.objects.create(
            user=self.user,
            codigo_estudiante='E12345',
            nombre_completo='Juan Pérez',
            correo='juan@test.com',
            semestre=5
        )
        
        # URLs de los endpoints (usando reverse para obtener la URL correcta)
        self.list_url = reverse('estudiantes:estudiante-list')  # /api/estudiantes/
        self.detail_url = reverse('estudiantes:estudiante-detail', args=[self.estudiante.id])  # /api/estudiantes/{id}/
    
    def test_listar_estudiantes(self):
        """
        Test GET /api/estudiantes/
        Verifica que se listen todos los estudiantes con paginación.
        """
        response = self.client.get(self.list_url)
        
        # Verificar código de respuesta exitoso
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que hay un estudiante en los resultados paginados
        self.assertEqual(len(response.data['results']), 1)
    
    def test_obtener_detalle_estudiante(self):
        """
        Test GET /api/estudiantes/{id}/
        Verifica que se obtenga el detalle de un estudiante específico.
        """
        response = self.client.get(self.detail_url)
        
        # Verificar respuesta exitosa
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que los datos son correctos
        self.assertEqual(response.data['codigo_estudiante'], 'E12345')
    
    def test_crear_estudiante_exitosamente(self):
        """
        Test POST /api/estudiantes/
        Verifica que se pueda crear un nuevo estudiante.
        Debe crear tanto el estudiante como el usuario asociado.
        """
        # Datos del nuevo estudiante
        data = {
            'codigo_estudiante': 'E67890',
            'nombre_completo': 'María López',
            'correo': 'maria@test.com',
            'programa': 'Medicina',
            'semestre': 3,
            'telefono': '3001234567'
        }
        
        # Hacer petición POST
        response = self.client.post(self.list_url, data, format='json')
        
        # Verificar que se creó exitosamente (código 201)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar que los datos de respuesta son correctos
        self.assertEqual(response.data['codigo_estudiante'], 'E67890')
        
        # Verificar que se creó en la base de datos
        self.assertTrue(Estudiante.objects.filter(codigo_estudiante='E67890').exists())
        
        # Verificar que se creó el usuario automáticamente
        self.assertTrue(User.objects.filter(username='E67890').exists())
    
    def test_crear_estudiante_sin_datos_requeridos(self):
        """
        Test POST /api/estudiantes/ con datos incompletos.
        Debe rechazar la petición si faltan campos requeridos.
        """
        # Datos incompletos (falta codigo_estudiante y correo)
        data = {'nombre_completo': 'Test'}
        
        response = self.client.post(self.list_url, data, format='json')
        
        # Debe retornar error 400 (Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_crear_estudiante_codigo_duplicado(self):
        """
        Test POST /api/estudiantes/ con código duplicado.
        No debe permitir crear estudiante con código ya existente.
        """
        # Intentar crear con código que ya existe
        data = {
            'codigo_estudiante': 'E12345',  # Ya existe
            'nombre_completo': 'Nuevo Estudiante',
            'correo': 'nuevo@test.com'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        # Debe rechazar la petición
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_actualizar_estudiante(self):
        """
        Test PATCH /api/estudiantes/{id}/
        Verifica que se pueda actualizar parcialmente un estudiante.
        """
        # Datos a actualizar (actualización parcial)
        data = {'telefono': '3109876543', 'semestre': 6}
        
        # Hacer petición PATCH
        response = self.client.patch(self.detail_url, data, format='json')
        
        # Verificar respuesta exitosa
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que los datos se actualizaron
        self.assertEqual(response.data['telefono'], '3109876543')
    
    def test_eliminar_estudiante(self):
        """
        Test DELETE /api/estudiantes/{id}/
        Verifica que se pueda eliminar un estudiante.
        """
        response = self.client.delete(self.detail_url)
        
        # Verificar código 204 (No Content - eliminación exitosa)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verificar que ya no existe en la base de datos
        self.assertFalse(Estudiante.objects.filter(id=self.estudiante.id).exists())


# ===========================================
# TESTS DE INTEGRACIÓN
# ===========================================

class EstudianteIntegrationTest(APITestCase):
    """
    Tests de integración que verifican flujos completos de la aplicación.
    Simulan casos de uso reales con múltiples operaciones.
    """
    
    def test_flujo_completo_crud(self):
        """
        Test de integración: Flujo completo CRUD (Create, Read, Update, Delete).
        Simula el ciclo de vida completo de un estudiante en el sistema.
        """
        
        # ========== 1. CREAR ESTUDIANTE ==========
        create_data = {
            'codigo_estudiante': 'E11111',
            'nombre_completo': 'Test Completo',
            'correo': 'test@test.com',
            'semestre': 1
        }
        
        # Crear nuevo estudiante
        create_response = self.client.post(
            reverse('estudiantes:estudiante-list'),
            create_data,
            format='json'
        )
        
        # Verificar creación exitosa
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        
        # Guardar el ID para operaciones posteriores
        estudiante_id = create_response.data['id']
        
        # ========== 2. LISTAR ESTUDIANTES ==========
        list_response = self.client.get(reverse('estudiantes:estudiante-list'))
        
        # Verificar que aparece en el listado
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['results']), 1)
        
        # ========== 3. OBTENER DETALLE ==========
        detail_url = reverse('estudiantes:estudiante-detail', args=[estudiante_id])
        detail_response = self.client.get(detail_url)
        
        # Verificar que se obtienen los detalles correctamente
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        
        # ========== 4. ACTUALIZAR ==========
        update_response = self.client.patch(
            detail_url,
            {'semestre': 5},  # Actualizar semestre
            format='json'
        )
        
        # Verificar actualización exitosa
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['semestre'], 5)
        
        # ========== 5. ELIMINAR ==========
        delete_response = self.client.delete(detail_url)
        
        # Verificar eliminación exitosa
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)