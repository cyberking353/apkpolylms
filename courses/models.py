from django.db import models
from django.conf import settings
from django.utils import timezone
from accounts.models import get_department_choices


SEMESTER_CHOICES = [('1', 'Semester 1'), ('2', 'Semester 2')]

COURSE_STATUS_CHOICES = [
    ('draft',     'Draft'),            # lecturer is still working on it, not submitted
    ('pending',   'Pending Review'),   # lecturer submitted, waiting on admin
    ('published', 'Published'),        # admin approved — visible to students
    ('rejected',  'Rejected'),         # admin sent it back; lecturer can edit and resubmit
]


class AcademicSettings(models.Model):
    """
    Singleton row: controls the school-wide current semester.
    Admin flips this once per semester; every student's dashboard follows it automatically.
    """
    current_semester = models.CharField(max_length=1, choices=SEMESTER_CHOICES, default='1')
    academic_year    = models.CharField(max_length=20, default='2025/2026', help_text='e.g. 2025/2026')
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Academic Settings'
        verbose_name_plural = 'Academic Settings'

    def __str__(self):
        return f"{self.academic_year} — Semester {self.current_semester}"

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton: there is only ever one row
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton row should never be deleted

    @classmethod
    def get_current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AcademicSession(models.Model):
    """
    A school year (e.g. 2024/2025) pushed from the Portal via
    POST /api/v1/sync/sessions. Mirror-only data: the Portal owns sessions;
    the LMS stores them so courses/registrations can be placed in time.
    """
    portal_id   = models.CharField(max_length=64, blank=True, null=True, unique=True,
                    help_text="Portal's UUID for this session.")
    name        = models.CharField(max_length=20, unique=True, help_text="e.g. 2024/2025")
    start_date  = models.DateTimeField(blank=True, null=True)
    end_date    = models.DateTimeField(blank=True, null=True)
    is_current  = models.BooleanField(default=False,
                    help_text="Only one session is current at a time (as decided by the Portal).")
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    @classmethod
    def get_or_none(cls, name):
        try:
            return cls.objects.get(name=name)
        except cls.DoesNotExist:
            return None


class Programme(models.Model):
    """
    A study programme (e.g. National Diploma in Computer Science, code NDCSC)
    pushed from the Portal via POST /api/v1/sync/programmes. Mirror-only data.
    """
    portal_id      = models.CharField(max_length=64, blank=True, null=True, unique=True,
                        help_text="Portal's UUID for this programme.")
    code           = models.CharField(max_length=20, unique=True, help_text="e.g. NDCSC")
    name           = models.CharField(max_length=200)
    department_code = models.CharField(max_length=10, blank=True,
                        help_text="Short department code this programme belongs to (e.g. CSC).")
    programme_type = models.CharField(max_length=50, blank=True,
                        help_text="e.g. NATIONAL_DIPLOMA, HIGHER_NATIONAL_DIPLOMA.")
    duration       = models.PositiveIntegerField(default=2, help_text="Duration in years.")
    is_active      = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"

    @classmethod
    def get_or_none(cls, code):
        try:
            return cls.objects.get(code=code)
        except cls.DoesNotExist:
            return None


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, default='📚')

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class CourseDepartment(models.Model):
    """
    Through-model for Course.departments (M2M). A plain M2M would be enough, but an
    explicit through-model lets us mark which department actually "owns" the course
    (its home department) vs which ones are just borrowing it, without extra tables.
    """
    course      = models.ForeignKey('Course', on_delete=models.CASCADE)
    department  = models.CharField(max_length=10)
    is_home     = models.BooleanField(default=False, help_text="This is the course's home/owning department.")

    class Meta:
        unique_together = ('course', 'department')

    def __str__(self):
        return f"{self.course} — {self.get_department_display()}{' (home)' if self.is_home else ''}"


