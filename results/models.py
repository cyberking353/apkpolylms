from django.db import models
from django.conf import settings
from courses.models import Course, AcademicSettings


GRADE_CHOICES = [
    ('A', 'A — Distinction (70–100)'),
    ('B', 'B — Credit (60–69)'),
    ('C', 'C — Merit (50–59)'),
    ('D', 'D — Pass (45–49)'),
    ('E', 'E — Pass (40–44)'),
    ('F', 'F — Fail (0–39)'),
]


def score_to_grade(total):
    if total >= 70: return 'A'
    if total >= 60: return 'B'
    if total >= 50: return 'C'
    if total >= 45: return 'D'
    if total >= 40: return 'E'
    return 'F'


class Result(models.Model):
    """
    One row per student per course per semester.
    CA comes from quiz averages (auto-calculated), exam from ExamAttempt (auto-calculated).
    Admin can override either component manually if needed.
    """
    student         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='results')
    course          = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='results')
    academic_year   = models.CharField(max_length=20)
    semester        = models.CharField(max_length=1, choices=[('1','Semester 1'),('2','Semester 2')])

    # CA out of 40 — auto-calculated from quiz attempts, but admin can override
    ca_score        = models.FloatField(default=0, help_text='Out of 40. Auto-calculated from weekly quiz averages.')
    ca_override     = models.BooleanField(default=False, help_text='Tick if you manually set ca_score.')

    # Exam out of 60 — auto-calculated from ExamAttempt, but admin can override
    exam_score      = models.FloatField(default=0, help_text='Out of 60. Auto-calculated from the official exam attempt.')
    exam_override   = models.BooleanField(default=False, help_text='Tick if you manually set exam_score.')

    # Computed on save
    total           = models.FloatField(default=0, help_text='CA + Exam, out of 100.')
    grade           = models.CharField(max_length=1, choices=GRADE_CHOICES, default='F')

    remark          = models.TextField(blank=True, help_text='Optional admin remark shown to student.')
    computed_at     = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_year', 'semester')
        ordering = ['course__title']

    def __str__(self):
        return f"{self.student} — {self.course.title} — {self.grade}"

    def compute(self):
        """Recalculate CA and/or exam score from live data, then derive total and grade."""
        if not self.ca_override:
            self.ca_score = round(self._calc_ca(), 2)
        if not self.exam_override:
            self.exam_score = round(self._calc_exam(), 2)
        self.total = round(self.ca_score + self.exam_score, 2)
        self.grade = score_to_grade(self.total)

    def save(self, *args, **kwargs):
        self.compute()
        super().save(*args, **kwargs)

    def _calc_ca(self):
        """
        Average the student's best quiz attempt per weekly quiz in this course,
        then scale to 40. Unattempted quizzes count as 0 — the denominator is
        always the TOTAL number of quizzes in the course, not just the ones the
        student has attempted, so a student who skipped a quiz doesn't get
        scored as if it never existed.
        """
        from quizzes.models import QuizAttempt
        quizzes = self.course.quizzes.filter(quiz_type='weekly', is_active=True)
        total_quizzes = quizzes.count()
        if not total_quizzes:
            return 0
        total_pct = 0
        for quiz in quizzes:
            best = (QuizAttempt.objects
                    .filter(student=self.student, quiz=quiz, submitted_at__isnull=False)
                    .order_by('-score').first())
            total_pct += best.score if best else 0
        avg_pct = total_pct / total_quizzes
        return (avg_pct / 100) * 40

    def _calc_exam(self):
        """Scale the student's exam attempt score (%) to 60 marks."""
        from exams.models import ExamAttempt
        try:
            attempt = ExamAttempt.objects.get(
                student=self.student,
                exam__course=self.course,
                submitted_at__isnull=False,
            )
            return (attempt.score / 100) * 60
        except ExamAttempt.DoesNotExist:
            return 0

    @classmethod
    def sync_for_student_course(cls, student, course):
        """Create or refresh the Result row for this student+course using current semester."""
        settings_obj = AcademicSettings.get_current()
        result, _ = cls.objects.get_or_create(
            student=student, course=course,
            academic_year=settings_obj.academic_year,
            semester=settings_obj.current_semester,
        )
        result.save()  # triggers compute()
        return result

    @classmethod
    def sync_for_student(cls, student):
        """Refresh results for every course the student is enrolled in."""
        from courses.models import Enrollment
        for enrollment in Enrollment.objects.filter(student=student).select_related('course'):
            cls.sync_for_student_course(student, enrollment.course)
