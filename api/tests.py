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
from results.models import Result

from .sso import sign_jwt
from . import sync as sync_helpers

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

    def test_missing_id_falls_back_to_name(self):
        # The Portal's init endpoint can omit the session uuid; portal_id must
        # not become empty (uniqueness + scores export needs a non-empty id).
        url = reverse('api:sync_sessions')
        resp = self.client.post(url, data=json.dumps({
            'name': '2026/2027', 'is_current': True, 'is_active': True,
        }), content_type='application/json', **AUTH)
        self.assertEqual(resp.status_code, 200)
        session = AcademicSession.objects.get(name='2026/2027')
        self.assertEqual(session.portal_id, '2026/2027')


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
class StaffSyncTests(TestCase):
    URL = reverse('api:sync_staff')

    def _post(self, payload):
        return self.client.post(self.URL, data=json.dumps(payload),
                                content_type='application/json', **AUTH)

    PAYLOAD = {
        'portal_id': 'staff-uuid',
        'staff_id': 'STF/CSC/24/0001',
        'first_name': 'Ibrahim', 'last_name': 'Musa',
        'email': 'ibrahim@example.com',
        'department_code': 'CSC', 'staff_category': 'ACADEMIC',
        'is_active': True,
        'assigned_courses': [
            {'course_code': 'CSC101', 'title': 'Intro to CS'},
        ],
    }

    def test_create_staff(self):
        resp = self._post(self.PAYLOAD)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['created'])
        staff = Student.objects.get(role='lecturer', staff_id='STF/CSC/24/0001')
        self.assertEqual(staff.email, 'ibrahim@example.com')
        self.assertEqual(staff.portal_id, 'staff-uuid')
        self.assertTrue(staff.is_sms_synced)
        self.assertFalse(staff.has_usable_password())

    def test_assigned_courses_linked(self):
        self._post(self.PAYLOAD)
        staff = Student.objects.get(staff_id='STF/CSC/24/0001')
        course = Course.objects.get(code='CSC101')
        self.assertEqual(course.lecturer_id, staff.id)

    def test_update_is_idempotent(self):
        self._post(self.PAYLOAD)
        resp = self._post(self.PAYLOAD)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['created'])
        self.assertEqual(
            Student.objects.filter(role='lecturer', staff_id='STF/CSC/24/0001').count(),
            1)

    def test_missing_staff_id_400(self):
        resp = self._post({'email': 'x@example.com'})
        self.assertEqual(resp.status_code, 400)


