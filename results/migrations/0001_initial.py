import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0003_lecturer_departments_status_workflow'),
    ]

    operations = [
        migrations.CreateModel(
            name='Result',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_year', models.CharField(max_length=20)),
                ('semester', models.CharField(choices=[('1', 'Semester 1'), ('2', 'Semester 2')], max_length=1)),
                ('ca_score', models.FloatField(default=0, help_text='Out of 40. Auto-calculated from weekly quiz averages.')),
                ('ca_override', models.BooleanField(default=False, help_text='Tick if you manually set ca_score.')),
                ('exam_score', models.FloatField(default=0, help_text='Out of 60. Auto-calculated from the official exam attempt.')),
                ('exam_override', models.BooleanField(default=False, help_text='Tick if you manually set exam_score.')),
                ('total', models.FloatField(default=0, help_text='CA + Exam, out of 100.')),
                ('grade', models.CharField(choices=[('A', 'A — Distinction (70–100)'), ('B', 'B — Credit (60–69)'), ('C', 'C — Merit (50–59)'), ('D', 'D — Pass (45–49)'), ('E', 'E — Pass (40–44)'), ('F', 'F — Fail (0–39)')], default='F', max_length=1)),
                ('remark', models.TextField(blank=True, help_text='Optional admin remark shown to student.')),
                ('computed_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='courses.course')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['course__title'],
                'unique_together': {('student', 'course', 'academic_year', 'semester')},
            },
        ),
    ]
