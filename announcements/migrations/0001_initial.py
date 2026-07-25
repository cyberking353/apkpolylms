import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('priority', models.CharField(choices=[('normal','Normal'),('urgent','Urgent')], default='normal', max_length=10)),
                ('audience', models.CharField(choices=[('all','Everyone (all students)'),('dept','Specific Department(s)'),('level','Specific Level(s)')], default='all', max_length=10)),
                ('departments', models.CharField(blank=True, max_length=100, help_text='Comma-separated dept codes e.g. CS,EE')),
                ('levels', models.CharField(blank=True, max_length=50, help_text='Comma-separated levels e.g. ND1,HND1')),
                ('is_active', models.BooleanField(default=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True, help_text='Leave blank to never expire.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='announcements', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
