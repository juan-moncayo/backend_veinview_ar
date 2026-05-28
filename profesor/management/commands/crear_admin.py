from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from profesor.models import Profesor
from estudiantes.models import Estudiante


class Command(BaseCommand):
    help = 'Crea usuarios iniciales si no existen'

    def handle(self, *args, **kwargs):

        # ── Profesor ──────────────────────────────────────────
        if not User.objects.filter(username='veinview').exists():
            user_prof = User.objects.create_user(
                username='veinview',
                password='Veinview12345',
                email='veinview@veinview.com'
            )
            user_prof.is_staff = True
            user_prof.is_superuser = True
            user_prof.save()

            Profesor.objects.create(
                user=user_prof,
                nombre_completo='VeinView AR',
                cedula='00000001',
                correo='veinview@veinview.com',
                activo=True
            )
            self.stdout.write(self.style.SUCCESS('Profesor veinview creado'))
        else:
            self.stdout.write('Profesor veinview ya existe — omitiendo')

        # ── Estudiante ────────────────────────────────────────
        if not User.objects.filter(username='josemafla441@gmail.com').exists():
            try:
                profesor = Profesor.objects.get(user__username='veinview')

                user_est = User.objects.create_user(
                    username='josemafla441@gmail.com',
                    password='1010019817',
                    email='josemafla441@gmail.com'
                )
                user_est.save()

                Estudiante.objects.create(
                    user=user_est,
                    profesor=profesor,
                    codigo_estudiante='1010019817',
                    nombre_completo='Jose Ma Fla',
                    correo='josemafla441@gmail.com',
                    programa='Enfermería',
                    semestre=1,
                    activo=True
                )
                self.stdout.write(self.style.SUCCESS('Estudiante josemafla441 creado'))
            except Profesor.DoesNotExist:
                self.stdout.write(self.style.ERROR('Profesor no encontrado para asignar al estudiante'))
        else:
            self.stdout.write('Estudiante josemafla441 ya existe — omitiendo')