class Course(models.Model):
    LEVEL_CHOICES = [('ND1', 'ND Year 1'), ('ND2', 'ND Year 2'), ('HND1', 'HND Year 1'), ('HND2', 'HND Year 2')]
    SEMESTER_CHOICES = SEMESTER_CHOICES
    STATUS_CHOICES = COURSE_STATUS_CHOICES

    title       = models.CharField(max_length=200)
    slug        = models.SlugField(unique=True)
    category    = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='courses')
    description = models.TextField()
    thumbnail   = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True)
    icon        = models.CharField(max_length=10, default='📚')
    color_start = models.CharField(max_length=20, default='#0D1F3C')  # CSS gradient start
    color_end   = models.CharField(max_length=20, default='#1A3A6C')  # CSS gradient end

    # --- Academic identifiers ---
    code        = models.CharField(max_length=20, blank=True, help_text='e.g. COM101')
    credit_unit = models.PositiveIntegerField(default=3, help_text='Credit units for this course')

    # --- Portal mirror data (from POST /api/v1/sync/courses) ---
    # Raw JSON as received from the Portal. The Portal owns the catalog; the
    # LMS mirrors it here so course shells can be built and offered.
    portal_offerings = models.JSONField(default=list, blank=True,
        help_text="List of {programme_code, department_code, level, semester, is_elective} from the Portal.")
    portal_lecturers = models.JSONField(default=list, blank=True,
        help_text="List of {staff_id, first_name, last_name} from the Portal.")

    # --- Who this course is for ---
    # A course can serve more than one department at once (a "borrowed" course),
    # e.g. "Communication Skills" taken by both CS and EE. The set of departments
    # is stored via CourseDepartment (see coursedepartment_set / department_list
    # below) rather than a plain M2M field, so we can mark which one is "home".
    # An empty CourseDepartment set means "all departments at this level".

    level       = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='ND1')
    semester    = models.CharField(max_length=1, choices=SEMESTER_CHOICES, default='1')

    # --- Who teaches it ---
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='courses_taught',
        limit_choices_to={'role': 'lecturer'},
        help_text='The lecturer who created/teaches this course. Admin-created courses can leave this blank.'
    )
    # Kept for any course created directly by admin with no lecturer account attached yet.
    instructor_name_override  = models.CharField(max_length=100, blank=True)
    instructor_title_override = models.CharField(max_length=150, blank=True)

    duration_hours  = models.PositiveIntegerField(default=0)

    # --- Publishing workflow ---
    status        = models.CharField(max_length=10, choices=COURSE_STATUS_CHOICES, default='draft')
    review_note   = models.TextField(blank=True, help_text='Admin note when approving/rejecting (visible to the lecturer).')
    submitted_at  = models.DateTimeField(blank=True, null=True)
    published_at  = models.DateTimeField(blank=True, null=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_level_display()}, Sem {self.semester})"

    # --- Backward-compatible helpers (so old code/templates expecting these still work) ---
    @property
    def is_published(self):
        return self.status == 'published'

    @property
    def instructor_name(self):
        if self.lecturer_id:
            return self.lecturer.display_name
        return self.instructor_name_override or 'Al-Hikma Faculty'

    @property
    def instructor_title(self):
        if self.lecturer_id and self.lecturer.department:
            return f"{self.lecturer.get_department_display()} Department"
        return self.instructor_title_override

    @property
    def instructor_initials(self):
        if self.lecturer_id:
            return self.lecturer.initials
        parts = self.instructor_name.split()
        return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else self.instructor_name[:2].upper()

    @property
    def total_modules(self):
        return self.modules.count()

    @property
    def enrolled_count(self):
        return self.enrollments.count()

    @property
    def department_list(self):
        """List of department codes this course serves. Empty list means 'all departments at this level'."""
        return list(self.coursedepartment_set.values_list('department', flat=True))

    @property
    def home_department(self):
        cd = self.coursedepartment_set.filter(is_home=True).first()
        return cd.department if cd else None

    @property
    def is_borrowed(self):
        """True if more than one department takes this course."""
        return self.coursedepartment_set.count() > 1

    def submit_for_review(self):
        self.status = 'pending'
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitted_at'])

    def publish(self, note=''):
        self.status = 'published'
        self.published_at = timezone.now()
        self.review_note = note
        self.save(update_fields=['status', 'published_at', 'review_note'])

    def reject(self, note=''):
        self.status = 'rejected'
        self.review_note = note
        self.save(update_fields=['status', 'review_note'])

    @classmethod
    def for_student(cls, student):
        """
        Courses a given student should see right now: matching academic level,
        matching one of their assigned departments (or department-agnostic/shared
        courses with no department set at all), the school's current semester,
        and published. This is the single source of truth for
        'what shows on this student's dashboard'.
        """
        if getattr(student, 'role', 'student') != 'student':
            return cls.objects.none()
        if not student.academic_level:
            return cls.objects.none()
        current_semester = AcademicSettings.get_current().current_semester
        qs = cls.objects.filter(
            status='published',
            level=student.academic_level,
            semester=current_semester,
        ).distinct()
        if student.department:
            qs = qs.filter(
                models.Q(coursedepartment__department=student.department) | models.Q(coursedepartment__isnull=True)
            )
        return qs.distinct()

    @classmethod
    def for_lecturer(cls, lecturer):
        """Every course this lecturer created/teaches, regardless of status (draft, pending, published, rejected)."""
        return cls.objects.filter(lecturer=lecturer)


