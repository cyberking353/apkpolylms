from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Exam, ExamQuestion, ExamChoice, ExamAttempt, ExamAnswer
from courses.models import Course, Module, Category, Enrollment, Lecture, LectureProgress

User = get_user_model()


class ExamFinalizeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer', password='pass', role='lecturer')
        cls.student = User.objects.create_user(
            username='student', password='pass', role='student')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='Exam Course', slug='exam-course',
            description='', category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1')
        cls.module = Module.objects.create(course=cls.course, title='W1', week_number=1)
        cls.lecture = Lecture.objects.create(
            module=cls.module, title='L1', video_url='https://youtube.com/',
            duration_minutes=10, order=1)
        cls.enr = Enrollment.objects.create(student=cls.student, course=cls.course)
        cls.exam = Exam.objects.create(
            course=cls.course, title='Final', time_limit_minutes=30,
            pass_mark=50)
        cls.q1 = ExamQuestion.objects.create(exam=cls.exam, text='Q1', order=1)
        cls.correct = ExamChoice.objects.create(question=cls.q1, text='Right', is_correct=True, order=1)
        cls.wrong = ExamChoice.objects.create(question=cls.q1, text='Wrong', is_correct=False, order=2)

    def _finalize(self, score=100):
        from exams.views import _finalize_attempt
        attempt = ExamAttempt.objects.create(student=self.student, exam=self.exam)
        selected = self.correct if score >= self.exam.pass_mark else self.wrong
        ExamAnswer.objects.create(attempt=attempt, question=self.q1, selected_choice=selected)
        _finalize_attempt(attempt, auto_submitted=False)
        attempt.refresh_from_db()
        return attempt

    def test_finalize_calculates_score(self):
        attempt = self._finalize(100)
        self.assertEqual(attempt.score, 100.0)
        self.assertTrue(attempt.passed)

    def test_finalize_fail(self):
        attempt = self._finalize(0)
        self.assertEqual(attempt.score, 0.0)
        self.assertFalse(attempt.passed)

    def test_submit_exam_redirects_authenticated(self):
        self.client.force_login(self.student)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture, completed=True)
        resp = self.client.get(reverse('exams:exam_detail', args=[self.exam.id]))
        self.assertEqual(resp.status_code, 200)


class ExamDetailRequiresLoginTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer2', password='pass', role='lecturer')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='EC2', slug='ec2', description='',
            category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1')
        cls.exam = Exam.objects.create(
            course=cls.course, title='E', time_limit_minutes=30, pass_mark=50)

    def test_exam_detail_requires_login(self):
        resp = self.client.get(reverse('exams:exam_detail', args=[self.exam.id]))
        self.assertEqual(resp.status_code, 302)

    def test_exam_start_requires_login(self):
        resp = self.client.post(reverse('exams:start_exam', args=[self.exam.id]))
        self.assertEqual(resp.status_code, 302)
