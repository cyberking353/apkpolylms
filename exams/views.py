import secrets
import time
from functools import wraps
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db.utils import OperationalError
from .models import Exam, ExamQuestion, ExamChoice, ExamAttempt, ExamAnswer, ExamReschedule, ExamViolation
from courses.models import Enrollment, Module


def _retry_on_lock(max_retries=3, delay=0.5):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return view_func(request, *args, **kwargs)
                except OperationalError as e:
                    if 'database is locked' not in str(e):
                        raise
                    last_exc = e
                    time.sleep(delay * (attempt + 1))
            raise last_exc
        return wrapper
    return decorator


def _ensure_enrolled_or_redirect(request, course):
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.warning(request, 'You must be enrolled in this course to access its exam.')
        return redirect('courses:course_detail', slug=course.slug)
    return None


def _effective_status(exam, student):
    """
    Returns the exam status for a specific student.
    If a reschedule exists for this student, use those dates instead of the global ones.
    """
    if exam.exam_status != 'approved' or not exam.is_active:
        return 'not_approved'
    try:
        rs = ExamReschedule.objects.get(exam=exam, student=student)
        open_at, close_at = rs.open_at, rs.close_at
    except ExamReschedule.DoesNotExist:
        open_at, close_at = exam.open_at, exam.close_at

    if not open_at or not close_at:
        return 'not_approved'
    now = timezone.now()
    if now < open_at:  return 'scheduled'
    if now > close_at: return 'closed'
    return 'open'


def _status_message_for(exam, student):
    status = _effective_status(exam, student)
    if status == 'scheduled':
        try:
            rs = ExamReschedule.objects.get(exam=exam, student=student)
            return f"Your exam opens on {rs.open_at:%d %b %Y, %I:%M %p}."
        except ExamReschedule.DoesNotExist:
            return f"This exam opens on {exam.open_at:%d %b %Y, %I:%M %p}."
    if status == 'closed':
        return "This exam window has closed."
    return "This exam is not currently available."


