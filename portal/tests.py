from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class StudentExportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='admin', password='pass', email='admin@test.com',
            is_staff=True)
        cls.student1 = User.objects.create_user(
            username='alice', password='pass', role='student',
            first_name='Alice', last_name='Ade',
            department='CS', academic_level='ND1')
        cls.student2 = User.objects.create_user(
            username='bob', password='pass', role='student',
            first_name='Bob', last_name='Bako',
            department='EE', academic_level='ND2')

    def test_export_requires_staff(self):
        resp = self.client.get(reverse('portal:student_export'))
        self.assertEqual(resp.status_code, 302)

    def test_export_returns_excel(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('portal:student_export') + '?all=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])

    def test_export_form_page_renders(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('portal:student_export'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Department')
        self.assertContains(resp, 'Academic Level')

    def test_export_filtered_by_dept(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:student_export'), {'dept': 'CS', 'level': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])

    def test_export_filtered_by_level(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('portal:student_export'), {'dept': '', 'level': 'ND1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])


class PortalAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='admin2', password='pass', is_staff=True)
        cls.student = User.objects.create_user(
            username='stud', password='pass', role='student')

    def test_student_cannot_access_portal(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse('portal:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_admin_can_access_portal(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('portal:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_portal_login_redirects_authenticated_staff(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('portal:login'))
        self.assertEqual(resp.status_code, 302)


class ResultExportPortalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='admin3', password='pass', is_staff=True)
        from courses.models import Course, Category, AcademicSession
        from results.models import Result
        from accounts.models import Student
        cls.cat = Category.objects.create(name='Export')
        cls.session = AcademicSession.objects.create(
            portal_id='sess-uuid', name='2025/2026', is_current=True)
        cls.course = Course.objects.create(
            title='CS 101', slug='cs101', code='CS101', description='',
            category=cls.cat, level='ND1', semester='1', status='published')
        cls.student = Student.objects.create_user(
            username='s1@test.com', password='pass', role='student',
            portal_id='stu-uuid', matric_number='AH/001')
        Result.objects.create(
            student=cls.student, course=cls.course,
            academic_year='2025/2026', semester='1',
            ca_score=30, exam_score=60, ca_override=True, exam_override=True)
        cls.lecturer = Student.objects.create_user(
            username='lec1@test.com', password='pass', role='lecturer',
            portal_id='lec-uuid', staff_id='LE1', is_sms_synced=True)

    def test_requires_staff(self):
        resp = self.client.get(reverse('portal:result_export_portal'))
        self.assertEqual(resp.status_code, 302)

    def test_form_page_renders(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('portal:result_export_portal'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CS101')

    def test_post_exports_with_selected_course(self):
        from unittest.mock import patch
        self.client.force_login(self.admin)
        with patch('api.sync.export_scores_to_portal',
                   return_value=(True, {'exported': 1, 'warnings': []})) as mock:
            resp = self.client.post(
                reverse('portal:result_export_portal'),
                {'year': '2025/2026', 'sem': '1', 'course': 'CS101',
                 'staff_id': 'lec-uuid'})
        self.assertEqual(resp.status_code, 302)
        mock.assert_called_once_with('2025/2026', '1', staff_id='lec-uuid',
                                     course_code='CS101')

    def test_post_requires_valid_year_and_semester(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('portal:result_export_portal'),
            {'year': '', 'sem': '9', 'course': ''})
        self.assertEqual(resp.status_code, 302)
