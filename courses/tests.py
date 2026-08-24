from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from .models import Course, Module, Lecture, LectureProgress, Enrollment, Notification, Category, CourseDepartment, CourseMessage, CourseMessageReply
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

class StaleEnrollmentSyncTest(TestCase):
    """A course moved to a different level must disappear from students of the old level."""

    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            username='stale-student', password='pass', role='student',
            department='CSC', academic_level='HND2')
        cls.cat = Category.objects.create(name='StaleCat')

    def _course(self, slug, level):
        return Course.objects.create(
            title=f'Course {slug}', slug=slug, description='',
            category=self.cat, level=level, semester='1',
            status='published', code=f'{slug.upper()}')

    def test_level_change_removes_stale_enrollment(self):
        course = self._course('stale-one', 'HND2')
        Enrollment.sync_for_student(self.student)
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=course).exists())

        # Admin moves the course to HND1
        course.level = 'HND1'
        course.save()

        Enrollment.sync_for_student(self.student)
        self.assertFalse(Enrollment.objects.filter(student=self.student, course=course).exists())

    def test_department_change_keeps_other_dept_students(self):
        course = self._course('stale-two', 'HND2')
        CourseDepartment.objects.create(course=course, department='EE', is_home=True)
        # student is CSC; the course is now EE-only
        Enrollment.sync_for_student(self.student)
        self.assertFalse(Enrollment.objects.filter(
            student=self.student, course=course).exists())

    def test_unpublished_course_removed_from_enrollments(self):
        course = self._course('stale-three', 'HND2')
        Enrollment.sync_for_student(self.student)
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=course).exists())
        course.status = 'draft'
        course.save()
        Enrollment.sync_for_student(self.student)
        self.assertFalse(Enrollment.objects.filter(student=self.student, course=course).exists())

    def test_valid_enrollment_survives_sync(self):
        course = self._course('stale-keep', 'HND2')
        Enrollment.sync_for_student(self.student)
        Enrollment.sync_for_student(self.student)
        self.assertEqual(Enrollment.objects.filter(student=self.student).count(), 1)


class CourseDeleteWithRelationsTest(TestCase):
    """Deleting a course must succeed even with all related objects present."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='deleter', password='pass', role='student', is_staff=True)
        cls.student = User.objects.create_user(
            username='del-student', password='pass', role='student')
        cls.cat = Category.objects.create(name='DelCat')
        cls.course = Course.objects.create(
            title='Delete Me', slug='delete-me', description='',
            category=cls.cat, level='ND1', semester='1',
            status='published', code='DEL1')
        module = Module.objects.create(course=cls.course, title='M1', week_number=1)
        Lecture.objects.create(module=module, title='L1', order=1)
        quiz = Quiz.objects.create(course=cls.course, module=module, title='Q')
        from quizzes.models import Question
        Question.objects.create(quiz=quiz, text='t', order=1)
        Enrollment.objects.create(student=cls.student, course=cls.course)

    def test_delete_via_portal_view(self):
        from django.urls import reverse
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_delete', args=[self.course.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())


class CourseArchiveOnDeleteTest(TestCase):
    """Courses with academic records are archived on delete; empty ones are truly deleted."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='arch-admin', password='pass', role='student', is_staff=True)
        cls.student = User.objects.create_user(
            username='arch-student', password='pass', role='student')
        cls.cat = Category.objects.create(name='ArchCat')

    def _course(self, slug):
        return Course.objects.create(
            title=f'Arch {slug}', slug=slug, description='',
            category=self.cat, level='ND1', semester='1',
            status='published', code=slug.upper())

    def test_course_with_results_is_archived_not_deleted(self):
        from results.models import Result
        course = self._course('arch-res')
        Enrollment.objects.create(student=self.student, course=course)
        Result.objects.create(student=self.student, course=course,
                              academic_year='2025/2026', semester='1')
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_delete', args=[course.pk]))
        self.assertEqual(resp.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, 'archived')
        # records survive
        self.assertTrue(Result.objects.filter(course=course).exists())
        self.assertTrue(Enrollment.objects.filter(course=course).exists())

    def test_archived_course_hidden_from_students_and_lecturer_lists(self):
        from django.db.models import QuerySet
        course = self._course('arch-hide')
        course.status = 'archived'
        course.save()
        # student visibility query never returns archived
        self.assertNotIn(course, list(Course.for_student(self.student)))
        # lecturer lists exclude archived
        lecturer = User.objects.create_user(username='arch-lect', password='x', role='lecturer')
        course.lecturer = lecturer
        course.save()
        self.assertNotIn(course, list(Course.for_lecturer(lecturer)))

    def test_empty_course_is_still_permanently_deleted(self):
        course = self._course('arch-empty')
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_delete', args=[course.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())

    def test_restore_returns_archived_course_to_draft(self):
        course = self._course('arch-restore')
        course.status = 'archived'
        course.save()
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_restore', args=[course.pk]))
        self.assertEqual(resp.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, 'draft')

    def test_quiz_attempt_counts_as_academic_data(self):
        from quizzes.models import Quiz, Question, QuizAttempt
        course = self._course('arch-quiz')
        module = Module.objects.create(course=course, title='M1', week_number=1)
        quiz = Quiz.objects.create(course=course, module=module, title='Q')
        q = Question.objects.create(quiz=quiz, text='t', order=1)
        QuizAttempt.objects.create(student=self.student, quiz=quiz)
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_delete', args=[course.pk]))
        course.refresh_from_db()
        self.assertEqual(course.status, 'archived')


