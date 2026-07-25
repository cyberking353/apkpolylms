from django.db import migrations

INITIAL_DEPARTMENTS = [
    ('CS',  'Computer Science',              1),
    ('EE',  'Electrical Engineering',        2),
    ('ME',  'Mechanical Engineering',        3),
    ('BA',  'Business Administration',       4),
    ('SLT', 'Science Laboratory Technology', 5),
    ('ACC', 'Accountancy',                   6),
    ('MC',  'Mass Communication',            7),
    ('OTH', 'Other',                         8),
]

def seed_departments(apps, schema_editor):
    Department = apps.get_model('departments', 'Department')
    for code, name, order in INITIAL_DEPARTMENTS:
        Department.objects.get_or_create(code=code, defaults={'name': name, 'order': order})

def unseed_departments(apps, schema_editor):
    pass  # leave rows in place on reverse

class Migration(migrations.Migration):
    dependencies = [('departments', '0001_initial')]
    operations = [migrations.RunPython(seed_departments, unseed_departments)]
