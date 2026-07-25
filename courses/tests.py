from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import Course, Module, Lecture, LectureProgress, Enrollment, Notification, Category
from quizzes.models import Quiz, QuizAttempt
from exams.models import Exam, ExamAttempt

User = get_user_model()


class ModuleCompletionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer', password='pass', role='lecturer')
        cls.student = User.objects.create_user(
            username='student', password='pass', role='student')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='Test Course', slug='test-course',
            description='', category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1')
        cls.module = Module.objects.create(
            course=cls.course, title='Week 1', week_number=1)
        cls.lecture1 = Lecture.objects.create(
            module=cls.module, title='L1', video_url='https://youtube.com/',
            duration_minutes=10, order=1)
        cls.lecture2 = Lecture.objects.create(
            module=cls.module, title='L2', video_url='https://youtube.com/',
            duration_minutes=10, order=2)
        Enrollment.objects.create(student=cls.student, course=cls.course)

    def test_no_lectures_no_quiz_is_complete(self):
        m = Module.objects.create(course=self.course, title='Empty', week_number=99)
        self.assertTrue(m.is_complete_for(self.student))

    def test_lectures_not_done_not_complete(self):
        self.assertFalse(self.module.is_complete_for(self.student))

    def test_lectures_done_no_quiz_is_complete(self):
        LectureProgress.objects.create(student=self.student, lecture=self.lecture1, completed=True)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture2, completed=True)
        self.assertTrue(self.module.is_complete_for(self.student))

    def test_lectures_done_quiz_not_passed_not_complete(self):
        LectureProgress.objects.create(student=self.student, lecture=self.lecture1, completed=True)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture2, completed=True)
        quiz = Quiz.objects.create(module=self.module, course=self.course, title='Q')
        QuizAttempt.objects.create(student=self.student, quiz=quiz, score=30, passed=False, submitted_at=timezone.now())
        self.assertFalse(self.module.is_complete_for(self.student))

    def test_lectures_done_quiz_passed_is_complete(self):
        LectureProgress.objects.create(student=self.student, lecture=self.lecture1, completed=True)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture2, completed=True)
        quiz = Quiz.objects.create(module=self.module, course=self.course, title='Q')
        QuizAttempt.objects.create(student=self.student, quiz=quiz, score=80, passed=True, submitted_at=timezone.now())
        self.assertTrue(self.module.is_complete_for(self.student))

    def test_bulk_completion_all_incomplete(self):
        result = Module.bulk_completion(self.student, self.course)
        self.assertFalse(result[self.module.id])

    def test_bulk_completion_all_complete(self):
        LectureProgress.objects.create(student=self.student, lecture=self.lecture1, completed=True)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture2, completed=True)
        result = Module.bulk_completion(self.student, self.course)
        self.assertTrue(result[self.module.id])

    def test_bulk_completion_with_quiz(self):
        LectureProgress.objects.create(student=self.student, lecture=self.lecture1, completed=True)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture2, completed=True)
        quiz = Quiz.objects.create(module=self.module, course=self.course, title='Q')
        result = Module.bulk_completion(self.student, self.course)
        self.assertFalse(result[self.module.id])
        QuizAttempt.objects.create(student=self.student, quiz=quiz, score=80, passed=True, submitted_at=timezone.now())
        result = Module.bulk_completion(self.student, self.course)
        self.assertTrue(result[self.module.id])

    def test_progress_percent_updates(self):
        enr = Enrollment.objects.get(student=self.student, course=self.course)
        self.assertEqual(enr.progress_percent, 0)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture1, completed=True)
        LectureProgress.objects.create(student=self.student, lecture=self.lecture2, completed=True)
        self.assertEqual(enr.progress_percent, 100)


class EnrollmentCompletionOnExamPassTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer2', password='pass', role='lecturer')
        cls.student = User.objects.create_user(
            username='student2', password='pass', role='student')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='Exam Course', slug='exam-course',
            description='', category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1')
        cls.exam = Exam.objects.create(
            course=cls.course, title='Final', time_limit_minutes=30,
            pass_mark=50)

    def setUp(self):
        self.enr = Enrollment.objects.create(student=self.student, course=self.course)

    def _create_attempt(self, should_pass):
        from exams.models import ExamAttempt, ExamQuestion, ExamChoice, ExamAnswer
        q = ExamQuestion.objects.create(exam=self.exam, text='Q1', order=1)
        correct = ExamChoice.objects.create(question=q, text='Right', is_correct=True, order=1)
        wrong = ExamChoice.objects.create(question=q, text='Wrong', is_correct=False, order=2)
        attempt = ExamAttempt.objects.create(student=self.student, exam=self.exam)
        chosen = correct if should_pass else wrong
        ExamAnswer.objects.create(attempt=attempt, question=q, selected_choice=chosen)
        from exams.views import _finalize_attempt
        _finalize_attempt(attempt, auto_submitted=False)
        attempt.refresh_from_db()
        return attempt

    def test_exam_pass_marks_enrollment_completed(self):
        self.assertFalse(self.enr.completed)
        self._create_attempt(True)
        self.enr.refresh_from_db()
        self.assertTrue(self.enr.completed)
        self.assertIsNotNone(self.enr.completed_at)

    def test_exam_fail_does_not_mark_completed(self):
        self._create_attempt(False)
        self.enr.refresh_from_db()
        self.assertFalse(self.enr.completed)


class NotificationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer3', password='pass', role='lecturer')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='Notif Course', slug='notif-course',
            description='', category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1', status='pending')

    def test_unread_by_default(self):
        note = Notification.objects.create(recipient=self.lecturer, message='Test')
        self.assertFalse(note.is_read)

    def test_marked_read(self):
        note = Notification.objects.create(recipient=self.lecturer, message='Test')
        note.is_read = True
        note.save()
        self.assertTrue(Notification.objects.filter(recipient=self.lecturer, is_read=True).exists())

    def test_ordering_most_recent_first(self):
        Notification.objects.create(recipient=self.lecturer, message='First')
        Notification.objects.create(recipient=self.lecturer, message='Second')
        notes = Notification.objects.filter(recipient=self.lecturer)
        self.assertEqual(notes.first().message, 'Second')

    def test_str_representation(self):
        note = Notification.objects.create(recipient=self.lecturer, message='Hello World')
        self.assertIn('Hello World', str(note))


class LectureProgressTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='lecturer4', password='pass', role='lecturer')
        cls.student = User.objects.create_user(
            username='student4', password='pass', role='student',
            academic_level='ND1', department='CS')
        cls.cat = Category.objects.create(name='Test')
        cls.course = Course.objects.create(
            title='Progress Course', slug='progress-course',
            description='', category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1', status='published')
        cls.module = Module.objects.create(
            course=cls.course, title='W1', week_number=1)
        cls.lecture = Lecture.objects.create(
            module=cls.module, title='L1', video_url='https://youtube.com/',
            duration_minutes=10, order=1)
        Enrollment.objects.create(student=cls.student, course=cls.course)

    def test_lecture_progress_created_on_view(self):
        self.client.force_login(self.student)
        self.client.get(reverse('courses:lecture', args=[self.course.slug, self.lecture.id]))
        self.assertTrue(LectureProgress.objects.filter(
            student=self.student, lecture=self.lecture, completed=True).exists())

    def test_dashboard_shows_progress(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse('courses:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.course.title)