from django.db import models
from django.conf import settings
from courses.models import Module, Course


class Quiz(models.Model):
    QUIZ_TYPE = [('weekly', 'Weekly Quiz'), ('final', 'Final Exam')]

    module     = models.OneToOneField(Module, on_delete=models.CASCADE, null=True, blank=True, related_name='quiz')
    course     = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    title      = models.CharField(max_length=200)
    quiz_type  = models.CharField(max_length=10, choices=QUIZ_TYPE, default='weekly')
    time_limit_minutes = models.PositiveIntegerField(default=10)
    pass_mark  = models.PositiveIntegerField(default=50)   # percentage
    max_attempts = models.PositiveIntegerField(default=3)
    is_active  = models.BooleanField(default=True)
    show_correct_answers = models.BooleanField(default=True, help_text='Show which answers were right/wrong after submission')

    class Meta:
        ordering = ['course', 'module__week_number']
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    quiz  = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text  = models.TextField()
    order = models.PositiveIntegerField(default=0)
    marks = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"


class Choice(models.Model):
    question   = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text       = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.text[:50]}"


class QuizAttempt(models.Model):
    student    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz       = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    score      = models.FloatField(default=0)       # percentage
    passed     = models.BooleanField(default=False)
    attempt_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student} — {self.quiz} (Attempt {self.attempt_number})"

    @property
    def correct_answers(self):
        return self.answers.filter(selected_choice__is_correct=True).count()

    @property
    def total_questions(self):
        return self.quiz.question_count


class Answer(models.Model):
    attempt          = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question         = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice  = models.ForeignKey(Choice, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"Answer to {self.question}"
