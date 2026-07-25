from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='exam_status',
            field=models.CharField(
                choices=[('draft','Draft — lecturer still adding questions'),
                         ('pending','Pending Admin Approval'),
                         ('approved','Approved — admin has set the schedule')],
                default='draft', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='exam',
            name='review_note',
            field=models.TextField(blank=True, help_text='Admin note back to lecturer.'),
        ),
        migrations.AlterField(
            model_name='exam',
            name='open_at',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text="Admin sets this when approving. Students can't start before this time."
            ),
        ),
        migrations.AlterField(
            model_name='exam',
            name='close_at',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text="Admin sets this when approving. Students can't start after this time."
            ),
        ),
    ]