@login_required
def exam_detail(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    course = exam.course
    redirect_resp = _ensure_enrolled_or_redirect(request, course)
    if redirect_resp:
        return redirect_resp

    existing_attempt = ExamAttempt.objects.filter(student=request.user, exam=exam).first()
    student_status = _effective_status(exam, request.user)

    module_completion = Module.bulk_completion(request.user, course)
    all_modules_complete = all(module_completion.values())

    context = {
        'exam': exam,
        'course': course,
        'attempt': existing_attempt,
        'status': student_status,
        'all_modules_complete': all_modules_complete,
    }
    return render(request, 'exams/exam_detail.html', context)


@login_required
def start_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    course = exam.course
    redirect_resp = _ensure_enrolled_or_redirect(request, course)
    if redirect_resp:
        return redirect_resp

    module_completion = Module.bulk_completion(request.user, course)
    if not all(module_completion.values()):
        messages.error(request, 'You must complete all course modules before you can take this exam.')
        return redirect('exams:exam_detail', exam_id=exam.id)

    # Entry is gated behind a JS-set hidden field, submitted via POST. A browser
    # with JavaScript disabled never sets it (and the button stays disabled), and
    # a student can't bypass this by pasting the URL directly (GET is rejected).
    # This matters because the exam's timer/proctoring/auto-submit all depend on JS.
    if request.method != 'POST' or request.POST.get('js_check') != '1':
        messages.error(request, 'JavaScript must be enabled in your browser to take this exam. '
                                 'Please enable it and try again.')
        return redirect('exams:exam_detail', exam_id=exam.id)

    student_status = _effective_status(exam, request.user)
    if student_status != 'open':
        messages.error(request, _status_message_for(exam, request.user))
        return redirect('exams:exam_detail', exam_id=exam.id)

    attempt, created = ExamAttempt.objects.get_or_create(student=request.user, exam=exam)

    if attempt.submitted_at:
        messages.info(request, 'You have already submitted this exam.')
        return redirect('exams:exam_result', attempt_id=attempt.id)

    if attempt.is_expired:
        _finalize_attempt(attempt, auto_submitted=True, terminated_reason='time_up')
        messages.warning(request, 'Time ran out for this exam. It has been submitted automatically.')
        return redirect('exams:exam_result', attempt_id=attempt.id)

    # A fresh session token is issued every time this page loads. If the student
    # already has this exam open in another tab/window, that older tab's token
    # goes stale and its heartbeat will report an invalid session (single active session).
    session_token = secrets.token_urlsafe(16)
    attempt.active_session_token = session_token
    attempt.save(update_fields=['active_session_token'])

    questions = attempt.shuffled_questions()
    return render(request, 'exams/take_exam.html', {
        'exam': exam, 'course': course, 'attempt': attempt,
        'questions': questions, 'seconds_remaining': attempt.seconds_remaining,
        'session_token': session_token,
    })


@login_required
def exam_heartbeat(request, exam_id):
    """
    Polled every few seconds while a student is on the take_exam page. Confirms
    this tab's session token is still the active one (single active session),
    and lets an already-submitted/expired attempt redirect the tab away cleanly.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)

    exam = get_object_or_404(Exam, id=exam_id)
    attempt = ExamAttempt.objects.filter(student=request.user, exam=exam).first()
    if not attempt:
        return JsonResponse({'status': 'error'}, status=404)

    if attempt.submitted_at:
        return JsonResponse({'status': 'submitted', 'redirect': reverse('exams:exam_result', args=[attempt.id])})

    if attempt.is_expired:
        _finalize_attempt(attempt, auto_submitted=True, terminated_reason='time_up')
        return JsonResponse({'status': 'submitted', 'redirect': reverse('exams:exam_result', args=[attempt.id])})

    if request.POST.get('token', '') != attempt.active_session_token:
        return JsonResponse({'status': 'invalid_session'})

    return JsonResponse({
        'status': 'ok',
        'seconds_remaining': attempt.seconds_remaining,
        'violation_count': attempt.violation_count,
    })


@login_required
def log_violation(request, exam_id):
    """Records a single proctoring event (fullscreen exit / tab switch) from the active tab."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)

    exam = get_object_or_404(Exam, id=exam_id)
    attempt = ExamAttempt.objects.filter(student=request.user, exam=exam).first()
    if not attempt or attempt.submitted_at:
        return JsonResponse({'status': 'ignored'})

    # If this event came from a tab that's no longer the active session, don't
    # count it — otherwise a stale background tab could double-count violations.
    if request.POST.get('token', '') != attempt.active_session_token:
        return JsonResponse({'status': 'stale'})

    violation_type = request.POST.get('type', '')
    if violation_type not in {c[0] for c in ExamViolation.VIOLATION_TYPES}:
        return JsonResponse({'status': 'error'}, status=400)

    ExamViolation.objects.create(attempt=attempt, violation_type=violation_type)
    attempt.violation_count += 1
    attempt.save(update_fields=['violation_count'])

    exceeded = exam.max_violations > 0 and attempt.violation_count >= exam.max_violations
    return JsonResponse({
        'status': 'ok',
        'violation_count': attempt.violation_count,
        'max_violations': exam.max_violations,
        'exceeded': exceeded,
    })


@login_required
@_retry_on_lock(max_retries=3)
def submit_exam(request, exam_id):
    if request.method != 'POST':
        return redirect('exams:exam_detail', exam_id=exam_id)

    exam = get_object_or_404(Exam, id=exam_id)
    attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam)

    if attempt.submitted_at:
        return redirect('exams:exam_result', attempt_id=attempt.id)

    violations_triggered = request.POST.get('terminated_reason') == 'violations'
    auto_submitted = attempt.is_expired or violations_triggered
    if violations_triggered:
        reason = 'violations'
    elif auto_submitted:
        reason = 'time_up'
    else:
        reason = 'normal'

    questions = exam.questions.prefetch_related('choices').all()
    for question in questions:
        choice_id = request.POST.get(f'question_{question.id}')
        selected = None
        if choice_id:
            try:
                selected = ExamChoice.objects.get(id=choice_id, question=question)
            except ExamChoice.DoesNotExist:
                selected = None
        ExamAnswer.objects.update_or_create(
            attempt=attempt, question=question, defaults={'selected_choice': selected}
        )

    _finalize_attempt(attempt, auto_submitted=auto_submitted, terminated_reason=reason)
    if reason == 'violations':
        messages.warning(request, 'Your exam was automatically submitted after repeated proctoring '
                                   'violations (exiting fullscreen / switching tabs).')
    elif auto_submitted:
        messages.warning(request, 'Time had already run out, but your answers were saved and submitted.')
    else:
        messages.success(request, 'Exam submitted successfully.')
    return redirect('exams:exam_result', attempt_id=attempt.id)


@login_required
def exam_result(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user)
    answers = attempt.answers.select_related('question', 'selected_choice').prefetch_related('question__choices')
    return render(request, 'exams/exam_result.html', {'attempt': attempt, 'answers': answers})


def _finalize_attempt(attempt, auto_submitted, terminated_reason='normal'):
    questions = attempt.exam.questions.all()
    correct = attempt.answers.filter(selected_choice__is_correct=True).count()
    total = questions.count()
    score = (correct / total * 100) if total else 0
    attempt.score = round(score, 2)
    attempt.passed = score >= attempt.exam.pass_mark
    attempt.submitted_at = timezone.now()
    attempt.auto_submitted = auto_submitted
    attempt.terminated_reason = terminated_reason
    attempt.save()

    if attempt.passed:
        Enrollment.objects.filter(
            student=attempt.student, course=attempt.exam.course
        ).update(completed=True, completed_at=timezone.now())
