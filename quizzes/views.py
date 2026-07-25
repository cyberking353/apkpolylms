from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import Quiz, Question, Choice, QuizAttempt, Answer
from courses.models import Enrollment, Course


@login_required
def quiz_detail(request, quiz_id):
    quiz    = get_object_or_404(Quiz, id=quiz_id, is_active=True)
    course  = quiz.course
    # Must be enrolled
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.warning(request, 'You must be enrolled to take this quiz.')
        return redirect('courses:course_detail', slug=course.slug)
    # Check attempt limit
    attempts_used = QuizAttempt.objects.filter(student=request.user, quiz=quiz,
                                                submitted_at__isnull=False).count()
    if attempts_used >= quiz.max_attempts:
        messages.error(request, f'You have used all {quiz.max_attempts} attempts for this quiz.')
        return redirect('courses:course_detail', slug=course.slug)

    questions = quiz.questions.prefetch_related('choices').all()
    context = {
        'quiz': quiz,
        'course': course,
        'questions': questions,
        'attempt_number': attempts_used + 1,
        'attempts_remaining': quiz.max_attempts - attempts_used,
    }
    return render(request, 'quizzes/quiz.html', context)


@login_required
def submit_quiz(request, quiz_id):
    if request.method != 'POST':
        return redirect('quizzes:quiz_detail', quiz_id=quiz_id)

    quiz = get_object_or_404(Quiz, id=quiz_id, is_active=True)

    attempts_used = QuizAttempt.objects.filter(
        student=request.user, quiz=quiz, submitted_at__isnull=False
    ).count()

    attempt = QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        attempt_number=attempts_used + 1,
    )

    questions = quiz.questions.prefetch_related('choices').all()
    correct   = 0

    for question in questions:
        choice_id = request.POST.get(f'question_{question.id}')
        selected  = None
        if choice_id:
            try:
                selected = Choice.objects.get(id=choice_id, question=question)
                if selected.is_correct:
                    correct += 1
            except Choice.DoesNotExist:
                pass
        Answer.objects.create(attempt=attempt, question=question, selected_choice=selected)

    total = questions.count()
    score = (correct / total * 100) if total else 0
    passed = score >= quiz.pass_mark

    attempt.score       = round(score, 2)
    attempt.passed      = passed
    attempt.submitted_at = timezone.now()
    attempt.save()

    # Award XP
    xp_gain = 20 if passed else 10
    request.user.xp_points += xp_gain
    request.user.save(update_fields=['xp_points'])

    return redirect('quizzes:quiz_result', attempt_id=attempt.id)


@login_required
def quiz_result(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user)
    answers = attempt.answers.select_related('question', 'selected_choice').prefetch_related('question__choices')

    next_module = None
    if attempt.quiz.quiz_type != 'final':
        module_list = list(attempt.quiz.course.modules.all())
        try:
            idx = next(i for i, m in enumerate(module_list) if hasattr(m, 'quiz') and m.quiz and m.quiz.id == attempt.quiz.id)
            if idx + 1 < len(module_list):
                next_module = module_list[idx + 1]
        except StopIteration:
            pass

    return render(request, 'quizzes/result.html', {
        'attempt': attempt, 'answers': answers, 'next_module': next_module,
    })
