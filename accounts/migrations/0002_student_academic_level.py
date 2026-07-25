from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='academic_level',
            field=models.CharField(
                blank=True,
                choices=[('ND1', 'ND Year 1'), ('ND2', 'ND Year 2'), ('HND1', 'HND Year 1'), ('HND2', 'HND Year 2')],
                help_text="Student's current study level (ND1, ND2, HND1, HND2). Assigned by admin — "
                          "this determines which courses appear on the student's dashboard.",
                max_length=10,
            ),
        ),
    ]
