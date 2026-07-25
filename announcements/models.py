from django.db import models
from django.conf import settings
from accounts.models import get_department_choices, ACADEMIC_LEVEL_CHOICES


AUDIENCE_CHOICES = [
    ('all',      'Everyone (all students)'),
    ('dept',     'Specific Department(s)'),
    ('level',    'Specific Level(s)'),
]

PRIORITY_CHOICES = [
    ('normal', 'Normal'),
    ('urgent', 'Urgent'),
]


class Announcement(models.Model):
    title       = models.CharField(max_length=200)
    body        = models.TextField()
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    audience    = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')
    # Comma-separated dept codes e.g. "CS,EE" — used when audience='dept'
    departments = models.CharField(max_length=100, blank=True,
                    help_text='Comma-separated dept codes e.g. CS,EE — only used when audience=dept')
    # Comma-separated levels e.g. "ND1,ND2" — used when audience='level'
    levels      = models.CharField(max_length=50, blank=True,
                    help_text='Comma-separated levels e.g. ND1,HND1 — only used when audience=level')
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                    null=True, related_name='announcements')
    created_at  = models.DateTimeField(auto_now_add=True)
    expires_at  = models.DateTimeField(null=True, blank=True,
                    help_text='Leave blank to never expire.')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def is_visible_to(self, student):
        """Check if this announcement should show for a given student."""
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.audience == 'all':
            return True
        if self.audience == 'dept':
            depts = [d.strip() for d in self.departments.split(',') if d.strip()]
            return student.department in depts
        if self.audience == 'level':
            lvls = [l.strip() for l in self.levels.split(',') if l.strip()]
            return student.academic_level in lvls
        return False

    @classmethod
    def for_student(cls, student):
        from django.utils import timezone
        from django.db.models import Q
        now = timezone.now()
        qs = cls.objects.filter(
            is_active=True
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        # Filter by audience in Python (small dataset, avoids complex SQL)
        return [a for a in qs if a.is_visible_to(student)]
