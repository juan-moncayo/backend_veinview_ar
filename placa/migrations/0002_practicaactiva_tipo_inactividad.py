from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('placa', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='practicaactiva',
            name='tipo',
            field=models.CharField(
                choices=[('examen', 'Examen — iniciada por profesor'),
                         ('prueba', 'Prueba — iniciada por estudiante')],
                default='examen',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='practicaactiva',
            name='ultima_actividad_sensor',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='practicaactiva',
            name='ultima_fuerza_sensor',
            field=models.FloatField(default=0.0),
        ),
    ]