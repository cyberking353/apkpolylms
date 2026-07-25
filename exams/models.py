import random
from django.db import models
from django.conf import settings
from django.utils import timezone
from courses.models import Course


EXAM_STATUS_CHOICES = [
    ('draft',    'Draft — lecturer still adding questions'),
    ('pending',  'Pending Admin Approval'),
    ('approved', 'Approved — admin has set the schedule'),
]


class Exam(models.Model):
    """
    Official semester exam per course.
    Lecturer creates questions → submits for approval → admin sets schedule → students sit it.
    """
    course      = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='exam')
    title       = models.CharField(max_length=200, blank=True)
    instructions = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=60)
    pass_mark   = models.PositiveIntegerField(default=50)

    # --- Proctoring ---
    enable_proctoring = models.BooleanField(
        default=True,
        help_text='Require fullscreen + tab-switch monitoring while students take this exam.'
    )
    max_violations = models.PositiveIntegerField(
        default=3,
        help_text='Auto-submit the exam after this many proctoring violations '
                   '(tab switches / fullscreen exits). Set to 0 to disable auto-submit-on-violation.'
    )

    # Set by admin after approval — null until then
    open_at     = models.DateTimeField(null=True, blank=True,
                    help_text="Admin sets this when approving. Students can't start before this time.")
    close_at    = models.DateTimeField(null=True, blank=True,
                    help_text="Admin sets this when approving. Students can't start after this time.")

    # Workflow
    exam_status = models.CharField(max_length=10, choices=EXAM_STATUS_CHOICES, default='draft')
    review_note = models.TextField(blank=True, help_text='Admin note back to lecturer.')
    is_active   = models.BooleanField(default=True, help_text='Admin off-switch.')

    class Meta:
        ordering = ['course']

    def __str__(self):
        return self.title or f"{self.course.title} — Exam"

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def status(self):
        """What students see: scheduled / open / closed / not_approved."""
        if self.exam_status != 'approved' or not self.is_active:
            return 'not_approved'
        if not self.open_at or not self.close_at:
            return 'not_approved'
        now = timezone.now()
        if now < self.open_at:
            return 'scheduled'
        if now > self.close_at:
            return 'closed'
        return 'open'

    def time_remaining_in_window(self):
        if not self.close_at:
            return 0
        return max(0, int((self.close_at - timezone.now()).total_seconds()))

    def submit_for_approval(self):
        self.exam_status = 'pending'
        self.save(update_fields=['exam_status'])

    def approve(self, open_at, close_at, note=''):
        self.exam_status = 'approved'
        self.open_at = open_at
        self.close_at = close_at
        self.review_note = note
        self.save(update_fields=['exam_status', 'open_at', 'close_at', 'review_note'])


class ExamQuestion(models.Model):
    exam  = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    text  = models.TextField()
    order = models.PositiveIntegerField(default=0)
    marks = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"


class ExamChoice(models.Model):
    question   = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='choices')
    text       = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.text[:50]}"


class ExamAttempt(models.Model):
    TERMINATION_CHOICES = [
        ('normal',     'Manual Submit'),
        ('time_up',    'Time Expired'),
        ('violations', 'Proctoring Violations'),
    ]

    student      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exam_attempts')
    exam         = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    started_at   = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    score        = models.FloatField(default=0)
    passed       = models.BooleanField(default=False)
    auto_submitted = models.BooleanField(default=False)
    terminated_reason = models.CharField(max_length=20, choices=TERMINATION_CHOICES, blank=True)

    # --- Proctoring ---
    violation_count = models.PositiveIntegerField(default=0)
    active_session_token = models.CharField(
        max_length=40, blank=True,
        help_text='Identifies the current active browser tab/window for this attempt — '
                   'regenerated every time the exam page loads, so an older tab/window '
                   'can detect it has been superseded (single active session).'
    )

    class Meta:
        unique_together = ('student', 'exam')
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student} — {self.exam}"

    @property
    def effective_close_at(self):
        """Returns this student's close_at — reschedule overrides the global one."""
        try:
            rs = ExamReschedule.objects.get(exam=self.exam, student=self.student)
            return rs.close_at
        except ExamReschedule.DoesNotExist:
            return self.exam.close_at

    @property
    def deadline(self):
        close = self.effective_close_at
        time_limit_deadline = self.started_at + timezone.timedelta(minutes=self.exam.time_limit_minutes)
        if not close:
            return time_limit_deadline
        return min(time_limit_deadline, close)

    @property
    def seconds_remaining(self):
        if self.submitted_at:
            return 0
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    @property
    def is_expired(self):
        return not self.submitted_at and timezone.now() >= self.deadline

    @property
    def correct_answers(self):
        return self.answers.filter(selected_choice__is_correct=True).count()

    @property
    def total_questions(self):
        return self.exam.question_count

    def shuffled_questions(self):
        """
        Returns this exam's questions (with each question's choices) in an order
        that's stable for this one attempt — same order every time the student
        reloads/resumes — but different from every other student's order, since
        the shuffle is seeded off this attempt's own id. Makes a screenshot of
        "the exam" much less useful to pass along to the next student, since
        their question numbering and choice letters won't line up.
        """
        questions = list(self.exam.questions.prefetch_related('choices').all())
        rng = random.Random(self.id)
        rng.shuffle(questions)
        for question in questions:
            choices = list(question.choices.all())
            rng.shuffle(choices)
            question.shuffled_choices = choices
        return questions


class ExamAnswer(models.Model):
    attempt         = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question        = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(ExamChoice, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('attempt', 'question')


class ExamViolation(models.Model):
    """
    A single proctoring event during an exam attempt (fullscreen exit, tab switch,
    or a second tab/window opening the same attempt). Purely a log — the running
    total lives on ExamAttempt.violation_count so we don't have to COUNT() it
    on every heartbeat.
    """
    VIOLATION_TYPES = [
        ('fullscreen_exit',  'Exited Fullscreen'),
        ('tab_switch',       'Switched Tab / Window'),
        ('session_conflict', 'Opened In Another Tab/Window'),
    ]

    attempt         = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='violations')
    violation_type  = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_violation_type_display()} — {self.attempt}"


class ExamReschedule(models.Model):
    """
    Admin-only. Gives specific student(s) a different exam window than the
    global Exam.open_at / close_at. When a student starts an exam, the system
    first checks if a Reschedule row exists for them — if yes, those dates are
    used instead of the global ones.
    """
    exam        = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='reschedules')
    student     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                    related_name='exam_reschedules')
    open_at     = models.DateTimeField()
    close_at    = models.DateTimeField()
    reason      = models.TextField(blank=True, help_text='Why this student is getting a different window.')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exam', 'student')
        ordering = ['-created_at']

    def __str__(self):
        return f"Reschedule: {self.student} — {self.exam}"
