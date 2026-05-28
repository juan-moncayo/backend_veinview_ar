from django.core.management.base import BaseCommand
from profesor.models import ResumenPractica
from placa.models import PracticaActiva, DatosSensor


class Command(BaseCommand):
    help = 'Recalcula estadísticas de todos los resúmenes existentes con los rangos actuales'

    def handle(self, *args, **options):
        resumenes = ResumenPractica.objects.select_related('practica').all()
        total = resumenes.count()
        self.stdout.write(f"Recalculando {total} resúmenes...")

        ok = 0
        errores = 0

        for resumen in resumenes:
            try:
                datos = DatosSensor.objects.filter(practica=resumen.practica).count()
                resumen.calcular_estadisticas()
                resumen.calcular_calificacion_automatica()
                self.stdout.write(
                    f"  ✅ Práctica #{resumen.practica.id} "
                    f"— {resumen.practica.estudiante.nombre_completo} "
                    f"— {datos} datos "
                    f"— {resumen.precision_porcentaje:.1f}% "
                    f"— {resumen.calificacion}/5"
                )
                ok += 1
            except Exception as e:
                self.stdout.write(
                    f"  ❌ Práctica #{resumen.practica.id} — Error: {str(e)}"
                )
                errores += 1

        # También generar resúmenes para prácticas finalizadas sin resumen
        practicas_sin_resumen = PracticaActiva.objects.filter(
            estado='finalizada'
        ).exclude(
            id__in=ResumenPractica.objects.values_list('practica_id', flat=True)
        )

        if practicas_sin_resumen.exists():
            self.stdout.write(
                f"\nGenerando resúmenes para "
                f"{practicas_sin_resumen.count()} prácticas sin resumen..."
            )
            for practica in practicas_sin_resumen:
                try:
                    resumen = ResumenPractica.objects.create(
                        practica=practica,
                        observaciones=''
                    )
                    resumen.calcular_estadisticas()
                    resumen.calcular_calificacion_automatica()
                    self.stdout.write(
                        f"  ✅ Práctica #{practica.id} "
                        f"— {practica.estudiante.nombre_completo} "
                        f"— {resumen.precision_porcentaje:.1f}%"
                    )
                    ok += 1
                except Exception as e:
                    self.stdout.write(
                        f"  ❌ Práctica #{practica.id} — Error: {str(e)}"
                    )
                    errores += 1

        self.stdout.write(f"\n✅ Completado: {ok} OK, {errores} errores")