class CourseDeleteSoftSignalsTest(TestCase):
    """Watch-progress and Q&A threads do NOT force archiving — only real records do."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='soft-admin', password='pass', role='student', is_staff=True)
        cls.student = User.objects.create_user(
            username='soft-student', password='pass', role='student')
        cls.cat = Category.objects.create(name='SoftCat')

    def test_lecture_progress_alone_still_deletes(self):
        course = Course.objects.create(
            title='Soft Prog', slug='soft-prog', description='',
            category=self.cat, level='ND1', semester='1',
            status='published', code='SFT1')
        module = Module.objects.create(course=course, title='M1', week_number=1)
        lecture = Lecture.objects.create(module=module, title='L1', order=1)
        LectureProgress.objects.create(student=self.student, lecture=lecture)
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_delete', args=[course.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())

    def test_course_message_alone_still_deletes(self):
        course = Course.objects.create(
            title='Soft Msg', slug='soft-msg', description='',
            category=self.cat, level='ND1', semester='1',
            status='published', code='SFT2')
        msg = CourseMessage.objects.create(
            course=course, student=self.student, subject='Broken video')
        CourseMessageReply.objects.create(thread=msg, sender=self.student, body='+1')
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:course_delete', args=[course.pk]))
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())


class HtmxNoMessageLeakTest(TestCase):
    """htmx module/lecture actions must not queue django messages — the partial
    has no messages block, so queued ones would surface on unrelated pages."""

    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='leak-lecturer', password='pass', role='lecturer')
        cls.cat = Category.objects.create(name='LeakCat')
        cls.course = Course.objects.create(
            title='Leak Course', slug='leak-course', description='',
            category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1', status='draft')
        cls.module = Module.objects.create(course=cls.course, title='M1', week_number=1)

    def setUp(self):
        self.client.force_login(self.lecturer)
        # clear any queued messages between tests
        list(messages.get_messages(self.client))

    def _queued(self):
        return list(messages.get_messages(self.client))

    def test_htmx_module_create_leaves_no_message(self):
        resp = self.client.post(
            reverse('courses:lecturer_module_create', args=[self.course.slug]),
            {'title': 'New Module'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('New Module', resp.content.decode())   # feedback shown inline
        self.assertEqual(list(self._queued()), [])           # nothing leaked

    def test_htmx_lecture_delete_leaves_no_message(self):
        lec = Lecture.objects.create(module=self.module, title='Temp', order=1)
        resp = self.client.post(
            reverse('courses:lecturer_lecture_delete', args=[self.course.slug, lec.id]),
            HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Lecture.objects.filter(pk=lec.pk).exists())
        self.assertEqual(list(self._queued()), [])

    def test_non_htmx_fallback_still_flashes(self):
        resp = self.client.post(
            reverse('courses:lecturer_module_create', args=[self.course.slug]),
            {'title': 'Fallback Module'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        msgs = [str(m) for m in resp.context['messages']]
        self.assertTrue(any('Fallback Module' in m for m in msgs))


class LecturerProgressMonitorTest(TestCase):
    """Progress dashboard, needs-attention flags, quiz analytics and drill-down."""

    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='prog-lect', password='pass', role='lecturer')
        cls.cat = Category.objects.create(name='ProgCat')
        cls.course = Course.objects.create(
            title='Prog Course', slug='prog-course', description='',
            category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1', status='published')
        cls.m1 = Module.objects.create(course=cls.course, title='W1', week_number=1)
        cls.m2 = Module.objects.create(course=cls.course, title='W2', week_number=2)
        cls.l1 = Lecture.objects.create(module=cls.m1, title='L1', order=1)
        cls.l2 = Lecture.objects.create(module=cls.m2, title='L2', order=1)
        cls.quiz = Quiz.objects.create(course=cls.course, module=cls.m1,
                                       title='W1 Quiz')
        from quizzes.models import Question, Choice
        cls.q1 = Question.objects.create(quiz=cls.quiz, text='Q one', order=1)
        Choice.objects.create(question=cls.q1, text='Right', is_correct=True, order=1)
        Choice.objects.create(question=cls.q1, text='Wrong', is_correct=False, order=2)

        cls.eager = User.objects.create_user(
            username='eager@student', password='pass', role='student',
            matric_number='EAG/001')
        cls.stalled = User.objects.create_user(
            username='stalled@student', password='pass', role='student',
            matric_number='STL/001')
        cls.struggling = User.objects.create_user(
            username='strug@student', password='pass', role='student',
            matric_number='STR/001')
        for s in (cls.eager, cls.stalled, cls.struggling):
            Enrollment.objects.create(student=s, course=cls.course)

        # eager: watched everything
        LectureProgress.objects.create(student=cls.eager, lecture=cls.l1, completed=True)
        LectureProgress.objects.create(student=cls.eager, lecture=cls.l2, completed=True)

    def _login(self):
        self.client.force_login(self.lecturer)

    def test_progress_dashboard_shows_rows_and_stats(self):
        from django.utils import timezone
        from datetime import timedelta
        QuizAttempt.objects.create(
            student=self.eager, quiz=self.quiz, score=80, passed=True,
            attempt_number=1, submitted_at=timezone.now())
        # stalled: watched one lecture 10 days ago
        LectureProgress.objects.create(
            student=self.stalled, lecture=self.l1, completed=True,
            watched_at=timezone.now() - timedelta(days=10))

        self._login()
        resp = self.client.get(
            reverse('courses:lecturer_course_progress', args=[self.course.slug]))
        html = resp.content.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn('EAG/001', html)
        self.assertEqual(html.count('Details'), 3)

    def test_attention_tab_flags(self):
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        # eager already watched both lectures (setUpTestData) — not flagged
        # struggling: 4 attempts averaging below 50
        for i, score in enumerate([30, 40, 20, 45], start=1):
            a = QuizAttempt.objects.create(
                student=self.struggling, quiz=self.quiz, score=score,
                passed=False, attempt_number=i)
            a.started_at = now - timedelta(days=i)
            a.save()
        # stalled: watched one lecture (setUp gave none) 10 days ago
        LectureProgress.objects.create(
            student=self.stalled, lecture=self.l1, completed=True,
            watched_at=now - timedelta(days=10))

        self._login()
        resp = self.client.get(
            reverse('courses:lecturer_course_progress', args=[self.course.slug]),
            {'tab': 'attention'})
        h = resp.content.decode()
        self.assertIn('Stalled 7+ days', h)
        self.assertIn('Avg score below 50%', h)
        # eager is doing fine and must not be flagged
        self.assertNotIn('EAG/001', h.split('Flagged students')[1])

    def test_quiz_analytics_question_breakdown(self):
        now = timezone.now()
        from quizzes.models import QuizAttempt, Answer
        for i in range(4):
            attempt = QuizAttempt.objects.create(
                student=self.eager if i < 2 else self.stalled,
                quiz=self.quiz, score=60, passed=True,
                attempt_number=i + 1)
            correct_choice = self.q1.choices.get(is_correct=True)
            wrong_choice = self.q1.choices.get(is_correct=False)
            Answer.objects.create(
                attempt=attempt, question=self.q1,
                selected_choice=correct_choice if i % 2 == 0 else wrong_choice)
        del now
        self._login()
        resp = self.client.get(
            reverse('courses:lecturer_course_progress', args=[self.course.slug]),
            {'tab': 'quizzes'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '% Correct')
        self.assertContains(resp, 'Re-teach suggestion')

    def test_student_drill_down(self):
        QuizAttempt.objects.create(student=self.eager, quiz=self.quiz,
                                   score=90, passed=True, attempt_number=1)
        self._login()
        resp = self.client.get(reverse(
            'courses:lecturer_student_progress', args=[self.course.slug, self.eager.id]))
        h = resp.content.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn('100%', h)                     # eager watched everything
        self.assertIn('Watched', h)
        self.assertIn('Passed', h)

    def test_csv_export(self):
        self._login()
        resp = self.client.get(
            reverse('courses:lecturer_progress_export', args=[self.course.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        body = resp.content.decode()
        self.assertIn('Lectures Watched', body)
        self.assertIn('EAG/001', body)

    def test_htmx_partial(self):
        self._login()
        resp = self.client.get(
            reverse('courses:lecturer_course_progress', args=[self.course.slug]),
            HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b'<html', resp.content)
        self.assertContains(resp, 'progress-area')


class NudgeAndActivityTest(TestCase):
    """Reminders for flagged students + the activity feed tab."""

    @classmethod
    def setUpTestData(cls):
        cls.lecturer = User.objects.create_user(
            username='nudge-lect', password='pass', role='lecturer')
        cls.cat = Category.objects.create(name='NudgeCat')
        cls.course = Course.objects.create(
            title='Nudge Course', slug='nudge-course', description='',
            category=cls.cat, lecturer=cls.lecturer,
            level='ND1', semester='1', status='published', code='NDG101')
        cls.m1 = Module.objects.create(course=cls.course, title='W1', week_number=1)
        cls.l1 = Lecture.objects.create(module=cls.m1, title='NL1', order=1)
        cls.never = User.objects.create_user(
            username='never@student', password='pass', role='student',
            matric_number='NV/001')
        cls.active = User.objects.create_user(
            username='active@student', password='pass', role='student',
            matric_number='AC/001')
        for s in (cls.never, cls.active):
            Enrollment.objects.create(student=s, course=cls.course)

    def setUp(self):
        self.client.force_login(self.lecturer)
        list(messages.get_messages(self.client))

    def test_nudge_creates_notification(self):
        resp = self.client.post(reverse(
            'courses:lecturer_nudge_student', args=[self.course.slug, self.never.id]),
            HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        from announcements.models import Announcement  # noqa — ensure app ready
        from courses.models import Notification
        n = Notification.objects.filter(recipient=self.never).latest('created_at')
        self.assertIn('Nudge Course', n.message)
        # htmx response must not queue django messages
        self.assertEqual(list(messages.get_messages(self.client)), [])

    def test_remind_all_only_flags_flagged(self):
        from django.utils import timezone
        from datetime import timedelta
        LectureProgress.objects.create(student=self.active, lecture=self.l1, completed=True)
        LectureProgress.objects.create(
            student=self.never if False else self.never, lecture=self.l1,
            completed=True) if False else None
        # never → not_started flag; active watched everything? l2 doesn't exist; active watched l1 only
        # give active a second lecture to watch so they're complete
        l2 = Lecture.objects.create(module=self.m1, title='NL2', order=2)
        LectureProgress.objects.create(student=self.active, lecture=l2, completed=True)
        # make 'never' stalled instead by giving them an old watch
        LectureProgress.objects.create(
            student=self.never, lecture=l2, completed=True,
            watched_at=timezone.now() - timedelta(days=10))

        resp = self.client.post(reverse(
            'courses:lecturer_nudge_all', args=[self.course.slug]),
            HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        from courses.models import Notification
        recipients = set(Notification.objects.values_list('recipient_id', flat=True))
        self.assertNotIn(self.active.id, recipients)   # doing fine → not nudged

    def test_activity_tab_shows_events(self):
        from django.utils import timezone
        from quizzes.models import Quiz, Question, QuizAttempt
        quiz = Quiz.objects.create(course=self.course, module=self.m1, title='NW1')
        Question.objects.create(quiz=quiz, text='t', order=1)
        QuizAttempt.objects.create(student=self.active, quiz=quiz,
                                   score=70, passed=True, attempt_number=1,
                                   submitted_at=timezone.now())
        LectureProgress.objects.create(student=self.never, lecture=self.l1, completed=True)
        resp = self.client.get(reverse(
            'courses:lecturer_course_progress', args=[self.course.slug]),
            {'tab': 'activity'})
        h = resp.content.decode()
        self.assertContains(resp, 'Recent student activity')
        self.assertIn('watched', h)
        self.assertIn('scored 70%', h)
