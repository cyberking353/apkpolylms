"""
Shared upsert logic for Portal -> LMS sync.

Each function takes a single JSON object exactly as the Portal webhook sends it
and upserts it idempotently. Used both by the HTTP sync endpoints
(api.views) and the bootstrap pull command (manage.py sync_portal) so the two
paths never drift.

Errors are raised as ValueError with a human-readable message; the callers turn
those into 400/422 responses or command warnings.
"""
from django.utils.text import slugify

from accounts.models import Student, ACADEMIC_LEVEL_CHOICES
from departments.models import Department
from courses.models import (
    AcademicSettings, AcademicSession, Course, CourseDepartment,
    Enrollment, Programme, SEMESTER_CHOICES,
)

# Portal numeric level (100/200/300/400) -> LMS label (ND1/ND2/HND1/HND2).
LEVEL_NUMERIC_TO_LABEL = {100: 'ND1', 200: 'ND2', 300: 'HND1', 400: 'HND2'}

# Portal statuses are authoritative: only "active" grants access. Everything
# else (suspended, withdrawn, expelled, graduated, inactive) deactivates.
ACTIVE_STATUSES = ('active',)


def _clean(value):
    if value is None:
        return ''
    return str(value).strip()


def _coerce_level(value):
    """Accept 'ND1' style labels, numeric 100/200/300/400, or anything else as-is."""
    value = _clean(value)
    if not value:
        return ''
    try:
        numeric = int(float(value))
        return LEVEL_NUMERIC_TO_LABEL.get(numeric, value)
    except (TypeError, ValueError):
        return value


def _coerce_semester(value):
    value = str(value).strip()
    return value if value in dict(SEMESTER_CHOICES) else '1'


def _course_slug(title, code):
    base = slugify(title) or slugify(code) or 'course'
    slug = base
    counter = 2
    while Course.objects.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def upsert_department(data):
    code = _clean(data.get('code'))
    name = _clean(data.get('name'))
    if not code or not name:
        raise ValueError('department: code and name are required')
    dept, _ = Department.objects.update_or_create(
        code=code,
        defaults={
            'portal_id': _clean(data.get('id')),
            'name': name,
            'is_active': bool(data.get('is_active', data.get('isActive', True))),
        },
    )
    return dept


def upsert_programme(data):
    code = _clean(data.get('code'))
    name = _clean(data.get('name'))
    if not code or not name:
        raise ValueError('programme: code and name are required')
    programme, _ = Programme.objects.update_or_create(
        code=code,
        defaults={
            'portal_id': _clean(data.get('id')),
            'name': name,
            'department_code': _clean(data.get('department_code')),
            'programme_type': _clean(data.get('programme_type')),
            'duration': data.get('duration') or data.get('duration_years') or 2,
            'is_active': bool(data.get('is_active', True)),
        },
    )
    return programme


def _parse_iso(value):
    from django.utils.dateparse import parse_datetime
    value = _clean(value)
    return parse_datetime(value) if value else None


def upsert_session(data):
    name = _clean(data.get('name'))
    if not name:
        raise ValueError('session: name is required')
    is_current = bool(data.get('is_current', False))
    session, _ = AcademicSession.objects.update_or_create(
        name=name,
        defaults={
            'portal_id': _clean(data.get('id')),
            'start_date': _parse_iso(data.get('start_date')),
            'end_date': _parse_iso(data.get('end_date')),
            'is_current': is_current,
            'is_active': bool(data.get('is_active', True)),
        },
    )
    if is_current:
        # Keep the LMS's school-wide academic year aligned with the Portal.
        settings = AcademicSettings.get_current()
        if settings.academic_year != name:
            settings.academic_year = name
            settings.save(update_fields=['academic_year'])
    return session


def _offerings_summary(offerings):
    """Extract (level, semester) from the first offering, and dept list."""
    level = ''
    semester = ''
    departments = []
    for offering in offerings or []:
        if not isinstance(offering, dict):
            continue
        if not level:
            level = _coerce_level(offering.get('level'))
        if not semester:
            semester = _coerce_semester(offering.get('semester'))
        dept = _clean(offering.get('department_code'))
        if dept and dept not in departments:
            departments.append(dept)
        if level and semester:
            break
    return level, semester, departments


