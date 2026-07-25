from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Result
from courses.models import AcademicSettings, Enrollment


@login_required
def my_results(request):
    if getattr(request.user, 'role', 'student') != 'student':
        messages.error(request, 'Results are only available for student accounts.')
        return __import__('django.shortcuts', fromlist=['redirect']).redirect('courses:lecturer_dashboard')

    settings_obj = AcademicSettings.get_current()

    # Auto-sync results on visit so they're always fresh
    Result.sync_for_student(request.user)

    results = (Result.objects
               .filter(student=request.user)
               .select_related('course')
               .order_by('-academic_year', 'semester', 'course__title'))

    # Group by academic_year + semester for display
    grouped = {}
    for r in results:
        key = f"{r.academic_year} — Semester {r.semester}"
        grouped.setdefault(key, []).append(r)

    current_key = f"{settings_obj.academic_year} — Semester {settings_obj.current_semester}"
    current_results = grouped.get(current_key, [])

    return render(request, 'results/my_results.html', {
        'current_results': current_results,
        'grouped': grouped,
        'current_key': current_key,
        'settings': settings_obj,
    })
