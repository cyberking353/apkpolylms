def portal_counts(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
    if not request.path.startswith('/portal/'):
        return {}
    from courses.models import Course, CourseMessage
    from exams.models import Exam
    return {
        'pending_courses_count': Course.objects.filter(status='pending').count(),
        'pending_exams_count':   Exam.objects.filter(exam_status='pending').count(),
        'open_messages_count':   CourseMessage.objects.filter(status='open').count(),
    }