def _link_lecturer(course, lecturers):
    """Attach the first lecturer who matches an existing lecturer account."""
    for lecturer in lecturers or []:
        if not isinstance(lecturer, dict):
            continue
        staff_id = _clean(lecturer.get('staff_id'))
        email = _clean(lecturer.get('email'))
        qs = Student.objects.filter(role='lecturer')
        account = None
        if staff_id:
            account = qs.filter(staff_id=staff_id).first()
        if account is None and email:
            account = qs.filter(email__iexact=email).first()
        if account is not None:
            if course.lecturer_id != account.id:
                course.lecturer = account
            break


def upsert_course(data):
    code = _clean(data.get('course_code') or data.get('code'))
    title = _clean(data.get('title'))
    if not code or not title:
        raise ValueError('course: course_code and title are required')

    offerings = data.get('offerings') or []
    level, semester, departments = _offerings_summary(offerings)
    level = level or 'ND1'
    semester = semester or '1'

    existing = Course.objects.filter(code=code).first()
    slug = existing.slug if existing else _course_slug(title, code)

    course, _ = Course.objects.update_or_create(
        code=code,
        defaults={
            'title': title,
            'slug': slug,
            'description': data.get('description') or '',
            'credit_unit': data.get('credit_unit') or 3,
            'level': level if level in dict(Course.LEVEL_CHOICES) else 'ND1',
            'semester': semester,
            'status': 'published',  # the Portal already decided this course exists
            'portal_offerings': offerings,
            'portal_lecturers': data.get('lecturers') or [],
        },
    )

    _link_lecturer(course, data.get('lecturers') or [])
    course.save()

    # Rebuild the department serving-list from the offerings.
    CourseDepartment.objects.filter(course=course).delete()
    for index, dept in enumerate(departments):
        CourseDepartment.objects.get_or_create(
            course=course, department=dept,
            defaults={'is_home': index == 0},
        )

    return course


def upsert_student(data):
    """
    Upsert a student from the Portal. Returns (student, created, field_errors).
    field_errors is a dict of warnings keyed by field (unknown dept, bad level).
    Raises ValueError for missing required fields (matric_number/email).
    """
    matric = _clean(data.get('matric_number'))
    email = _clean(data.get('email'))
    if not matric:
        raise ValueError('student: matric_number is required')
    if not email:
        raise ValueError('student: email is required')

    first = _clean(data.get('first_name'))
    last = _clean(data.get('last_name'))
    level = _clean(data.get('academic_level'))
    session = _clean(data.get('current_session'))
    semester = str(data.get('semester') or '').strip()
    status = _clean(data.get('status')) or 'active'
    dept_code = _clean(data.get('department_code'))

    field_errors = {}

    allowed_levels = [c[0] for c in ACADEMIC_LEVEL_CHOICES]
    if level and level not in allowed_levels:
        field_errors['academic_level'] = (
            f'academic_level "{level}" not in {allowed_levels}; stored as-is')

    if dept_code:
        dept = Department.get_or_none(dept_code)
        if dept is None:
            field_errors['department_code'] = (
                f'Unknown department code "{dept_code}", stored for review')
            dept_stored = dept_code
        else:
            dept_stored = dept.code
    else:
        dept_stored = ''

    is_active = status in ACTIVE_STATUSES
    lms_access = data.get('lms_access', True)
    lms_access = True if lms_access is None else bool(lms_access)

    defaults = {
        'username': email,
        'email': email,
        'first_name': first,
        'last_name': last,
        'department': dept_stored,
        'academic_level': level,
        'current_session': session,
        'current_semester': semester,
        'lms_access': lms_access,
        'is_active': is_active,
        'role': 'student',
        'is_sms_synced': True,
    }
    portal_id = _clean(data.get('id') or data.get('portal_id'))
    if portal_id:
        defaults['portal_id'] = portal_id

    student, created = Student.objects.update_or_create(
        matric_number=matric, defaults=defaults)

    if created:
        # No known password — logins happen via Portal SSO. Use an unusable
        # password so the account can't be entered with a blank credential.
        student.set_unusable_password()
        student.save()

    return student, created, field_errors


