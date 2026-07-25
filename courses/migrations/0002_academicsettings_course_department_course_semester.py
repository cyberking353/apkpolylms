from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        ('accounts', '0002_student_academic_level'),
    ]

    operations = [
        migrations.CreateModel(
            name='AcademicSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_semester', models.CharField(choices=[('1', 'Semester 1'), ('2', 'Semester 2')], default='1', max_length=1)),
                ('academic_year', models.CharField(default='2025/2026', help_text='e.g. 2025/2026', max_length=20)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Academic Settings',
                'verbose_name_plural': 'Academic Settings',
            },
        ),
        migrations.AddField(
            model_name='course',
            name='department',
            field=models.CharField(
                blank=True,
                choices=[('CS', 'Computer Science'), ('EE', 'Electrical Engineering'), ('ME', 'Mechanical Engineering'), ('BA', 'Business Administration'), ('SLT', 'Science Laboratory Technology'), ('ACC', 'Accountancy'), ('MC', 'Mass Communication'), ('OTH', 'Other')],
                help_text='Department this course belongs to. Leave blank if it is a general/shared course for all departments at this level.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='semester',
            field=models.CharField(choices=[('1', 'Semester 1'), ('2', 'Semester 2')], default='1', max_length=1),
        ),
    ]
