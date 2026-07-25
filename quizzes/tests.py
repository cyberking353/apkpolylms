from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Quiz, Question, Choice, QuizAttempt, Answer
from courses.models import Course, Module, Category, Enrollment

User = get_user_model()


class QuizVisibilityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer', password='pass', role='lecturer')
        cls.student = User.objects.create_user(
            username='student', password='pass', role='student')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='Quiz Course', slug='quiz-course',
            description='', category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1')
        cls.module = Module.objects.create(
            course=cls.course, title='W1', week_number=1)
        cls.quiz = Quiz.objects.create(
            module=cls.module, course=cls.course, title='Week 1 Quiz',
            pass_mark=50, show_correct_answers=True)
        cls.q1 = Question.objects.create(quiz=cls.quiz, text='Q1', order=1)
        cls.correct = Choice.objects.create(question=cls.q1, text='Right', is_correct=True, order=1)
        cls.wrong = Choice.objects.create(question=cls.q1, text='Wrong', is_correct=False, order=2)
        Enrollment.objects.create(student=cls.student, course=cls.course)

    def _submit_quiz(self):
        self.client.force_login(self.student)
        attempt = QuizAttempt.objects.create(
            student=self.student, quiz=self.quiz, attempt_number=1,
            submitted_at=timezone.now(), score=100, passed=True)
        Answer.objects.create(attempt=attempt, question=self.q1, selected_choice=self.correct)
        return attempt

    def test_show_correct_answers_when_enabled(self):
        attempt = self._submit_quiz()
        resp = self.client.get(reverse('quizzes:quiz_result', args=[attempt.id]))
        self.assertContains(resp, 'Answer Review')

    def test_hide_correct_answers_when_disabled(self):
        self.quiz.show_correct_answers = False
        self.quiz.save()
        attempt = self._submit_quiz()
        resp = self.client.get(reverse('quizzes:quiz_result', args=[attempt.id]))
        self.assertNotContains(resp, 'Answer Review')

    def test_quiz_detail_shows_questions(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse('quizzes:quiz_detail', args=[self.quiz.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Q1')


class QuizAttemptModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            username='student2', password='pass', role='student')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='C', slug='c', description='', category=cls.cat,
            level='ND1', semester='1')
        cls.module = Module.objects.create(course=cls.course, title='M', week_number=1)
        cls.quiz = Quiz.objects.create(module=cls.module, course=cls.course, title='Q')

    def test_correct_answers_property(self):
        q1 = Question.objects.create(quiz=self.quiz, text='Q1', order=1)
        q2 = Question.objects.create(quiz=self.quiz, text='Q2', order=2)
        c1 = Choice.objects.create(question=q1, text='A', is_correct=True)
        w1 = Choice.objects.create(question=q1, text='B', is_correct=False)
        c2 = Choice.objects.create(question=q2, text='C', is_correct=True)
        w2 = Choice.objects.create(question=q2, text='D', is_correct=False)
        attempt = QuizAttempt.objects.create(student=self.student, quiz=self.quiz)
        Answer.objects.create(attempt=attempt, question=q1, selected_choice=c1)
        Answer.objects.create(attempt=attempt, question=q2, selected_choice=w2)
        self.assertEqual(attempt.correct_answers, 1)
        self.assertEqual(attempt.total_questions, 2)

    def test_attempt_ordering(self):
        from django.utils import timezone
        q2 = Question.objects.create(quiz=self.quiz, text='Q', order=1)
        c2 = Choice.objects.create(question=q2, text='A', is_correct=True)
        a1 = QuizAttempt.objects.create(
            student=self.student, quiz=self.quiz, attempt_number=2,
            submitted_at=timezone.now(), score=90, passed=True)
        a2 = QuizAttempt.objects.create(
            student=self.student, quiz=self.quiz, attempt_number=1,
            submitted_at=timezone.now(), score=50, passed=False)
        attempts = QuizAttempt.objects.filter(student=self.student)
        self.assertEqual(attempts.first(), a2)  # most recent first (a2 created after a1)
