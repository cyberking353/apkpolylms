import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_old_values_to_new_fields(apps, schema_editor):
    """
    Preserve existing data when restructuring Course:
    - department (single CharField) -> one CourseDepartment row (marked is_home=True),
      or no row at all if it was blank (meaning "all departments", same as before).
    - instructor_name / instructor_title -> instructor_name_override / instructor_title_override
    - is_published (True/False) -> status ('published' / 'draft')
    """
    Course = apps.get_model('courses', 'Course')
    CourseDepartment = apps.get_model('courses', 'CourseDepartment')
    db_alias = schema_editor.connection.alias

    for course in Course.objects.using(db_alias).all():
        # is_published (bool) -> status
        course.status = 'published' if course.is_published else 'draft'
        if course.is_published:
            course.published_at = course.updated_at

        # instructor_name / instructor_title -> override fields
        course.instructor_name_override = course.instructor_name or ''
        course.instructor_title_override = course.instructor_title or ''

        course.save()

        # department (single value) -> one CourseDepartment row, if it was set
        if course.department:
            CourseDepartment.objects.using(db_alias).get_or_create(
                course=course, department=course.department, defaults={'is_home': True}
            )


def reverse_noop(apps, schema_editor):
    # Reversing this migration would lose the department-list/status nuance;
    # not supported. If you need to roll back, restore from a backup instead.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_academicsettings_course_department_course_semester'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0003_student_role_and_lecturer_fields'),
    ]

    operations = [
        # 1. Add all new fields alongside the old ones first.
        migrations.AddField(
            model_name='course',
            name='status',
            field=models.CharField(
                choices=[('draft', 'Draft'), ('pending', 'Pending Review'), ('published', 'Published'), ('rejected', 'Rejected')],
                default='draft', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='review_note',
            field=models.TextField(blank=True, help_text='Admin note when approving/rejecting (visible to the lecturer).'),
        ),
        migrations.AddField(
            model_name='course',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='lecturer',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='courses_taught', to=settings.AUTH_USER_MODEL,
                help_text='The lecturer who created/teaches this course. Admin-created courses can leave this blank.',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='instructor_name_override',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='course',
            name='instructor_title_override',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.CreateModel(
            name='CourseDepartment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department', models.CharField(choices=[('CS', 'Computer Science'), ('EE', 'Electrical Engineering'), ('ME', 'Mechanical Engineering'), ('BA', 'Business Administration'), ('SLT', 'Science Laboratory Technology'), ('ACC', 'Accountancy'), ('MC', 'Mass Communication'), ('OTH', 'Other')], max_length=10)),
                ('is_home', models.BooleanField(default=False, help_text="This is the course's home/owning department.")),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
            ],
            options={
                'unique_together': {('course', 'department')},
            },
        ),

        # 2. Copy data from the old fields into the new ones, while both still exist.
        migrations.RunPython(copy_old_values_to_new_fields, reverse_noop),

        # 3. Now it's safe to drop the old fields.
        migrations.RemoveField(model_name='course', name='department'),
        migrations.RemoveField(model_name='course', name='instructor_name'),
        migrations.RemoveField(model_name='course', name='instructor_title'),
        migrations.RemoveField(model_name='course', name='instructor_initials'),
        migrations.RemoveField(model_name='course', name='is_published'),
    ]
