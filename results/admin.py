from django.contrib import admin
from django.contrib import messages
from .models import Result


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display  = ('student', 'course', 'semester', 'academic_year', 'ca_score', 'exam_score', 'total', 'grade')
    list_filter   = ('grade', 'semester', 'academic_year', 'course__level')
    search_fields = ('student__first_name', 'student__last_name', 'student__email',
                     'student__matric_number', 'course__title')
    readonly_fields = ('total', 'grade', 'computed_at')
    fieldsets = (
        (None, {'fields': ('student', 'course', 'academic_year', 'semester')}),
        ('Scores', {
            'fields': ('ca_score', 'ca_override', 'exam_score', 'exam_override'),
            'description': 'Scores are auto-calculated. Tick the override checkbox and change the value to set it manually.'
        }),
        ('Result', {'fields': ('total', 'grade', 'remark', 'computed_at')}),
    )
    actions = ['recompute_selected', 'sync_all_results']

    @admin.action(description='Recompute scores from latest quiz/exam data')
    def recompute_selected(self, request, queryset):
        count = 0
        for result in queryset:
            result.ca_override = False
            result.exam_override = False
            result.save()
            count += 1
        self.message_user(request, f"Recomputed {count} result(s).", level=messages.SUCCESS)

    @admin.action(description='Sync results for ALL enrolled students (slow on large datasets)')
    def sync_all_results(self, request, queryset):
        from accounts.models import Student
        from courses.models import Enrollment
        total = 0
        for enrollment in Enrollment.objects.select_related('student', 'course').filter(student__role='student'):
            Result.sync_for_student_course(enrollment.student, enrollment.course)
            total += 1
        self.message_user(request, f"Synced {total} result(s).", level=messages.SUCCESS)
