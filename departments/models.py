from django.db import models


class Department(models.Model):
    """
    Replaces the hardcoded DEPARTMENT_CHOICES list.
    Admin manages this from the portal — add, rename, deactivate — no code change needed.
    `code` is the short unique identifier (e.g. 'CS') used as the FK key everywhere,
    keeping backward compatibility with existing data.
    """
    portal_id = models.CharField(max_length=64, blank=True, null=True, unique=True,
                  help_text="Portal's UUID for this department (from /api/v1/sync/departments).")
    code      = models.CharField(max_length=10, unique=True,
                  help_text="Short unique code e.g. CS, EE, BA. Cannot be changed after creation.")
    name      = models.CharField(max_length=100, help_text="Full name e.g. Computer Science")
    is_active = models.BooleanField(default=True,
                  help_text="Inactive departments are hidden from dropdowns but existing data is preserved.")
    order     = models.PositiveIntegerField(default=0, help_text="Display order in dropdowns.")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @classmethod
    def as_choices(cls, include_inactive=False):
        """Returns list of (code, name) tuples for use in forms and dropdowns."""
        qs = cls.objects.all() if include_inactive else cls.objects.filter(is_active=True)
        return [(d.code, d.name) for d in qs]

    @classmethod
    def get_or_none(cls, code):
        try:
            return cls.objects.get(code=code)
        except cls.DoesNotExist:
            return None
