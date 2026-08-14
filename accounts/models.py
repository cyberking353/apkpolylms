from django.contrib.auth.models import AbstractUser
from django.db import models


def get_department_choices():
    """
    Returns department choices from the database.
    Falls back to a safe static list if the table doesn't exist yet (e.g. during first migrate).
    """
    try:
        from departments.models import Department
        choices = Department.as_choices()
        if choices:
            return choices
    except Exception:
        pass
    # Fallback used only during initial migrations before the departments table exists
    return [
        ('CS','Computer Science'),('EE','Electrical Engineering'),('ME','Mechanical Engineering'),
        ('BA','Business Administration'),('SLT','Science Laboratory Technology'),
        ('ACC','Accountancy'),('MC','Mass Communication'),('OTH','Other'),
    ]

# Keep DEPARTMENT_CHOICES as a callable alias so existing imports don't break
DEPARTMENT_CHOICES = property(lambda self: get_department_choices()) if False else get_department_choices()

ACADEMIC_LEVEL_CHOICES = [
    ('ND1',  'ND Year 1'),
    ('ND2',  'ND Year 2'),
    ('HND1', 'HND Year 1'),
    ('HND2', 'HND Year 2'),
]

# Order used when promoting a student to the next level
LEVEL_PROGRESSION = ['ND1', 'ND2', 'HND1', 'HND2']

ROLE_CHOICES = [
    ('student',  'Student'),
    ('lecturer', 'Lecturer'),
]


class Student(AbstractUser):
    """
    Account model for Al-Hikma LMS. Despite the name (kept for backward compatibility
    with the rest of the codebase, which links to this as AUTH_USER_MODEL everywhere),
    this represents BOTH students and lecturers — see `role`. Student-only and
    lecturer-only fields are simply left blank for the other role.
    """
    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default='student',
        help_text='Determines whether this account sees the student dashboard or the lecturer dashboard.'
    )

    # --- Student fields ---
    matric_number  = models.CharField(max_length=30, blank=True, null=True, unique=True)
    department     = models.CharField(
        max_length=10, choices=DEPARTMENT_CHOICES, blank=True,
        help_text='Student: their department. Lecturer: their home department.'
    )
    academic_level = models.CharField(
        max_length=10, choices=ACADEMIC_LEVEL_CHOICES, blank=True,
        help_text="Student's current study level (ND1, ND2, HND1, HND2). Assigned by admin — "
                   "this determines which courses appear on the student's dashboard. Not used for lecturers."
    )

    # --- SMS/Portal integration (single source of truth is the SMS) ---
    portal_id = models.CharField(
        max_length=64, blank=True, null=True, unique=True,
        help_text="Portal's UUID for this account (the JWT 'sub' in SSO). "
                  "Primary link key between Portal and LMS users."
    )
    current_session = models.CharField(
        max_length=20, blank=True, default='',
        help_text='School year e.g. 2025/2026, as set by the SMS/Portal.'
    )
    current_semester = models.CharField(
        max_length=1, blank=True, default='',
        help_text='Semester (1 or 2) as reported by the SMS/Portal.'
    )
    lms_access   = models.BooleanField(
        default=True, help_text='Whether the SMS allows this student to use the LMS.'
    )
    is_sms_synced = models.BooleanField(
        default=False, help_text='True when the account was created/updated by the SMS/Portal.'
    )

    # --- Lecturer fields ---
    staff_id = models.CharField(max_length=30, blank=True, help_text='Lecturer staff/employee ID.')
    title    = models.CharField(max_length=50, blank=True, help_text="e.g. 'Dr.', 'Engr.', 'Mrs.' — shown on courses they teach.")

    # --- Shared fields ---
    bio           = models.TextField(blank=True)
    avatar        = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    # XP / gamification (students only, but harmless if unused for lecturers)
    xp_points = models.PositiveIntegerField(default=0)

    # Streak tracking
    last_activity = models.DateField(blank=True, null=True)
    streak_days   = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Account'
        verbose_name_plural = 'Accounts'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"

    @property
    def is_lecturer(self):
        return self.role == 'lecturer'

    @property
    def is_student_role(self):
        return self.role == 'student'

    @property
    def display_name(self):
        """Lecturer: 'Dr. Aliyu Garba'. Student: just their full name."""
        if self.is_lecturer and self.title:
            return f"{self.title} {self.get_full_name() or self.username}"
        return self.get_full_name() or self.username

    @property
    def xp_level(self):
        """Gamification level based on XP points. Unrelated to academic_level (ND1/ND2/etc)."""
        if self.xp_points >= 5000: return 5
        if self.xp_points >= 2000: return 4
        if self.xp_points >= 1000: return 3
        if self.xp_points >= 400:  return 2
        return 1

    @property
    def initials(self):
        parts = self.get_full_name().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}".upper()
        return self.username[:2].upper()

    @property
    def next_academic_level(self):
        """What this student would be promoted to, or None if already at the top or unset."""
        if self.academic_level not in LEVEL_PROGRESSION:
            return None
        idx = LEVEL_PROGRESSION.index(self.academic_level)
        if idx + 1 < len(LEVEL_PROGRESSION):
            return LEVEL_PROGRESSION[idx + 1]
        return None

    def promote(self):
        """Move student to the next academic level. Returns True if promoted, False if already at top."""
        nxt = self.next_academic_level
        if nxt:
            self.academic_level = nxt
            self.save(update_fields=['academic_level'])
            return True
        return False