class ReconcileStaffTests(TestCase):
    def _staff(self, staff_id, portal_id, is_sms_synced=True, is_active=True):
        return Student.objects.create(
            username=staff_id, email=f'{staff_id}@example.com',
            role='lecturer', staff_id=staff_id, portal_id=portal_id,
            is_sms_synced=is_sms_synced, is_active=is_active,
        )

    def test_deactivates_synced_staff_absent_from_list(self):
        kept = self._staff('STF/CSC/01', 'uuid-1')
        removed = self._staff('STF/CSC/02', 'uuid-2')
        deactivated = sync_helpers.reconcile_staff([
            {'staff_id': 'STF/CSC/01', 'portal_id': 'uuid-1'},
        ])
        self.assertEqual(deactivated, ['STF/CSC/02'])
        kept.refresh_from_db()
        removed.refresh_from_db()
        self.assertTrue(kept.is_active)
        self.assertFalse(removed.is_active)

    def test_matches_by_portal_id(self):
        removed = self._staff('STF/CSC/03', 'uuid-3')
        deactivated = sync_helpers.reconcile_staff([
            {'portal_id': 'uuid-3'},   # same user, staff_id omitted
        ])
        self.assertEqual(deactivated, [])
        removed.refresh_from_db()
        self.assertTrue(removed.is_active)

    def test_never_touches_manually_created_lecturers(self):
        local = self._staff('LEC-LOCAL', 'uuid-x', is_sms_synced=False)
        deactivated = sync_helpers.reconcile_staff([])
        self.assertEqual(deactivated, [])
        local.refresh_from_db()
        self.assertTrue(local.is_active)

    def test_already_inactive_untouched(self):
        inactive = self._staff('STF/CSC/04', 'uuid-4', is_active=False)
        deactivated = sync_helpers.reconcile_staff([])
        self.assertEqual(deactivated, [])
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)


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
        self.assertEqual(Student.objects.filter(role='lecturer').count(), 0)

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

    def test_staff_lms_access_false_blocked(self):
        Student.objects.create_user(
            username='denied@example.com', email='denied@example.com',
            password='x', role='lecturer', staff_id='STAFF002',
            lms_access=False, is_sms_synced=True)
        token = sign_jwt({'sub': 'st2', 'staff_id': 'STAFF002',
                          'email': 'denied@example.com', 'user_type': 'staff'},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('access is disabled', resp.json()['message'])

    def test_staff_deactivated_blocked(self):
        Student.objects.create_user(
            username='gone@example.com', email='gone@example.com',
            password='x', role='lecturer', staff_id='STAFF003',
            is_active=False, is_sms_synced=True)
        token = sign_jwt({'sub': 'st3', 'staff_id': 'STAFF003',
                          'email': 'gone@example.com', 'user_type': 'staff'},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('deactivated', resp.json()['message'])

    def test_staff_admin_account_is_staff_logs_in(self):
        # A portal admin can have role='student' + is_staff=True; SSO must still
        # match their account (staff lookup is widened to is_staff accounts).
        Student.objects.create_user(
            username='boss@example.com', email='boss@example.com',
            password='x', role='student', is_staff=True, staff_id='ADMIN001')
        token = sign_jwt({'sub': 'bs1', 'staff_id': 'ADMIN001',
                          'email': 'boss@example.com', 'user_type': 'staff'},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['user']['is_admin'])

    def test_payload_is_admin_promotes_account_to_staff(self):
        Student.objects.create_user(
            username='promo@example.com', email='promo@example.com',
            password='x', role='lecturer', staff_id='PROMO1')
        token = sign_jwt({'sub': 'pr1', 'staff_id': 'PROMO1',
                          'email': 'promo@example.com', 'user_type': 'staff',
                          'role': 'admin'},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 200)
        user = Student.objects.get(staff_id='PROMO1')
        self.assertTrue(user.is_staff)
        self.assertTrue(resp.json()['user']['is_admin'])

    def test_manage_lms_permission_promotes_account_to_staff(self):
        Student.objects.create_user(
            username='perm@example.com', email='perm@example.com',
            password='x', role='lecturer', staff_id='PERM1')
        token = sign_jwt({'sub': 'pe1', 'staff_id': 'PERM1',
                          'email': 'perm@example.com', 'user_type': 'staff',
                          'permissions': ['manage_lms']},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 200)
        user = Student.objects.get(staff_id='PERM1')
        self.assertTrue(user.is_staff)
        self.assertTrue(resp.json()['user']['is_admin'])

    def test_empty_permissions_does_not_promote_account(self):
        Student.objects.create_user(
            username='noperm@example.com', email='noperm@example.com',
            password='x', role='lecturer', staff_id='NOPERM1')
        token = sign_jwt({'sub': 'np1', 'staff_id': 'NOPERM1',
                          'email': 'noperm@example.com', 'user_type': 'staff',
                          'permissions': []},
                         TEST_SECRET)
        resp = self._sso(token)
        self.assertEqual(resp.status_code, 200)
        user = Student.objects.get(staff_id='NOPERM1')
        self.assertFalse(user.is_staff)
        self.assertFalse(resp.json()['user']['is_admin'])

    def test_removed_manage_lms_demotes_previously_promoted_account(self):
        # Regression: an account promoted via manage_lms must be demoted again
        # when the Portal stops granting the permission.
        Student.objects.create_user(
            username='rev@example.com', email='rev@example.com',
            password='x', role='lecturer', staff_id='REV1')
        granted = sign_jwt({'sub': 'rv1', 'staff_id': 'REV1',
                            'email': 'rev@example.com', 'user_type': 'staff',
                            'permissions': ['manage_lms']},
                           TEST_SECRET)
        self.assertEqual(self._sso(granted).status_code, 200)
        self.assertTrue(Student.objects.get(staff_id='REV1').is_staff)

        revoked = sign_jwt({'sub': 'rv1', 'staff_id': 'REV1',
                            'email': 'rev@example.com', 'user_type': 'staff',
                            'permissions': []},
                           TEST_SECRET)
        resp = self._sso(revoked)
        self.assertEqual(resp.status_code, 200)
        user = Student.objects.get(staff_id='REV1')
        self.assertFalse(user.is_staff)
        self.assertFalse(resp.json()['user']['is_admin'])


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

    def test_staff_is_staff_redirects_to_portal_dashboard(self):
        Student.objects.create_user(
            username='boss@example.com', email='boss@example.com',
            password='x', role='lecturer', staff_id='STAFF900', is_staff=True)
        token = sign_jwt({'sub': 'cb9', 'staff_id': 'STAFF900',
                          'email': 'boss@example.com', 'user_type': 'staff'},
                         TEST_SECRET)
        resp = self.client.get(self.URL, {'assertion': token})
        self.assertRedirects(resp, reverse('portal:dashboard'))

    def test_payload_is_admin_redirects_to_portal_dashboard(self):
        Student.objects.create_user(
            username='promo2@example.com', email='promo2@example.com',
            password='x', role='lecturer', staff_id='PROMO2')
        token = sign_jwt({'sub': 'cb10', 'staff_id': 'PROMO2',
                          'email': 'promo2@example.com', 'user_type': 'staff',
                          'is_admin': True},
                         TEST_SECRET)
        resp = self.client.get(self.URL, {'assertion': token})
        self.assertRedirects(resp, reverse('portal:dashboard'))
        self.assertTrue(Student.objects.get(staff_id='PROMO2').is_staff)

    def test_manage_lms_permission_redirects_to_portal_dashboard(self):
        Student.objects.create_user(
            username='promo3@example.com', email='promo3@example.com',
            password='x', role='lecturer', staff_id='PROMO3')
        token = sign_jwt({'sub': 'cb11', 'staff_id': 'PROMO3',
                          'email': 'promo3@example.com', 'user_type': 'staff',
                          'permissions': ['manage_lms']},
                         TEST_SECRET)
        resp = self.client.get(self.URL, {'assertion': token})
        self.assertRedirects(resp, reverse('portal:dashboard'))
        self.assertTrue(Student.objects.get(staff_id='PROMO3').is_staff)

    def test_empty_permissions_redirects_to_lecturer_dashboard(self):
        Student.objects.create_user(
            username='noperm2@example.com', email='noperm2@example.com',
            password='x', role='lecturer', staff_id='NOPERM2')
        token = sign_jwt({'sub': 'cb12', 'staff_id': 'NOPERM2',
                          'email': 'noperm2@example.com', 'user_type': 'staff',
                          'permissions': []},
                         TEST_SECRET)
        resp = self.client.get(self.URL, {'assertion': token})
        self.assertRedirects(resp, reverse('courses:lecturer_dashboard'))
        self.assertFalse(Student.objects.get(staff_id='NOPERM2').is_staff)

    def test_removed_manage_lms_no_longer_redirects_to_portal(self):
        # Regression: after manage_lms is revoked the callback must send the
        # lecturer to their courses dashboard, not the portal admin.
        Student.objects.create_user(
            username='rev2@example.com', email='rev2@example.com',
            password='x', role='lecturer', staff_id='REV2')
        granted = sign_jwt({'sub': 'cb13', 'staff_id': 'REV2',
                            'email': 'rev2@example.com', 'user_type': 'staff',
                            'permissions': ['manage_lms']},
                           TEST_SECRET)
        self.assertRedirects(self.client.get(self.URL, {'assertion': granted}),
                             reverse('portal:dashboard'))
        self.assertTrue(Student.objects.get(staff_id='REV2').is_staff)

        revoked = sign_jwt({'sub': 'cb13', 'staff_id': 'REV2',
                            'email': 'rev2@example.com', 'user_type': 'staff',
                            'permissions': []},
                           TEST_SECRET)
        resp = self.client_class().get(self.URL, {'assertion': revoked})
        self.assertRedirects(resp, reverse('courses:lecturer_dashboard'))
        self.assertFalse(Student.objects.get(staff_id='REV2').is_staff)


@override_settings(LMS_API_TOKEN=TEST_TOKEN, PORTAL_SSO_SECRET=TEST_SECRET)
class ScoresExportTests(TestCase):
    """Export builder tests: LMS -> Portal scores export."""

    def setUp(self):
        self.session = AcademicSession.objects.create(
            portal_id='session-uuid', name='2025/2026', is_current=True)
        self.student = Student.objects.create_user(
            username='stu@example.com', email='stu@example.com', password='x',
            matric_number='AHP/ND/CSC/24/0042', portal_id='student-uuid')
        self.course = Course.objects.create(code='CSC101', title='Intro to CS')

    def _result(self, student=None, course=None, ca=30.0, exam=60.0,
                academic_year='2025/2026', semester='1'):
        return Result.objects.create(
            student=student or self.student,
            course=course or self.course,
            academic_year=academic_year, semester=semester,
            ca_score=ca, exam_score=exam,
            ca_override=True, exam_override=True)

    def test_builds_payload_with_portal_ids(self):
        self._result()
        payload, warnings = sync_helpers.build_scores_payload(
            '2025/2026', '1', staff_id='staff-uuid')
        self.assertFalse(warnings)
        self.assertEqual(payload['academicSessionId'], 'session-uuid')
        self.assertEqual(payload['semesterId'], '1')
        self.assertEqual(payload['staffId'], 'staff-uuid')
        self.assertEqual(payload['results'], [{
            'studentId': 'student-uuid',
            'courseCode': 'CSC101',
            'caScore': 30.0,
            'examScore': 60.0,
        }])

    def test_missing_session_is_self_healing(self):
        self._result(academic_year='2099/2100')
        payload, warnings = sync_helpers.build_scores_payload('2099/2100', '1')
        self.assertEqual(payload['academicSessionId'], '2099/2100')
        self.assertTrue(any('created local session' in w for w in warnings))
        self.assertTrue(AcademicSession.objects.filter(
            name='2099/2100', portal_id='2099/2100').exists())

    def test_student_without_portal_id_skipped_with_warning(self):
        ghost = Student.objects.create_user(
            username='ghost@example.com', email='ghost@example.com',
            password='x', matric_number='AHP/ND/CSC/24/0099')
        self._result()
        self._result(student=ghost)
        payload, warnings = sync_helpers.build_scores_payload('2025/2026', '1')
        self.assertEqual(payload['results'], [{
            'studentId': 'student-uuid',
            'courseCode': 'CSC101',
            'caScore': 30.0,
            'examScore': 60.0,
        }])
        self.assertEqual(len(warnings), 1)

    def test_empty_results_raises(self):
        Result.objects.all().delete()
        with self.assertRaises(ValueError):
            sync_helpers.build_scores_payload('2025/2026', '1')

    def test_filters_by_semester(self):
        self._result()
        Result.objects.create(
            student=self.student, course=self.course,
            academic_year='2025/2026', semester='2',
            ca_score=10, exam_score=20,
            ca_override=True, exam_override=True)
        payload, _ = sync_helpers.build_scores_payload('2025/2026', '2')
        self.assertEqual(payload['semesterId'], '2')
        self.assertEqual(payload['results'][0]['caScore'], 10.0)
        self.assertEqual(payload['results'][0]['examScore'], 20.0)
