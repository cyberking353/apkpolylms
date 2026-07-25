from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import (
    AcademicSettings, Category, Course, CourseDepartment,
    Module, Lecture, Enrollment, LectureProgress,
)


@admin.register(AcademicSettings)
class AcademicSettingsAdmin(admin.ModelAdmin):
    """
    Singleton control panel: change the current semester here and every
    student's dashboard updates immediately (no per-student action needed).
    """
    list_display = ('academic_year', 'current_semester', 'updated_at')

    def has_add_permission(self, request):
        return not AcademicSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.message_user(
            request,
            f"Current semester is now Semester {obj.current_semester} ({obj.academic_year}). "
            f"Student dashboards will reflect this immediately.",
            level=messages.SUCCESS
        )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon')
    prepopulated_fields = {'slug': ('name',)}


class LectureInline(admin.TabularInline):
    model = Lecture
    extra = 1


class ModuleInline(admin.StackedInline):
    model = Module
    extra = 1


class CourseDepartmentInline(admin.TabularInline):
    """
    The 'checklist' for which departments take this course. Add one row per
    department; tick is_home for whichever department actually owns/created it.
    Leave this empty entirely for a course shared by every department at that level.
    """
    model = CourseDepartment
    extra = 2
    verbose_name = 'Department'
    verbose_name_plural = 'Departments taking this course (leave empty = all departments)'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = ('title', 'department_summary', 'level', 'semester', 'lecturer', 'status', 'enrolled_count')
    list_filter   = ('status', 'level', 'semester', 'category')
    search_fields = ('title', 'lecturer__first_name', 'lecturer__last_name', 'instructor_name_override')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CourseDepartmentInline, ModuleInline]
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'category', 'description', 'thumbnail', 'icon', 'color_start', 'color_end')}),
        ('Who is this course for?', {
            'fields': ('level', 'semester'),
            'description': 'Use the "Departments taking this course" section below to pick which department(s) '
                            'see this course. Leave it empty for a course shared by every department at this level.'
        }),
        ('Who teaches it?', {
            'fields': ('lecturer', 'instructor_name_override', 'instructor_title_override'),
            'description': 'Pick a Lecturer account if one exists. The override fields are only used as a fallback '
                            'when no lecturer account is linked.'
        }),
        ('Publishing', {
            'fields': ('status', 'review_note', 'duration_hours'),
            'description': 'A course is only visible to students once status is "Published". '
                            'Lecturer-submitted courses arrive here as "Pending Review".'
        }),
    )
    readonly_fields = ('submitted_at', 'published_at')

    actions = ['publish_courses', 'reject_courses', 'sync_enrollments_for_matching_students']

    def department_summary(self, obj):
        depts = obj.department_list
        if not depts:
            return '— (all departments)'
        return ', '.join(depts)
    department_summary.short_description = 'Departments'

    @admin.action(description='✓ Publish selected courses (visible to students immediately)')
    def publish_courses(self, request, queryset):
        count = 0
        for course in queryset.exclude(status='published'):
            course.publish()
            count += 1
        self.message_user(request, f"Published {count} course(s).", level=messages.SUCCESS)

    @admin.action(description='✗ Reject selected courses (sends back to lecturer as Rejected)')
    def reject_courses(self, request, queryset):
        count = queryset.exclude(status='rejected').update(status='rejected')
        self.message_user(request, f"Rejected {count} course(s).", level=messages.WARNING)

    @admin.action(description='Re-sync enrollments for all matching students (department + level + semester)')
    def sync_enrollments_for_matching_students(self, request, queryset):
        from accounts.models import Student
        total = 0
        for course in queryset.filter(status='published'):
            students = Student.objects.filter(role='student', academic_level=course.level)
            depts = course.department_list
            if depts:
                students = students.filter(department__in=depts)
            for student in students:
                _, created = Enrollment.objects.get_or_create(student=student, course=course)
                if created:
                    total += 1
        self.message_user(request, f"Created {total} new enrollment(s) for matching students.", level=messages.SUCCESS)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'week_number', 'order')
    inlines = [LectureInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'completed')
    list_filter  = ('completed', 'course__level', 'course__semester', 'course')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'course__title')
