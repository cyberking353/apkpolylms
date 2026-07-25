from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_student_academic_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='role',
            field=models.CharField(
                choices=[('student', 'Student'), ('lecturer', 'Lecturer')],
                default='student',
                help_text='Determines whether this account sees the student dashboard or the lecturer dashboard.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='staff_id',
            field=models.CharField(blank=True, help_text='Lecturer staff/employee ID.', max_length=30),
        ),
        migrations.AddField(
            model_name='student',
            name='title',
            field=models.CharField(blank=True, help_text="e.g. 'Dr.', 'Engr.', 'Mrs.' — shown on courses they teach.", max_length=50),
        ),
        migrations.AlterField(
            model_name='student',
            name='department',
            field=models.CharField(
                blank=True,
                choices=[('CS', 'Computer Science'), ('EE', 'Electrical Engineering'), ('ME', 'Mechanical Engineering'), ('BA', 'Business Administration'), ('SLT', 'Science Laboratory Technology'), ('ACC', 'Accountancy'), ('MC', 'Mass Communication'), ('OTH', 'Other')],
                help_text='Student: their department. Lecturer: their home department.',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='student',
            name='academic_level',
            field=models.CharField(
                blank=True,
                choices=[('ND1', 'ND Year 1'), ('ND2', 'ND Year 2'), ('HND1', 'HND Year 1'), ('HND2', 'HND Year 2')],
                help_text="Student's current study level (ND1, ND2, HND1, HND2). Assigned by admin — this determines which courses appear on the student's dashboard. Not used for lecturers.",
                max_length=10,
            ),
        ),
        migrations.AlterModelOptions(
            name='student',
            options={'verbose_name': 'Account', 'verbose_name_plural': 'Accounts'},
        ),
    ]
