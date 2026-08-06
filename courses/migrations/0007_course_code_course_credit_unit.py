from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='code',
            field=models.CharField(blank=True, help_text='e.g. COM101', max_length=20),
        ),
        migrations.AddField(
            model_name='course',
            name='credit_unit',
            field=models.PositiveIntegerField(default=3, help_text='Credit units for this course'),
        ),
    ]
