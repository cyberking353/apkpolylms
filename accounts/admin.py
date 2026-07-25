from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from .models import Student


@admin.register(Student)
class StudentAdmin(UserAdmin):
    list_display  = ('email', 'first_name', 'last_name', 'role', 'department', 'academic_level', 'is_active', 'is_staff')
    list_filter   = ('role', 'department', 'academic_level', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'matric_number', 'staff_id')
    ordering      = ('-date_joined',)

    fieldsets = UserAdmin.fieldsets + (
        ('Account Type', {
            'fields': ('role',),
            'description': "Student accounts use Department + Academic Level below to determine which courses "
                            "they see. Lecturer accounts use Department as their 'home department' and can create "
                            "their own courses (subject to admin approval)."
        }),
        ('Student Profile', {
            'fields': ('matric_number', 'academic_level'),
        }),
        ('Lecturer Profile', {
            'fields': ('staff_id', 'title'),
        }),
        ('Shared Profile', {
            'fields': ('department', 'bio', 'avatar', 'xp_points', 'streak_days'),
        }),
    )

    # Make the key fields settable right when admin creates a new account, not just after the fact.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
        ('Account Type & Profile', {
            'classes': ('wide',),
            'fields': ('role', 'department', 'academic_level', 'matric_number', 'staff_id', 'title'),
            'description': "For a Student: set Department + Academic Level so the right courses appear immediately. "
                            "For a Lecturer: set Department (their home department), staff ID, and title."
        }),
    )

    actions = ['promote_selected_students']

    @admin.action(description='Promote selected students to their next academic level')
    def promote_selected_students(self, request, queryset):
        students = queryset.filter(role='student')
        promoted, at_top, unset = 0, 0, 0
        for student in students:
            if not student.academic_level:
                unset += 1
                continue
            if student.promote():
                promoted += 1
            else:
                at_top += 1

        if promoted:
            self.message_user(request, f"Promoted {promoted} student(s) to their next level.", level=messages.SUCCESS)
        if at_top:
            self.message_user(request, f"{at_top} student(s) are already at the highest level (HND2) and were not changed.", level=messages.WARNING)
        if unset:
            self.message_user(request, f"{unset} student(s) have no academic level set and were skipped.", level=messages.WARNING)

    def save_model(self, request, obj, form, change):
        """After a student's department/level is set or changed, auto-enroll them in the matching courses."""
        super().save_model(request, obj, form, change)
        if obj.role == 'student':
            from courses.models import Enrollment
            Enrollment.sync_for_student(obj)
