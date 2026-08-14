import json
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Student
from courses.models import (
    AcademicSettings, AcademicSession, Course, CourseDepartment, Enrollment,
    Programme,
)
from departments.models import Department

from .sso import sign_jwt

TEST_TOKEN = 'test-lms-api-token'
TEST_SECRET = 'test-sso-secret'

AUTH = {'HTTP_AUTHORIZATION': f'Bearer {TEST_TOKEN}'}


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class SyncAuthTests(TestCase):
    def test_missing_token_is_401(self):
        resp = self.client.post(reverse('api:sync_students'),
                                data=json.dumps({}), content_type='application/json')
        self.assertEqual(resp.status_code, 401)

    def test_wrong_token_is_401(self):
        resp = self.client.post(
            reverse('api:sync_students'), data=json.dumps({}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer wrong-token')
        self.assertEqual(resp.status_code, 401)


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class StudentSyncTests(TestCase):
    URL = '/api/v1/sync/students'

    def _post(self, payload):
        return self.client.post(self.URL, data=json.dumps(payload),
                                content_type='application/json', **AUTH)

    def test_create_student(self):
        resp = self._post({
            'matric_number': 'AHP/ND/CSC/24/0042',
            'first_name': 'Amina', 'last_name': 'Bello',
            'email': 'amina@example.com', 'department_code': 'CSC',
            'academic_level': 'ND1', 'current_session': '2025/2026',
            'semester': '1', 'status': 'active', 'lms_access': True,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['created'])
        student = Student.objects.get(matric_number='AHP/ND/CSC/24/0042')
        self.assertEqual(student.email, 'amina@example.com')
        self.assertTrue(student.is_sms_synced)
        self.assertFalse(student.has_usable_password())

    def test_create_is_idempotent(self):
        payload = {
            'matric_number': 'AHP/ND/CSC/24/0042',
            'first_name': 'Amina', 'last_name': 'Bello',
            'email': 'amina@example.com', 'academic_level': 'ND1',
        }
        self._post(payload)
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['created'])
        self.assertEqual(Student.objects.filter(matric_number='AHP/ND/CSC/24/0042').count(), 1)

    def test_update_fields_on_resync(self):
        self._post({'matric_number': 'M1', 'first_name': 'A', 'last_name': 'B',
                    'email': 'a@example.com'})
        self._post({'matric_number': 'M1', 'first_name': 'Amira', 'last_name': 'B',
                    'email': 'a@example.com'})
        student = Student.objects.get(matric_number='M1')
        self.assertEqual(student.first_name, 'Amira')

    def test_missing_matric_is_400(self):
        resp = self._post({'email': 'x@example.com'})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_department_warns_but_stores(self):
        resp = self._post({'matric_number': 'M2', 'email': 'm2@example.com',
                           'department_code': 'ZZZ'})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()['warning'])
        self.assertEqual(Student.objects.get(matric_number='M2').department, 'ZZZ')

    def test_inactive_status_deactivates(self):
        self._post({'matric_number': 'M3', 'email': 'm3@example.com',
                    'status': 'suspended'})
        self.assertFalse(Student.objects.get(matric_number='M3').is_active)

    def test_lms_access_false_blocks(self):
        self._post({'matric_number': 'M4', 'email': 'm4@example.com',
                    'lms_access': False})
        self.assertFalse(Student.objects.get(matric_number='M4').lms_access)


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class DepartmentSyncTests(TestCase):
    def test_create_and_update(self):
        url = reverse('api:sync_departments')
        resp = self.client.post(url, data=json.dumps({
            'id': 'dept-uuid', 'code': 'CSC', 'name': 'Computer Science',
            'is_active': True,
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        dept = Department.objects.get(code='CSC')
        self.assertEqual(dept.name, 'Computer Science')
        self.assertEqual(dept.portal_id, 'dept-uuid')

        self.client.post(url, data=json.dumps({
            'id': 'dept-uuid', 'code': 'CSC', 'name': 'Computer Science & Eng',
        }), content_type='application/json', **AUTH)
        dept.refresh_from_db()
        self.assertEqual(dept.name, 'Computer Science & Eng')
        self.assertEqual(Department.objects.filter(code='CSC').count(), 1)


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class ProgrammeSyncTests(TestCase):
    def test_create_programme(self):
        resp = self.client.post(reverse('api:sync_programmes'), data=json.dumps({
            'id': 'prog-uuid', 'code': 'NDCSC', 'name': 'National Diploma in CS',
            'department_code': 'CSC', 'programme_type': 'NATIONAL_DIPLOMA',
            'duration': 2, 'is_active': True,
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        prog = Programme.objects.get(code='NDCSC')
        self.assertEqual(prog.department_code, 'CSC')


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class SessionSyncTests(TestCase):
    def test_create_and_set_current(self):
        url = reverse('api:sync_sessions')
        resp = self.client.post(url, data=json.dumps({
            'id': 'sess-uuid', 'name': '2025/2026',
            'start_date': '2025-09-01T00:00:00Z', 'end_date': '2026-08-31T00:00:00Z',
            'is_current': True, 'is_active': True,
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        session = AcademicSession.objects.get(name='2025/2026')
        self.assertTrue(session.is_current)
        # School-wide academic year follows the current portal session.
        self.assertEqual(AcademicSettings.get_current().academic_year, '2025/2026')


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class CourseSyncTests(TestCase):
    def test_create_course_with_offerings_and_lecturers(self):
        url = reverse('api:sync_courses')
        resp = self.client.post(url, data=json.dumps({
            'course_code': 'CSC101', 'title': 'Introduction to Computer Science',
            'credit_unit': 3, 'description': 'An intro course.',
            'offerings': [
                {'programme_code': 'NDCSC', 'department_code': 'CSC',
                 'level': 100, 'semester': '1', 'is_elective': False},
            ],
            'lecturers': [{'staff_id': 'STAFF001', 'first_name': 'Dr.',
                           'last_name': 'Musa'}],
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        course = Course.objects.get(code='CSC101')
        self.assertEqual(course.title, 'Introduction to Computer Science')
        self.assertEqual(course.level, 'ND1')  # 100 -> ND1
        self.assertEqual(course.status, 'published')
        self.assertEqual(course.department_list, ['CSC'])
        self.assertEqual(len(course.portal_offerings), 1)
        self.assertEqual(len(course.portal_lecturers), 1)

    def test_update_keeps_same_slug(self):
        url = reverse('api:sync_courses')
        payload = {'course_code': 'MTH101', 'title': 'Mathematics'}
        self.client.post(url, data=json.dumps(payload),
                         content_type='application/json', **AUTH)
        self.client.post(url, data=json.dumps({**payload, 'title': 'Mathematics II'}),
                         content_type='application/json', **AUTH)
        self.assertEqual(Course.objects.filter(code='MTH101').count(), 1)


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class RegistrationSyncTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create_user(
            username='stu@example.com', email='stu@example.com',
            password='x', matric_number='AHP/ND/CSC/24/0042')

    def test_enroll_student(self):
        url = reverse('api:sync_registrations')
        resp = self.client.post(url, data=json.dumps({
            'id': 'reg-uuid', 'student_matric': 'AHP/ND/CSC/24/0042',
            'academic_session': '2025/2026', 'semester': '1', 'level': 100,
            'courses': ['CSC101', 'MTH101'], 'status': 'SUBMITTED',
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['enrollments_created'], 2)
        self.assertEqual(self.student.enrollments.count(), 2)
        # Courses shells were created if missing.
        self.assertTrue(Course.objects.filter(code='CSC101').exists())

    def test_unknown_student_warns(self):
        url = reverse('api:sync_registrations')
        resp = self.client.post(url, data=json.dumps({
            'student_matric': 'NOPE/001', 'courses': ['CSC101'],
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()['warning'])


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class SsoApiTests(TestCase):
    URL = reverse('api:auth_sso')

    def _sso(self, assertion):
        return self.client.post(self.URL, data=json.dumps({'assertion': assertion}),
                                content_type='application/json')

    def _student_assertion(self, **overrides):
        payload = {
            'sub': 'fbba8d1d-bd55-4ddc-b978-36ce979c841f',
            'matric_number': 'AHP/ND/CSC/24/0042',
            'email': 'amina@example.com', 'first_name': 'Amina',
            'last_name': 'Bello', 'user_type': 'student',
        }
        payload.update(overrides)
        return sign_jwt(payload, TEST_SECRET)

    def test_valid_assertion_logs_in(self):
        resp = self._sso(self._student_assertion())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['matric_number'], 'AHP/ND/CSC/24/0042')
        self.assertTrue(data['token'])
        # find-or-create on sub (portal UUID)
        student = Student.objects.get(portal_id='fbba8d1d-bd55-4ddc-b978-36ce979c841f')
        self.assertEqual(student.matric_number, 'AHP/ND/CSC/24/0042')

    def test_replay_matches_existing_student(self):
        self._sso(self._student_assertion())
        resp = self._sso(self._student_assertion())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Student.objects.filter(portal_id='fbba8d1d-bd55-4ddc-b978-36ce979c841f').count(),
            1)

    def test_missing_assertion_401(self):
        resp = self._sso('')
        self.assertEqual(resp.status_code, 401)

    def test_expired_assertion_401(self):
        token = sign_jwt(
            {'sub': 's1', 'user_type': 'student', 'matric_number': 'M'},
            TEST_SECRET, ttl=60, now=int(time.time()) - 120)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('expired', resp.json()['message'])

    def test_bad_signature_401(self):
        token = sign_jwt({'sub': 's1', 'user_type': 'student'}, 'wrong-secret')
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('Invalid', resp.json()['message'])

    def test_invalid_user_type_401(self):
        token = sign_jwt({'sub': 's1', 'user_type': 'admin'}, TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 401)

    def test_lms_access_false_blocked(self):
        Student.objects.create_user(
            username='blocked@example.com', email='blocked@example.com',
            password='x', matric_number='BLK/001', lms_access=False,
            is_sms_synced=True)
        resp = self._sso(self._student_assertion(matric_number='BLK/001',
                                                 email='blocked@example.com'))
        self.assertEqual(resp.status_code, 401)

    def test_staff_without_lecturer_account_401(self):
        token = sign_jwt({'sub': 'st1', 'staff_id': 'STAFF001',
                          'email': 'ibrahim@example.com', 'user_type': 'staff'},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 401)

    def test_staff_with_lecturer_account_logs_in(self):
        Student.objects.create_user(
            username='ibrahim@example.com', email='ibrahim@example.com',
            password='x', role='lecturer', staff_id='STAFF001')
        token = sign_jwt({'sub': 'st1', 'staff_id': 'STAFF001',
                          'email': 'ibrahim@example.com', 'user_type': 'staff'},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['user']['user_type'], 'lecturer')


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class SsoCallbackTests(TestCase):
    URL = '/sso/callback'

    def test_no_assertion_shows_error(self):
        resp = self.client.get(self.URL)
        self.assertContains(resp, 'No assertion provided', status_code=401)

    def test_valid_assertion_redirects_to_dashboard(self):
        token = sign_jwt({
            'sub': 'cb1', 'matric_number': 'CB/001', 'email': 'cb@example.com',
            'first_name': 'Chi', 'last_name': 'B', 'user_type': 'student',
        }, TEST_SECRET)
        resp = self.client.get(self.URL, {'assertion': token})
        self.assertRedirects(resp, reverse('courses:dashboard'))
        student = Student.objects.get(portal_id='cb1')
        self.assertEqual(student.email, 'cb@example.com')

    def test_expired_assertion_shows_expired_error(self):
        token = sign_jwt({'sub': 'cb2', 'user_type': 'student'},
                         TEST_SECRET, ttl=60, now=int(time.time()) - 120)
        resp = self.client.get(self.URL, {'assertion': token})
        self.assertContains(resp, 'Assertion expired', status_code=401)