class Module(models.Model):
    course     = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title      = models.CharField(max_length=200)
    week_number = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'week_number']

    def __str__(self):
        return f"Week {self.week_number}: {self.title}"

    def is_complete_for(self, student):
        if self.lectures.exists():
            completed = set(
                LectureProgress.objects.filter(
                    student=student,
                    lecture__module=self,
                    completed=True
                ).values_list('lecture_id', flat=True)
            )
            if not all(l.id in completed for l in self.lectures.all()):
                return False

        if hasattr(self, 'quiz') and self.quiz is not None:
            from quizzes.models import QuizAttempt
            if not QuizAttempt.objects.filter(
                student=student, quiz=self.quiz,
                passed=True, submitted_at__isnull=False
            ).exists():
                return False

        return True

    @classmethod
    def bulk_completion(cls, student, course):
        """Return {module_id: True/False} for all modules in course — single query."""
        all_lectures = Lecture.objects.filter(module__course=course)
        completed_lecture_ids = set(
            LectureProgress.objects.filter(
                student=student,
                lecture__in=all_lectures,
                completed=True
            ).values_list('lecture_id', flat=True)
        )
        modules = list(course.modules.prefetch_related('lectures'))
        module_ids = [m.id for m in modules if hasattr(m, 'quiz') and m.quiz is not None]
        passed_quiz_ids = set()
        if module_ids:
            from quizzes.models import QuizAttempt
            passed_quiz_ids = set(
                QuizAttempt.objects.filter(
                    student=student,
                    quiz__module_id__in=module_ids,
                    passed=True,
                    submitted_at__isnull=False
                ).values_list('quiz__module_id', flat=True)
            )
        result = {}
        for module in modules:
            lecture_ids = [l.id for l in module.lectures.all()]
            lectures_ok = (not lecture_ids) or all(lid in completed_lecture_ids for lid in lecture_ids)
            quiz_ok = True
            if hasattr(module, 'quiz') and module.quiz is not None:
                quiz_ok = module.id in passed_quiz_ids
            result[module.id] = lectures_ok and quiz_ok
        return result


class Lecture(models.Model):
    module      = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lectures')
    title       = models.CharField(max_length=200)
    video_url   = models.URLField(blank=True)          # YouTube / external URL
    video_file  = models.FileField(upload_to='lectures/', blank=True, null=True)
    notes       = models.FileField(upload_to='notes/', blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    order       = models.PositiveIntegerField(default=0)
    is_free_preview = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    student    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course     = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed   = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student} → {self.course}"

    @property
    def progress_percent(self):
        modules = self.course.modules.all()
        total = len(modules)
        if not total:
            return 0
        done = sum(1 for v in Module.bulk_completion(self.student, self.course).values() if v)
        return int((done / total) * 100)

    @classmethod
    def sync_for_student(cls, student):
        """
        Auto-enroll a student in every course currently visible to them
        (their department + level + the school's current semester).
        Safe to call repeatedly — existing enrollments are left untouched.
        No-ops for lecturer accounts.
        """
        if getattr(student, 'role', 'student') != 'student':
            return
        if not student.academic_level:
            return
        for course in Course.for_student(student):
            cls.objects.get_or_create(student=student, course=course)


class LectureProgress(models.Model):
    student   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lecture   = models.ForeignKey(Lecture, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    watched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'lecture')

    def __str__(self):
        return f"{self.student} — {self.lecture}"


class CourseMessage(models.Model):
    """
    A support 'ticket' a student opens against a specific course — e.g. to flag a
    broken video, a wrong quiz answer, or ask the lecturer something directly.
    The actual conversation (the student's opening message + every reply after
    it) lives in CourseMessageReply; this row is just the thread header + status.
    """
    STATUS_CHOICES = [('open', 'Open'), ('resolved', 'Resolved')]

    course     = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='messages')
    student    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_messages')
    subject    = models.CharField(max_length=150)
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Simple unread flags — enough for a sidebar badge count without a full notifications system.
    lecturer_unread = models.BooleanField(default=True)
    student_unread  = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['student', 'student_unread']),
            models.Index(fields=['course', 'lecturer_unread']),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.subject} — {self.student} → {self.course}"


class CourseMessageReply(models.Model):
    thread     = models.ForeignKey(CourseMessage, on_delete=models.CASCADE, related_name='replies')
    sender     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_message_replies')
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} @ {self.created_at:%d %b %H:%M}"


class Notification(models.Model):
    recipient  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message    = models.CharField(max_length=500)
    link       = models.CharField(max_length=300, blank=True)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{'✓' if self.is_read else ' '}] {self.recipient} — {self.message[:60]}"
