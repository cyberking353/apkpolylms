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
