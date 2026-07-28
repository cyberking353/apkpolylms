from functools import wraps
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from .models import (
    Course, CourseDepartment, Module, Lecture, Enrollment,
    LectureProgress, Category, AcademicSettings,
    CourseMessage, CourseMessageReply,
)
from quizzes.models import QuizAttempt
from exams.models import ExamAttempt


def lecturer_or_staff_required(view_func):
    """Like @login_required, but requires role == 'lecturer' OR is_staff (portal admin)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if getattr(request.user, 'role', 'student') != 'lecturer' and not request.user.is_staff:
            messages.error(request, "That page is only available to lecturer accounts.")
            return redirect('courses:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def _course_for_user(slug, user):
    """Return a course the given user is allowed to edit — lecturers by ownership, staff by role."""
    from django.shortcuts import get_object_or_404
    if user.is_staff:
        return get_object_or_404(Course, slug=slug)
    return get_object_or_404(Course, slug=slug, lecturer=user)


def lecturer_required(view_func):
    """Like @login_required, but also requires role == 'lecturer' (original, kept for compatibility)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if getattr(request.user, 'role', 'student') != 'lecturer':
            messages.error(request, "That page is only available to lecturer accounts.")
            return redirect('courses:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def student_required(view_func):
    """Like @login_required, but also requires role == 'student' (keeps lecturers off student-only pages)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if getattr(request.user, 'role', 'student') != 'student':
            messages.info(request, "That page is for students. Here's your lecturer dashboard instead.")
            return redirect('courses:lecturer_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def landing(request):
    """Public marketing page. Shows a sample of published courses, not tied to any student."""
    courses = Course.objects.filter(status='published')[:6]
    return render(request, 'courses/landing.html', {'courses': courses})


@student_required
def dashboard(request):
    """
    A student's home: only the courses matching their department + academic level +
    the school's current semester.
    """
    Enrollment.sync_for_student(request.user)
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course').order_by('course__title')
    from announcements.models import Announcement
    context = {
        'enrollments': enrollments,
        'current_semester': AcademicSettings.get_current(),
        'announcements': Announcement.for_student(request.user),
    }
    return render(request, 'courses/dashboard.html', context)


@student_required
def course_list(request):
    """'My Courses' — same scope as the dashboard (their dept + level + current semester), optionally filtered by category."""
    Enrollment.sync_for_student(request.user)
    categories = Category.objects.filter(courses__in=Course.for_student(request.user)).distinct()
    cat_slug   = request.GET.get('category')
    courses    = Course.for_student(request.user)
    if cat_slug:
        courses = courses.filter(category__slug=cat_slug)
    return render(request, 'courses/course_list.html', {
        'courses': courses, 'categories': categories, 'active_cat': cat_slug
    })


@student_required
def course_detail(request, slug):
    """
    Course preview/overview page. Only accessible if the course is currently assigned
    to this student (their department + level + current semester) — students can't
    browse into courses outside their own cohort.
    """
    course = get_object_or_404(Course, slug=slug, status='published')
    if not Course.for_student(request.user).filter(pk=course.pk).exists():
        messages.error(request, "That course isn't part of your current study plan.")
        return redirect('courses:dashboard')
    modules  = course.modules.prefetch_related('lectures')
    enrolled = Enrollment.objects.filter(student=request.user, course=course).exists()
    module_completion = Module.bulk_completion(request.user, course) if enrolled else {}
    all_modules_complete = enrolled and all(module_completion.values())
    return render(request, 'courses/course_detail.html', {
        'course': course, 'modules': modules, 'enrolled': enrolled,
        'module_completion': module_completion,
        'all_modules_complete': all_modules_complete,
    })


def _youtube_embed_url(url):
    """Convert any YouTube URL to embed format. Returns original URL if not YouTube."""
    if not url:
        return ''
    import re
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return f'https://www.youtube.com/embed/{m.group(1)}?modestbranding=1'
    return url


@student_required
def lecture_view(request, course_slug, lecture_id):
    course  = get_object_or_404(Course, slug=course_slug)
    lecture = get_object_or_404(Lecture, id=lecture_id, module__course=course)
    if not Course.for_student(request.user).filter(pk=course.pk).exists():
        messages.error(request, "That course isn't part of your current study plan.")
        return redirect('courses:dashboard')
    LectureProgress.objects.get_or_create(student=request.user, lecture=lecture,
                                          defaults={'completed': True})
    module = lecture.module
    module_lectures = list(module.lectures.all())
    lecture_index = next((i for i, l in enumerate(module_lectures) if l.id == lecture.id), 0)
    prev_lecture = module_lectures[lecture_index - 1].id if lecture_index > 0 else None
    next_lecture = module_lectures[lecture_index + 1].id if lecture_index < len(module_lectures) - 1 else None

    module_list = list(course.modules.all())
    module_index = next((i for i, m in enumerate(module_list) if m.id == module.id), 0)
    prev_module = module_list[module_index - 1] if module_index > 0 else None
    next_module = module_list[module_index + 1] if module_index < len(module_list) - 1 else None

    has_quiz = hasattr(module, 'quiz') and module.quiz is not None
    is_last_lecture = lecture_index >= len(module_lectures) - 1

    next_target_url = None
    next_target_label = None
    if is_last_lecture and has_quiz:
        next_target_url = reverse('quizzes:quiz_detail', args=[module.quiz.id])
        next_target_label = 'Take Quiz →'
    elif next_module and next_module.lectures.exists():
        next_target_url = reverse('courses:lecture', args=[course.slug, next_module.lectures.first().id])
        next_target_label = 'Next Module →'

    prev_module_lecture_id = prev_module.lectures.first().id if prev_module and prev_module.lectures.exists() else None
    next_module_lecture_id = next_module.lectures.first().id if next_module and next_module.lectures.exists() else None

    module_completion = Module.bulk_completion(request.user, course)
    all_modules_complete = all(module_completion.values())
    modules = course.modules.prefetch_related('lectures')
    return render(request, 'courses/lecture.html', {
        'course': course, 'lecture': lecture, 'modules': modules,
        'module': module, 'module_lectures': module_lectures,
        'lecture_index': lecture_index,
        'prev_lecture': prev_lecture, 'next_lecture': next_lecture,
        'prev_module_lecture_id': prev_module_lecture_id,
        'next_module_lecture_id': next_module_lecture_id,
        'next_target_url': next_target_url,
        'next_target_label': next_target_label,
        'module_completion': module_completion,
        'all_modules_complete': all_modules_complete,
        'embed_url': _youtube_embed_url(lecture.video_url),
    })


@lecturer_or_staff_required
def lecturer_course_preview(request, slug):
    """
    Lets a lecturer view their own course exactly as an enrolled student would see it —
    same template, but ownership-gated instead of enrollment-gated, and no progress
    records are created since the lecturer isn't actually a student taking the course.
    """
    course = _course_for_user(slug, request.user)
    modules = course.modules.prefetch_related('lectures')
    module_completion = Module.bulk_completion(request.user, course)
    all_modules_complete = all(module_completion.values())
    return render(request, 'courses/course_detail.html', {
        'course': course, 'modules': modules, 'enrolled': True,
        'module_completion': module_completion,
        'all_modules_complete': all_modules_complete,
        'lecturer_preview': True,
    })


@lecturer_or_staff_required
def lecturer_lecture_preview(request, slug, lecture_id):
    """Lecturer preview of a single lecture's video/notes — same template as students see."""
    course = _course_for_user(slug, request.user)
    lecture = get_object_or_404(Lecture, id=lecture_id, module__course=course)
    modules = course.modules.prefetch_related('lectures')
    module_completion = Module.bulk_completion(request.user, course)
    all_modules_complete = all(module_completion.values())
    return render(request, 'courses/lecture.html', {
        'course': course, 'lecture': lecture, 'modules': modules,
        'embed_url': _youtube_embed_url(lecture.video_url),
        'lecturer_preview': True,
        'module_completion': module_completion,
        'all_modules_complete': all_modules_complete,
    })


# ─────────────────────────────────────────────────────────────────────────
# Lecturer-facing views
# ─────────────────────────────────────────────────────────────────────────

@lecturer_required
def lecturer_dashboard(request):
    """A lecturer's home: every course they've created, regardless of status, grouped for clarity."""
    courses = Course.for_lecturer(request.user).select_related('category').order_by('-created_at')
    from .models import Notification
    context = {
        'courses': courses,
        'draft_count':     courses.filter(status='draft').count(),
        'pending_count':   courses.filter(status='pending').count(),
        'published_count': courses.filter(status='published').count(),
        'rejected_count':  courses.filter(status='rejected').count(),
        'unread_notifications': Notification.objects.filter(recipient=request.user, is_read=False).count(),
    }
    return render(request, 'courses/lecturer_dashboard.html', context)


@lecturer_required
def lecturer_course_create(request):
    """
    A lecturer starts a new course. It's always created as a draft — they fill in
    details, pick the department(s) it serves (their home department is pre-ticked,
    but they can also tick other departments to mark it as a borrowed/shared course),
    then submit it from the edit page when ready for admin review.
    """
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Please give the course a title.')
            return render(request, 'courses/lecturer_course_form.html', {
                'departments': _department_choices(), 'is_new': True, 'posted': request.POST,
                'levels': Course.LEVEL_CHOICES, 'categories': Category.objects.all(),
                'selected_departments': request.POST.getlist('departments'),
            })

        slug = _unique_slug(title)
        category_id = request.POST.get('category') or None

        course = Course.objects.create(
            title=title,
            slug=slug,
            category_id=category_id,
            description=request.POST.get('description', '').strip(),
            icon=request.POST.get('icon', '📚').strip() or '📚',
            level=request.POST.get('level', 'ND1'),
            semester=request.POST.get('semester', '1'),
            duration_hours=request.POST.get('duration_hours') or 0,
            lecturer=request.user,
            status='draft',
        )
        _save_departments(course, request.POST.getlist('departments'), request.user.department)

        messages.success(request, f'"{course.title}" created as a draft. Add modules and lectures, then submit it for review when ready.')
        return redirect('courses:lecturer_course_edit', slug=course.slug)

    return render(request, 'courses/lecturer_course_form.html', {
        'departments': _department_choices(), 'is_new': True,
        'default_department': request.user.department,
        'levels': Course.LEVEL_CHOICES,
        'categories': Category.objects.all(),
        'selected_departments': [request.user.department] if request.user.department else [],
    })


@lecturer_or_staff_required
def lecturer_course_edit(request, slug):
    """Edit a course's basic details and department assignment. Only the owning lecturer (or staff) can access this."""
    course = _course_for_user(slug, request.user)

    if request.method == 'POST':
        course.title = request.POST.get('title', '').strip() or course.title
        course.category_id = request.POST.get('category') or None
        course.description = request.POST.get('description', '').strip()
        course.icon = request.POST.get('icon', course.icon).strip() or course.icon
        course.level = request.POST.get('level', course.level)
        course.semester = request.POST.get('semester', course.semester)
        course.duration_hours = request.POST.get('duration_hours') or 0
        # Rejected courses go back to draft so the lecturer can fix and resubmit.
        # Published courses stay published — minor edits don't need re-approval.
        if course.status == 'rejected':
            course.status = 'draft'
        course.save()
        _save_departments(course, request.POST.getlist('departments'), request.user.department)

        messages.success(request, 'Course updated.')
        return redirect('courses:lecturer_course_edit', slug=course.slug)

    modules = course.modules.prefetch_related('lectures')
    return render(request, 'courses/lecturer_course_form.html', {
        'course': course, 'modules': modules, 'is_new': False,
        'departments': _department_choices(),
        'selected_departments': course.department_list,
        'levels': Course.LEVEL_CHOICES,
        'categories': Category.objects.all(),
    })


@lecturer_or_staff_required
def lecturer_course_submit(request, slug):
    """Submit a draft (or previously rejected) course for admin review."""
    course = _course_for_user(slug, request.user)
    if request.method != 'POST':
        return redirect('courses:lecturer_course_edit', slug=slug)

    if course.status not in ('draft', 'rejected'):
        messages.info(request, 'This course has already been submitted.')
    elif not course.modules.exists():
        messages.error(request, 'Add at least one module before submitting for review.')
    else:
        course.submit_for_review()
        messages.success(request, f'"{course.title}" submitted for admin review.')
    return redirect('courses:lecturer_dashboard')


@lecturer_or_staff_required
def lecturer_module_create(request, slug):
    """Quick add-a-module action from the course edit page."""
    course = _course_for_user(slug, request.user)
    feedback = None
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if title:
            next_week = (course.modules.count() or 0) + 1
            Module.objects.create(
                course=course, title=title,
                week_number=next_week, order=next_week,
                description=request.POST.get('description', '').strip(),
            )
            messages.success(request, f'Module "{title}" added.')
            feedback = ('success', f'Module "{title}" added.')
        else:
            messages.error(request, 'Module title is required.')
            feedback = ('error', 'Module title is required.')

    if request.headers.get('HX-Request'):
        modules = course.modules.prefetch_related('lectures')
        return render(request, 'courses/_modules_list.html', {'course': course, 'modules': modules, 'feedback': feedback})
    return redirect('courses:lecturer_course_edit', slug=slug)


@lecturer_or_staff_required
def lecturer_lecture_create(request, slug, module_id):
    """Quick add-a-lecture action from the course edit page."""
    course = _course_for_user(slug, request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    feedback = None
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if title:
            next_order = (module.lectures.count() or 0) + 1
            lec = Lecture.objects.create(
                module=module, title=title, order=next_order,
                video_url=request.POST.get('video_url', '').strip(),
                duration_minutes=request.POST.get('duration_minutes') or 0,
            )
            if request.FILES.get('notes'):
                lec.notes = request.FILES['notes']
                lec.save()
            messages.success(request, f'Lecture "{title}" added.')
            feedback = ('success', f'Lecture "{title}" added.')
        else:
            messages.error(request, 'Lecture title is required.')
            feedback = ('error', 'Lecture title is required.')

    if request.headers.get('HX-Request'):
        modules = course.modules.prefetch_related('lectures')
        return render(request, 'courses/_modules_list.html', {'course': course, 'modules': modules, 'feedback': feedback})
    return redirect('courses:lecturer_course_edit', slug=slug)


@lecturer_or_staff_required
def lecturer_module_edit(request, slug, module_id):
    """Edit a module's title/description. Same partial-swap pattern as create."""
    course = _course_for_user(slug, request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    feedback = None
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if title:
            module.title = title
            module.description = request.POST.get('description', '').strip()
            module.save()
            messages.success(request, f'Module "{title}" updated.')
            feedback = ('success', f'Module "{title}" updated.')
        else:
            messages.error(request, 'Module title is required.')
            feedback = ('error', 'Module title is required.')

    if request.headers.get('HX-Request'):
        modules = course.modules.prefetch_related('lectures')
        return render(request, 'courses/_modules_list.html', {'course': course, 'modules': modules, 'feedback': feedback})
    return redirect('courses:lecturer_course_edit', slug=slug)


@lecturer_or_staff_required
def lecturer_module_delete(request, slug, module_id):
    """Delete a module and all its lectures."""
    course = _course_for_user(slug, request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    feedback = None
    if request.method == 'POST':
        title = module.title
        module.delete()
        messages.success(request, f'Module "{title}" deleted.')
        feedback = ('success', f'Module "{title}" deleted.')

    if request.headers.get('HX-Request'):
        modules = course.modules.prefetch_related('lectures')
        return render(request, 'courses/_modules_list.html', {'course': course, 'modules': modules, 'feedback': feedback})
    return redirect('courses:lecturer_course_edit', slug=slug)


@lecturer_or_staff_required
def lecturer_lecture_edit(request, slug, lecture_id):
    """Edit a lecture's title/video/notes. Same partial-swap pattern as create."""
    course = _course_for_user(slug, request.user)
    lecture = get_object_or_404(Lecture, id=lecture_id, module__course=course)
    feedback = None
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if title:
            lecture.title = title
            lecture.video_url = request.POST.get('video_url', '').strip()
            lecture.duration_minutes = request.POST.get('duration_minutes') or 0
            if request.FILES.get('notes'):
                lecture.notes = request.FILES['notes']
            lecture.save()
            messages.success(request, f'Lecture "{title}" updated.')
            feedback = ('success', f'Lecture "{title}" updated.')
        else:
            messages.error(request, 'Lecture title is required.')
            feedback = ('error', 'Lecture title is required.')

    if request.headers.get('HX-Request'):
        modules = course.modules.prefetch_related('lectures')
        return render(request, 'courses/_modules_list.html', {'course': course, 'modules': modules, 'feedback': feedback})
    return redirect('courses:lecturer_course_edit', slug=slug)


@lecturer_or_staff_required
def lecturer_lecture_delete(request, slug, lecture_id):
    """Delete a single lecture."""
    course = _course_for_user(slug, request.user)
    lecture = get_object_or_404(Lecture, id=lecture_id, module__course=course)
    feedback = None
    if request.method == 'POST':
        title = lecture.title
        lecture.delete()
        messages.success(request, f'Lecture "{title}" deleted.')
        feedback = ('success', f'Lecture "{title}" deleted.')

    if request.headers.get('HX-Request'):
        modules = course.modules.prefetch_related('lectures')
        return render(request, 'courses/_modules_list.html', {'course': course, 'modules': modules, 'feedback': feedback})
    return redirect('courses:lecturer_course_edit', slug=slug)


@lecturer_or_staff_required
def lecturer_quiz_create(request, slug, module_id):
    """Create a quiz for a module (or update if one already exists)."""
    course = _course_for_user(slug, request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    from quizzes.models import Quiz
    if request.method == 'POST':
        quiz, _ = Quiz.objects.get_or_create(
            module=module,
            defaults={'course': course, 'title': f'{module.title} — Quiz', 'quiz_type': 'weekly'}
        )
        quiz.title = request.POST.get('title', quiz.title).strip() or quiz.title
        quiz.time_limit_minutes = request.POST.get('time_limit_minutes') or 10
        quiz.pass_mark = request.POST.get('pass_mark') or 50
        quiz.max_attempts = request.POST.get('max_attempts') or 3
        quiz.is_active = True
        quiz.course = course
        quiz.save()
        messages.success(request, f'Quiz "{quiz.title}" saved.')
        return redirect('courses:lecturer_quiz_manage', slug=slug, quiz_id=quiz.id)
    existing = Quiz.objects.filter(module=module).first()
    return render(request, 'courses/lecturer_quiz_form.html', {
        'course': course, 'module': module, 'quiz': existing,
    })


def _padded_quiz_questions(quiz):
    questions = list(quiz.questions.prefetch_related('choices').all())
    for q in questions:
        choices = list(q.choices.all())
        while len(choices) < 4:
            choices.append(None)
        q.padded_choices = choices[:4]
    return questions


@lecturer_or_staff_required
def lecturer_quiz_manage(request, slug, quiz_id):
    """Quiz question editor — each question is now its own independently-saved row."""
    course = _course_for_user(slug, request.user)
    from quizzes.models import Quiz
    quiz = get_object_or_404(Quiz, id=quiz_id, course=course)
    if request.method == 'POST':
        quiz.show_correct_answers = 'show_correct_answers' in request.POST
        quiz.save(update_fields=['show_correct_answers'])
        messages.success(request, 'Quiz settings updated.')
        return redirect('courses:lecturer_quiz_manage', slug=slug, quiz_id=quiz.id)
    return render(request, 'courses/lecturer_quiz_manage.html', {
        'course': course, 'quiz': quiz, 'questions': _padded_quiz_questions(quiz),
    })


def _save_quiz_question(request, quiz, question=None):
    """Shared save logic for one quiz question + its 4 choices."""
    from quizzes.models import Question, Choice
    text = request.POST.get('text', '').strip()
    if not text:
        return None, 'Question text is required.'
    if question is None:
        next_order = (quiz.questions.count() or 0) + 1
        question = Question.objects.create(quiz=quiz, text=text, order=next_order)
    else:
        question.text = text
        question.save()
    correct_idx = request.POST.get('correct')
    correct_idx = int(correct_idx) if correct_idx and correct_idx.isdigit() else None
    question.choices.all().delete()
    for i in range(4):
        ct = request.POST.get(f'choice_{i}', '').strip()
        if ct:
            Choice.objects.create(question=question, text=ct, is_correct=(correct_idx == i), order=i)
    return question, None


@lecturer_or_staff_required
def lecturer_quiz_question_add(request, slug, quiz_id):
    course = _course_for_user(slug, request.user)
    from quizzes.models import Quiz
    quiz = get_object_or_404(Quiz, id=quiz_id, course=course)
    feedback = None
    if request.method == 'POST':
        question, error = _save_quiz_question(request, quiz)
        feedback = ('error', error) if error else ('success', 'Question added.')
    if request.headers.get('HX-Request'):
        return render(request, 'courses/_quiz_questions.html', {
            'course': course, 'quiz': quiz, 'questions': _padded_quiz_questions(quiz), 'feedback': feedback,
        })
    return redirect('courses:lecturer_quiz_manage', slug=slug, quiz_id=quiz.id)


@lecturer_or_staff_required
def lecturer_quiz_question_edit(request, slug, quiz_id, question_id):
    course = _course_for_user(slug, request.user)
    from quizzes.models import Quiz, Question
    quiz = get_object_or_404(Quiz, id=quiz_id, course=course)
    question = get_object_or_404(Question, id=question_id, quiz=quiz)
    feedback = None
    if request.method == 'POST':
        question, error = _save_quiz_question(request, quiz, question=question)
        feedback = ('error', error) if error else ('success', 'Question updated.')
    if request.headers.get('HX-Request'):
        return render(request, 'courses/_quiz_questions.html', {
            'course': course, 'quiz': quiz, 'questions': _padded_quiz_questions(quiz), 'feedback': feedback,
        })
    return redirect('courses:lecturer_quiz_manage', slug=slug, quiz_id=quiz.id)


@lecturer_or_staff_required
def lecturer_quiz_question_delete(request, slug, quiz_id, question_id):
    course = _course_for_user(slug, request.user)
    from quizzes.models import Quiz, Question
    quiz = get_object_or_404(Quiz, id=quiz_id, course=course)
    question = get_object_or_404(Question, id=question_id, quiz=quiz)
    feedback = None
    if request.method == 'POST':
        question.delete()
        feedback = ('success', 'Question deleted.')
    if request.headers.get('HX-Request'):
        return render(request, 'courses/_quiz_questions.html', {
            'course': course, 'quiz': quiz, 'questions': _padded_quiz_questions(quiz), 'feedback': feedback,
        })
    return redirect('courses:lecturer_quiz_manage', slug=slug, quiz_id=quiz.id)

@lecturer_or_staff_required
def lecturer_exam_create(request, slug):
    course = _course_for_user(slug, request.user)
    from exams.models import Exam
    exam, created = Exam.objects.get_or_create(
        course=course,
        defaults={'title': f"{course.title} — Semester Exam", 'time_limit_minutes': 60, 'pass_mark': 50, 'exam_status': 'draft'}
    )
    if created:
        messages.success(request, 'Exam created. Add questions then submit for admin approval.')
    return redirect('courses:lecturer_exam_manage', slug=slug)


@lecturer_or_staff_required
def lecturer_exam_manage(request, slug):
    course = _course_for_user(slug, request.user)
    from exams.models import Exam, ExamQuestion, ExamChoice
    exam = get_object_or_404(Exam, course=course)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'submit':
            if exam.question_count < 1:
                messages.error(request, 'Add at least one question before submitting.')
            elif exam.exam_status == 'pending':
                messages.info(request, 'Already submitted and under review.')
            else:
                exam.submit_for_approval()
                messages.success(request, 'Exam submitted for admin approval. Admin will set the schedule.')
            return redirect('courses:lecturer_exam_manage', slug=slug)

        if exam.exam_status == 'pending':
            messages.error(request, 'Cannot edit while under admin review.')
            return redirect('courses:lecturer_exam_manage', slug=slug)

        exam.title = request.POST.get('title', exam.title).strip() or exam.title
        exam.time_limit_minutes = request.POST.get('time_limit_minutes') or 60
        exam.pass_mark = request.POST.get('pass_mark') or 50
        exam.instructions = request.POST.get('instructions', '').strip()
        exam.enable_proctoring = bool(request.POST.get('enable_proctoring'))
        exam.max_violations = request.POST.get('max_violations') or 3
        exam.save()

        existing_ids = {str(q.id) for q in exam.questions.all()}
        posted_keys = {k[len('question_'):] for k in request.POST if k.startswith('question_')}
        order = 1
        for rowkey in sorted(posted_keys, key=lambda k: (k.startswith('new'), k)):
            text = request.POST.get(f'question_{rowkey}', '').strip()
            if not text:
                continue
            if rowkey in existing_ids:
                q = ExamQuestion.objects.get(id=rowkey, exam=exam)
                q.text = text; q.order = order; q.save()
            else:
                q = ExamQuestion.objects.create(exam=exam, text=text, order=order)
            correct_raw = request.POST.get(f'correct_{rowkey}')
            correct_idx = int(correct_raw) if correct_raw and correct_raw.isdigit() else None
            q.choices.all().delete()
            for i in range(4):
                ct = request.POST.get(f'choice_{rowkey}_{i}', '').strip()
                if ct:
                    ExamChoice.objects.create(question=q, text=ct, is_correct=(correct_idx == i), order=i)
            order += 1
        if request.POST.getlist('delete_question'):
            ExamQuestion.objects.filter(id__in=request.POST.getlist('delete_question'), exam=exam).delete()
        messages.success(request, 'Exam questions saved.')
        return redirect('courses:lecturer_exam_manage', slug=slug)

    questions = list(exam.questions.prefetch_related('choices').all())
    for q in questions:
        choices = list(q.choices.all())
        while len(choices) < 4:
            choices.append(None)
        q.padded_choices = choices[:4]
    return render(request, 'courses/lecturer_exam_manage.html', {
        'course': course, 'exam': exam, 'questions': questions,
        'blank_rows': range(3 if not questions else 1),
        'choice_range': range(4),
        'can_edit': exam.exam_status in ('draft',),
    })


def _department_choices():
    from accounts.models import get_department_choices
    return get_department_choices()


def _unique_slug(title):
    base = slugify(title)
    slug = base
    n = 1
    while Course.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


def _save_departments(course, selected_depts, home_department):
    """
    Replace this course's CourseDepartment rows wholesale based on the posted
    checklist. The lecturer's own home department (if among those selected) is
    marked is_home=True; any others are "borrowed" departments.
    """
    CourseDepartment.objects.filter(course=course).delete()
    for dept in selected_depts:
        if dept:
            CourseDepartment.objects.create(
                course=course, department=dept, is_home=(dept == home_department)
            )


# ══════════════════════════════════════════════
# Course Messages — student ↔ lecturer support threads
# ══════════════════════════════════════════════

@student_required
def message_list(request):
    """Every thread the current student has opened, most recently active first."""
    threads = CourseMessage.objects.filter(student=request.user).select_related('course')
    return render(request, 'courses/message_list.html', {'threads': threads})


@student_required
def message_new(request, slug):
    """Start a new support thread against a course the student is enrolled in."""
    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "You can only message the instructor for a course you're enrolled in.")
        return redirect('courses:course_detail', slug=course.slug)

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        if not subject or not body:
            messages.error(request, 'Please fill in both the subject and your message.')
            return render(request, 'courses/message_new.html', {'course': course, 'subject': subject, 'body': body})
        thread = CourseMessage.objects.create(course=course, student=request.user, subject=subject)
        CourseMessageReply.objects.create(thread=thread, sender=request.user, body=body)
        messages.success(request, 'Your message has been sent to the course instructor.')
        return redirect('courses:message_thread', pk=thread.id)

    return render(request, 'courses/message_new.html', {'course': course})


def _can_view_thread(user, thread):
    if getattr(user, 'role', 'student') == 'student':
        return thread.student_id == user.id
    if getattr(user, 'role', None) == 'lecturer':
        return thread.course.lecturer_id == user.id
    return user.is_staff  # admin/portal oversight


@login_required
def message_thread(request, pk):
    """
    Shared conversation view for the student who opened it, the course's lecturer,
    and portal staff (in case a course has no lecturer yet, or one needs to step in).
    """
    thread = get_object_or_404(CourseMessage.objects.select_related('course', 'student'), pk=pk)
    if not _can_view_thread(request.user, thread):
        messages.error(request, "You don't have access to that conversation.")
        return redirect('courses:dashboard')

    is_student = thread.student_id == request.user.id

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        new_status = request.POST.get('status')
        if body:
            CourseMessageReply.objects.create(thread=thread, sender=request.user, body=body)
            if is_student:
                thread.lecturer_unread, thread.student_unread = True, False
            else:
                thread.student_unread, thread.lecturer_unread = True, False
        if new_status in ('open', 'resolved') and not is_student:
            thread.status = new_status
        thread.save()
        return redirect('courses:message_thread', pk=thread.id)

    # Viewing clears this viewer's own unread flag.
    if is_student and thread.student_unread:
        thread.student_unread = False
        thread.save(update_fields=['student_unread'])
    elif not is_student and thread.lecturer_unread:
        thread.lecturer_unread = False
        thread.save(update_fields=['lecturer_unread'])

    replies = thread.replies.select_related('sender')
    return render(request, 'courses/message_thread.html', {
        'thread': thread, 'replies': replies, 'is_student': is_student,
    })


@lecturer_or_staff_required
def lecturer_message_list(request):
    """Every support thread raised against this lecturer's own courses (or all threads for staff)."""
    if request.user.is_staff:
        threads = CourseMessage.objects.select_related('course', 'student')
    else:
        threads = CourseMessage.objects.filter(course__lecturer=request.user).select_related('course', 'student')
    status_filter = request.GET.get('status')
    if status_filter in ('open', 'resolved'):
        threads = threads.filter(status=status_filter)
    return render(request, 'courses/lecturer_message_list.html', {
        'threads': threads, 'status_filter': status_filter or 'all',
    })


@lecturer_or_staff_required
def lecturer_course_results(request, slug):
    course = _course_for_user(slug, request.user)
    enrollments = Enrollment.objects.filter(course=course).select_related('student')
    student_ids = [e.student_id for e in enrollments]
    modules = list(course.modules.all())

    modules_with_quiz = [m for m in modules if hasattr(m, 'quiz') and m.quiz is not None]
    quiz_ids = [m.quiz.id for m in modules_with_quiz]
    qid_to_mid = {m.quiz.id: m.id for m in modules_with_quiz}

    best_quiz = {}
    if student_ids and quiz_ids:
        for a in QuizAttempt.objects.filter(
            student_id__in=student_ids,
            quiz_id__in=quiz_ids,
            submitted_at__isnull=False
        ).order_by('-score'):
            key = (a.student_id, a.quiz_id)
            if key not in best_quiz:
                best_quiz[key] = a

    best_exam = {}
    if student_ids and hasattr(course, 'exam') and course.exam:
        for a in ExamAttempt.objects.filter(
            student_id__in=student_ids,
            exam=course.exam,
            submitted_at__isnull=False
        ).order_by('-score'):
            if a.student_id not in best_exam:
                best_exam[a.student_id] = a

    rows = []
    for enr in enrollments:
        sid = enr.student_id
        quiz_scores = {}
        for m in modules_with_quiz:
            a = best_quiz.get((sid, m.quiz.id))
            if a:
                quiz_scores[m.id] = a
        exam_attempt = best_exam.get(sid)

        rows.append({
            'student': enr.student,
            'quiz_scores': quiz_scores,
            'exam_attempt': exam_attempt,
        })

    return render(request, 'courses/lecturer_results.html', {
        'course': course,
        'modules': modules,
        'rows': rows,
    })


@lecturer_required
def lecturer_notifications(request):
    from .models import Notification
    notify_list = Notification.objects.filter(recipient=request.user)
    notify_list.update(is_read=True)
    return render(request, 'courses/lecturer_notifications.html', {
        'notifications': notify_list,
    })