def _find_or_create_course_for_registration(code, level_label, semester):
    code = _clean(code)
    if not code:
        return None
    course = Course.objects.filter(code=code).first()
    if course is None:
        course = Course.objects.create(
            title=code, code=code,
            slug=_course_slug(code, code),
            level=level_label if level_label in dict(Course.LEVEL_CHOICES) else 'ND1',
            semester=semester,
            status='published',
        )
    return course


def upsert_registration(data):
    """
    Enroll a student in the listed courses. Returns (created_count, warnings).
    The Portal's registration is authoritative for what the student can access.
    """
    matric = _clean(data.get('student_matric'))
    if not matric:
        raise ValueError('registration: student_matric is required')

    student = Student.objects.filter(matric_number=matric).first()
    if student is None:
        return 0, [f'registration for {matric}: student not found, skipped']

    level_label = _coerce_level(data.get('level'))
    semester = _coerce_semester(data.get('semester'))
    raw_courses = data.get('courses') or []
    if isinstance(raw_courses, dict):
        raw_courses = [raw_courses]

    created_count = 0
    warnings = []
    for item in raw_courses:
        if isinstance(item, dict):
            code = _clean(item.get('course_code') or item.get('code'))
        else:
            code = _clean(item)
        if not code:
            warnings.append(f'registration for {matric}: empty course code, skipped')
            continue
        course = _find_or_create_course_for_registration(code, level_label, semester)
        if course is None:
            continue
        _, was_created = Enrollment.objects.get_or_create(student=student, course=course)
        if was_created:
            created_count += 1

    return created_count, warnings


def upsert_staff(data):
    """
    Upsert a staff (lecturer) account from the Portal. The Portal owns user
    creation (it applies its own permission matrix before letting a staff
    member reach the LMS), so the LMS only mirrors what it is sent.

    Returns (staff, created, warnings). Raises ValueError if staff_id missing.
    """
    staff_id = _clean(data.get('staff_id'))
    email = _clean(data.get('email'))
    if not staff_id:
        raise ValueError('staff: staff_id is required')

    first = _clean(data.get('first_name'))
    last = _clean(data.get('last_name'))
    dept_code = _clean(data.get('department_code'))
    portal_id = _clean(data.get('portal_id'))
    is_active = bool(data.get('is_active', True))

    warnings = {}
    if dept_code:
        dept = Department.get_or_none(dept_code)
        if dept is None:
            warnings['department_code'] = (
                f'Unknown department code "{dept_code}", stored for review')
            dept_stored = dept_code
        else:
            dept_stored = dept.code
    else:
        dept_stored = ''

    user = None
    if portal_id:
        user = Student.objects.filter(role='lecturer', portal_id=portal_id).first()
    if user is None:
        user = Student.objects.filter(role='lecturer', staff_id=staff_id).first()
    if user is None and email:
        user = Student.objects.filter(role='lecturer', email__iexact=email).first()

    created = user is None
    if created:
        base = email or staff_id or portal_id or 'staff'
        username = base
        counter = 1
        while Student.objects.filter(username__iexact=username).exists():
            counter += 1
            username = f'{base}-{counter}'
        user = Student(
            username=username,
            email=email,
            role='lecturer',
            is_active=is_active,
            is_sms_synced=True,
        )
        # No password known — staff sign in via the Portal SSO.
        user.set_unusable_password()

    user.staff_id = staff_id
    user.portal_id = portal_id or user.portal_id
    user.email = email
    user.first_name = first
    user.last_name = last
    user.department = dept_stored
    user.is_active = is_active
    user.role = 'lecturer'
    user.is_sms_synced = True
    user.save()

    # Bind assigned courses to this lecturer (find-or-create the shell).
    for item in data.get('assigned_courses') or []:
        if not isinstance(item, dict):
            continue
        code = _clean(item.get('course_code') or item.get('code'))
        if not code:
            continue
        title = _clean(item.get('title')) or code
        course = Course.objects.filter(code=code).first()
        if course is None:
            course = Course.objects.create(
                title=title, code=code,
                slug=_course_slug(title, code),
                status='published', level='ND1', semester='1',
            )
        if course.lecturer_id != user.id:
            course.lecturer = user
            course.save(update_fields=['lecturer'])

    return user, created, warnings
