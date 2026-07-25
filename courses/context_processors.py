def message_counts(request):
    if not request.user.is_authenticated:
        return {}
    role = getattr(request.user, 'role', 'student')
    from .models import CourseMessage
    if role == 'student':
        count = CourseMessage.objects.filter(student=request.user, student_unread=True).count()
        return {'unread_message_count': count}
    if role == 'lecturer':
        count = CourseMessage.objects.filter(course__lecturer=request.user, status='open', lecturer_unread=True).count()
        return {'unread_message_count': count}
    return {}
