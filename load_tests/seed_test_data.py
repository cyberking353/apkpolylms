"""
Seed script: Creates test student accounts and ensures a test exam exists.

Usage:
    python load_tests/seed_test_data.py [--students N] [--exam-id 1]

Run this from the Django project root (where manage.py lives).
Must have the Django environment set up (python manage.py shell context).
"""

import os
import sys
import csv
import argparse
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhikma_lms.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

Student = get_user_model()


def create_students(count: int, csv_path: str):
    from django.contrib.auth.hashers import make_password
    from accounts.models import get_department_choices
    from courses.models import Enrollment, Course

    depts = [c[0] for c in get_department_choices() if c[0] != 'OTH']
    if not depts:
        depts = ['CS', 'EE', 'ME', 'BA', 'SLT', 'ACC', 'MC']
    levels = ['ND1', 'ND2', 'HND1', 'HND2']

    emails = [f'loadtest.student{i:03d}@alhikma.edu.ng' for i in range(1, count + 1)]
    existing = set(Student.objects.filter(email__in=emails).values_list('email', flat=True))
    pw = 'testpass123'
    hashed = make_password(pw)

    rows = []
    new_students = []

    for i in range(1, count + 1):
        email = f'loadtest.student{i:03d}@alhikma.edu.ng'
        dept = depts[(i - 1) % len(depts)]
        level = levels[(i - 1) % len(levels)]

        rows.append({'email': email, 'password': pw, 'department': dept, 'level': level})

        if email not in existing:
            new_students.append(Student(
                username=email,
                email=email,
                first_name=f'LoadTest{i:03d}',
                last_name='Student',
                password=hashed,
                role='student',
                department=dept,
                academic_level=level,
                matric_number=f'LMS/LOAD/{i:04d}',
            ))

    if new_students:
        Student.objects.bulk_create(new_students, batch_size=100)
        print(f'  Bulk-created {len(new_students)} students')

        for s in Student.objects.filter(email__in=[u.email for u in new_students]):
            Enrollment.sync_for_student(s)
        print(f'  Synced enrollments for {len(new_students)} students')

    print(f'  {len(existing)} students already existed')

    with open(csv_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['email', 'password', 'department', 'level'])
        w.writeheader()
        w.writerows(rows)

    print(f'\nDone. {len(new_students)} created, {len(existing)} already existed.')
    print(f'Credentials written to {csv_path}')


def ensure_exam(course_slug: Optional[str] = None):
    from courses.models import Course, AcademicSettings
    from exams.models import Exam, ExamQuestion, ExamChoice

    if course_slug:
        courses = Course.objects.filter(slug=course_slug, status='published')
    else:
        settings = AcademicSettings.get_current()
        courses = Course.objects.filter(status='published')

    if not courses.exists():
        print('No published courses found. Run `python manage.py seed` first.')
        return

    course = courses.first()
    exam, created = Exam.objects.get_or_create(
        course=course,
        defaults={
            'title': f'{course.title} — Semester Exam',
            'time_limit_minutes': 30,
            'pass_mark': 40,
            'exam_status': 'approved',
            'open_at': timezone.now() - timedelta(hours=1),
            'close_at': timezone.now() + timedelta(days=7),
            'is_active': True,
            'enable_proctoring': False,
            'max_violations': 0,
        }
    )
    if not created and exam.exam_status != 'approved':
        exam.exam_status = 'approved'
        exam.open_at = timezone.now() - timedelta(hours=1)
        exam.close_at = timezone.now() + timedelta(days=7)
        exam.save()

    if exam.questions.count() < 10:
        existing = exam.questions.count()
        for i in range(existing + 1, 21):
            q = ExamQuestion.objects.create(
                exam=exam, text=f'Load test question {i}: What is the capital of Nigeria?',
                order=i, marks=1
            )
            ExamChoice.objects.create(question=q, text='Abuja', is_correct=True, order=0)
            ExamChoice.objects.create(question=q, text='Lagos', is_correct=False, order=1)
            ExamChoice.objects.create(question=q, text='Kano', is_correct=False, order=2)
            ExamChoice.objects.create(question=q, text='Ibadan', is_correct=False, order=3)

    print(f'Exam ready: exam_id={exam.id}, course="{course.title}", '
          f'{exam.questions.count()} questions')

    return exam.id, course.slug


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed load test data')
    parser.add_argument('--students', type=int, default=210,
                        help='Number of test students to create (default: 210)')
    parser.add_argument('--csv', type=str, default='load_tests/students.csv',
                        help='Output CSV path (default: load_tests/students.csv)')
    parser.add_argument('--exam-course-slug', type=str, default=None,
                        help='Course slug to seed exam for (default: first published course)')
    args = parser.parse_args()

    print(f'Creating {args.students} test students...')
    create_students(args.students, args.csv)

    print('\nEnsuring a test exam exists...')
    result = ensure_exam(args.exam_course_slug)

    if result:
        exam_id, slug = result
        print(f'\nLoad test configuration:')
        print(f'  HOST=http://localhost:8000')
        print(f'  EXAM_ID={exam_id}')
        print(f'  COURSE_SLUG={slug}')
        print(f'  CREDENTIALS_FILE={args.csv}')
