import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0002_academicsettings_course_department_course_semester'),
    ]

    operations = [
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200)),
                ('instructions', models.TextField(blank=True, help_text="Shown to the student before they start. E.g. rules, what's allowed.")),
                ('time_limit_minutes', models.PositiveIntegerField(default=60)),
                ('pass_mark', models.PositiveIntegerField(default=50, help_text='Percentage required to pass')),
                ('open_at', models.DateTimeField(help_text="Students can't see or start the exam before this time.")),
                ('close_at', models.DateTimeField(help_text="Students can't start the exam after this time.")),
                ('is_active', models.BooleanField(default=True, help_text='Admin off-switch, independent of the schedule.')),
                ('course', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='exam', to='courses.course')),
            ],
            options={
                'ordering': ['course'],
            },
        ),
        migrations.CreateModel(
            name='ExamQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('order', models.PositiveIntegerField(default=0)),
                ('marks', models.PositiveIntegerField(default=1)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='exams.exam')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='ExamChoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=300)),
                ('is_correct', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='exams.examquestion')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='ExamAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('score', models.FloatField(default=0)),
                ('passed', models.BooleanField(default=False)),
                ('auto_submitted', models.BooleanField(default=False, help_text='True if the time limit expired before the student submitted.')),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='exams.exam')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-started_at'],
                'unique_together': {('student', 'exam')},
            },
        ),
        migrations.CreateModel(
            name='ExamAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='exams.examattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='exams.examquestion')),
                ('selected_choice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='exams.examchoice')),
            ],
            options={
                'unique_together': {('attempt', 'question')},
            },
        ),
    ]
