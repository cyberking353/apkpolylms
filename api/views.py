"""
Portal <-> LMS integration endpoints.

Server-to-server sync (Bearer LMS_API_TOKEN, all idempotent upserts):
    POST /api/v1/sync/students
    POST /api/v1/sync/courses
    POST /api/v1/sync/departments
    POST /api/v1/sync/programmes
    POST /api/v1/sync/sessions
    POST /api/v1/sync/registrations

SSO (user-facing):
    POST /api/v1/auth/sso          JSON JWT verification (returns session)
    GET  /sso/callback             browser landing page after Portal redirect

The Portal is the source of truth for identity + academic data; the LMS only
mirrors what it is told and never creates or modifies Portal-owned data.
"""
import json

from django.conf import settings
from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from . import sync as sync_helpers
from .sso import verify_jwt, ALLOWED_USER_TYPES

from accounts.models import Student
from courses.models import Enrollment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_ok(request):
    """Check the shared server-to-server token (matches the Portal's LMS_API_TOKEN)."""
    auth = request.headers.get('Authorization', '')
    expected = settings.LMS_API_TOKEN
    if not expected:
        return False
    return auth == f'Bearer {expected}'


def _parse_json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return None


def _bad_request(message, **extra):
    return JsonResponse({'ok': False, 'success': False, 'error': message, **extra},
                        status=400)


def _success(message, **extra):
    return JsonResponse({'ok': True, 'success': True, 'message': message, **extra},
                        status=200)


class SsoError(Exception):
    pass


# ---------------------------------------------------------------------------
# Sync endpoints (server-to-server)
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class SyncAPIView(View):
    """Base view: requires the Portal's Bearer token on every sync request."""

    def dispatch(self, request, *args, **kwargs):
        if not _token_ok(request):
            return JsonResponse({'ok': False, 'success': False,
                                 'error': 'Unauthorized'}, status=401)
        return super().dispatch(request, *args, **kwargs)

    def _upsert(self, request, func, entity):
        data = _parse_json_body(request)
        if data is None:
            return _bad_request('Invalid JSON body')
        if not isinstance(data, dict):
            return _bad_request(f'{entity}: expected a JSON object')
        try:
            func(data)
        except ValueError as exc:
            return _bad_request(str(exc))
        return _success(f'{entity} synced successfully')


class SyncStudentView(SyncAPIView):
    """POST /api/v1/sync/students — upsert a single student."""

    def post(self, request):
        data = _parse_json_body(request)
        if data is None:
            return _bad_request('Invalid JSON body')
        if not isinstance(data, dict):
            return _bad_request('student: expected a JSON object')
        try:
            student, created, field_errors = sync_helpers.upsert_student(data)
        except ValueError as exc:
            return _bad_request(str(exc))
        # Keep the derived-enrollment convenience: portal registrations remain
        # the authoritative course list, this only adds identity-based defaults.
        Enrollment.sync_for_student(student)
        return _success(
            'Student synced successfully',
            created=created,
            matric_number=student.matric_number,
            student_id=student.id,
            warning=field_errors if field_errors else None,
        )


class SyncCourseView(SyncAPIView):
    """POST /api/v1/sync/courses — upsert a course + its offerings/lecturers."""

    def post(self, request):
        return self._upsert(request, sync_helpers.upsert_course, 'course')


class SyncDepartmentView(SyncAPIView):
    """POST /api/v1/sync/departments — upsert a department."""

    def post(self, request):
        return self._upsert(request, sync_helpers.upsert_department, 'department')


class SyncProgrammeView(SyncAPIView):
    """POST /api/v1/sync/programmes — upsert a programme (mirror only)."""

    def post(self, request):
        return self._upsert(request, sync_helpers.upsert_programme, 'programme')


class SyncSessionView(SyncAPIView):
    """POST /api/v1/sync/sessions — upsert an academic session."""

    def post(self, request):
        return self._upsert(request, sync_helpers.upsert_session, 'session')


class SyncRegistrationView(SyncAPIView):
    """POST /api/v1/sync/registrations — enroll a student in their courses."""

    def post(self, request):
        data = _parse_json_body(request)
        if data is None:
            return _bad_request('Invalid JSON body')
        if not isinstance(data, dict):
            return _bad_request('registration: expected a JSON object')
        try:
            created_count, warnings = sync_helpers.upsert_registration(data)
        except ValueError as exc:
            return _bad_request(str(exc))
        return _success(
            'Registration synced successfully',
            enrollments_created=created_count,
            warning=warnings or None,
        )


# ---------------------------------------------------------------------------
# SSO
# ---------------------------------------------------------------------------

