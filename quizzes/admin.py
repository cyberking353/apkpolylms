from django.contrib import admin
from .models import Quiz, Question, Choice, QuizAttempt, Answer

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4

class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display  = ('title', 'course', 'quiz_type', 'time_limit_minutes', 'pass_mark', 'is_active')
    list_filter   = ('quiz_type', 'is_active')
    inlines       = [QuestionInline]

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'order', 'marks')
    inlines      = [ChoiceInline]

@admin.register(QuizAttempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'passed', 'attempt_number', 'submitted_at')
    list_filter  = ('passed', 'quiz')