def _resolve_sso_user(payload):
    """
    Find-or-create the LMS account for an SSO assertion. Students are linked by
    portal_id (sub) -> matric_number -> email, and bootstrapped from the
    assertion if they don't exist yet. Staff are matched to existing lecturer
    accounts only (never auto-created). Raises SsoError for anything blocking.
    """
    user_type = payload.get('user_type')
    if user_type not in ALLOWED_USER_TYPES:
        raise SsoError('Unsupported user type')

    sub = (payload.get('sub') or '').strip()
    email = (payload.get('email') or '').strip()
    first = (payload.get('first_name') or '').strip()
    last = (payload.get('last_name') or '').strip()

    if user_type == 'student':
        matric = (payload.get('matric_number') or '').strip()
        user = None
        if sub:
            user = Student.objects.filter(portal_id=sub).first()
        if user is None and matric:
            user = Student.objects.filter(matric_number=matric).first()
        if user is None and email:
            user = Student.objects.filter(email__iexact=email).first()

        if user is None:
            user = Student(
                username=email or matric or sub,
                email=email,
                first_name=first,
                last_name=last,
                role='student',
                is_active=True,
                is_sms_synced=True,
            )
            if sub:
                user.portal_id = sub
            user.set_unusable_password()
            user.save()
            if matric:
                user.matric_number = matric
                user.save(update_fields=['matric_number'])
        else:
            changed = False
            if sub and not user.portal_id:
                user.portal_id = sub
                changed = True
            for field, value in (('first_name', first), ('last_name', last)):
                if value and getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if email and user.email != email:
                user.email = email
                user.username = email
                changed = True
            if changed:
                user.save()

        if not getattr(user, 'lms_access', True):
            raise SsoError('Your LMS access is disabled. Please contact the school office.')
        if not user.is_active:
            raise SsoError('This account has been deactivated. Please contact the school office.')
        return user

    # staff
    staff_id = (payload.get('staff_id') or '').strip()
    user = None
    if sub:
        user = Student.objects.filter(portal_id=sub).first()
    if user is None and staff_id:
        user = Student.objects.filter(role='lecturer', staff_id=staff_id).first()
    if user is None and email:
        user = Student.objects.filter(role='lecturer', email__iexact=email).first()
    if user is None:
        raise SsoError('Staff account not provisioned in the LMS. Please contact the administrator.')
    if sub and not user.portal_id:
        user.portal_id = sub
        user.save(update_fields=['portal_id'])
    if not user.is_active:
        raise SsoError('This account has been deactivated. Please contact the school office.')
    return user


def _user_payload(user):
    return {
        'id': user.id,
        'portal_id': getattr(user, 'portal_id', None) or '',
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'user_type': 'lecturer' if user.role == 'lecturer' else 'student',
        'matric_number': getattr(user, 'matric_number', None) or '',
        'staff_id': getattr(user, 'staff_id', None) or '',
    }


@method_decorator(csrf_exempt, name='dispatch')
class SsoAuthView(View):
    """
    POST /api/v1/auth/sso
    Body: {"assertion": "<jwt>"}
    Verifies the Portal's JWT, logs the user into a Django session and returns
    the session token. The JWT is single-use and short-lived — never reused.
    """

    def post(self, request):
        data = _parse_json_body(request)
        if data is None or not isinstance(data, dict):
            return JsonResponse({'success': False, 'message': 'Invalid request'},
                                status=400)
        assertion = data.get('assertion')
        if not assertion:
            return JsonResponse({'success': False, 'message': 'No assertion provided'},
                                status=401)

        payload, error = verify_jwt(assertion, settings.PORTAL_SSO_SECRET)
        if error == 'expired':
            return JsonResponse(
                {'success': False, 'message': 'Assertion expired, please try again from the Portal'},
                status=401)
        if error:
            return JsonResponse({'success': False, 'message': 'Invalid assertion'},
                                status=401)
        if not payload:
            return JsonResponse({'success': False, 'message': 'Invalid assertion'},
                                status=401)

        try:
            user = _resolve_sso_user(payload)
        except SsoError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=401)

        # Single-use: the JWT is authentication only; we mint our own session.
        login(request, user)
        request.session.cycle_key()
        return JsonResponse({
            'success': True,
            'user': _user_payload(user),
            'token': request.session.session_key,
        })


class SsoCallbackView(View):
    """
    GET /sso/callback?assertion=<jwt>
    Browser entry point after the Portal's 302 redirect. Verifies the assertion
    server-side and logs the user in, then sends them to their dashboard.
    """

    @method_decorator(require_GET)
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(_home_url_for(request.user))
        assertion = request.GET.get('assertion', '')
        if not assertion:
            return self._error(request, 'No assertion provided')
        payload, error = verify_jwt(assertion, settings.PORTAL_SSO_SECRET)
        if error == 'expired':
            return self._error(request, 'Assertion expired, please try again from the Portal')
        if error or not payload:
            return self._error(request, 'Invalid assertion')
        try:
            user = _resolve_sso_user(payload)
        except SsoError as exc:
            return self._error(request, str(exc))
        login(request, user)
        request.session.cycle_key()
        return redirect(_home_url_for(user))

    def _error(self, request, message):
        return render(request, 'sso/callback.html', {'error': message}, status=401)


def _home_url_for(user):
    if getattr(user, 'role', 'student') == 'lecturer':
        return reverse('courses:lecturer_dashboard')
    return reverse('courses:dashboard')
