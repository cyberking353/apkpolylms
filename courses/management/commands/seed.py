"""
Management command: python manage.py seed
Creates sample categories, courses, modules, lectures, quizzes, and demo accounts
(students AND lecturers) for development.
"""
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta
from courses.models import Category, Course, CourseDepartment, Module, Lecture, AcademicSettings, Enrollment
from quizzes.models import Quiz, Question, Choice
from exams.models import Exam, ExamQuestion, ExamChoice
from accounts.models import Student


SAMPLE_COURSES = [
    {
        'title': 'Introduction to Computer Science',
        'code': 'COM101', 'credit_unit': 3,
        'icon': '💻', 'color_start': '#0D1F3C', 'color_end': '#1A3A6C',
        'category': 'Computer Science',
        'description': 'A comprehensive foundation course covering core computing concepts, algorithms, data structures, and introductory programming — designed for Al-Hikma Polytechnic students.',
        'lecturer_key': 'aliyu_garba',
        'duration_hours': 36, 'level': 'ND1', 'departments': ['CS'], 'home_department': 'CS',
        'modules': [
            {'title': 'Introduction to Computing', 'desc': 'History of computers and binary systems',
             'lectures': [('Intro to Computing', 45), ('History of Computers', 30), ('What is a Computer?', 25)]},
            {'title': 'Data Representation', 'desc': 'Number systems, ASCII, Unicode',
             'lectures': [('Number Systems', 40), ('ASCII and Unicode', 35), ('Data Types', 30)]},
            {'title': 'Introduction to Programming', 'desc': 'Variables, control flow, functions',
             'lectures': [('Programming Fundamentals', 58), ('Variables & Data Types', 41), ('Control Flow', 47)]},
            {'title': 'Algorithms & Problem Solving', 'desc': 'Flowcharts, pseudocode, sorting',
             'lectures': [('Algorithm Design', 50), ('Flowcharts', 35), ('Sorting Basics', 45)]},
        ],
        'quiz': {
            'title': 'Week 1 Quiz — Introduction to Computing',
            'time_limit': 10, 'pass_mark': 50,
            'questions': [
                ('What does CPU stand for?',
                 ['Central Processing Unit', 'Computer Personal Unit', 'Central Program Utility', 'Core Processing Unit'], 0),
                ('Which of these is NOT an input device?',
                 ['Keyboard', 'Mouse', 'Monitor', 'Scanner'], 2),
                ('Binary uses how many digits?',
                 ['8', '10', '2', '16'], 2),
                ('What does RAM stand for?',
                 ['Read Access Memory', 'Random Access Memory', 'Rapid Application Module', 'Remote Access Management'], 1),
                ('Which storage type is non-volatile?',
                 ['RAM', 'Cache', 'ROM', 'Register'], 2),
            ]
        },
        'exam': {
            'time_limit': 45, 'pass_mark': 50,
            'questions': [
                ('What does CPU stand for?',
                 ['Central Processing Unit', 'Computer Personal Unit', 'Central Program Utility', 'Core Processing Unit'], 0),
                ('Which number base does binary use?',
                 ['Base 8', 'Base 10', 'Base 2', 'Base 16'], 2),
                ('Which of these is a non-volatile storage type?',
                 ['RAM', 'Cache', 'ROM', 'Register'], 2),
                ('In programming, what is a "variable"?',
                 ['A fixed value that never changes', 'A named container that holds a value', 'A type of loop', 'A syntax error'], 1),
                ('What is the primary purpose of an algorithm?',
                 ['To store data permanently', 'To provide step-by-step instructions to solve a problem', 'To connect to the internet', 'To design a computer chip'], 1),
                ('Which of the following is an example of an input device?',
                 ['Monitor', 'Printer', 'Keyboard', 'Speaker'], 2),
                ('ASCII is primarily used to represent what?',
                 ['Images', 'Characters/text', 'Sound', 'Video'], 1),
                ('What does RAM stand for?',
                 ['Read Access Memory', 'Random Access Memory', 'Rapid Application Module', 'Remote Access Management'], 1),
            ]
        }
    },
    {
        'title': 'Electrical Engineering Basics',
        'code': 'EEC101', 'credit_unit': 3,
        'icon': '⚡', 'color_start': '#2A1400', 'color_end': '#5A3000',
        'category': 'Engineering',
        'description': 'Circuit analysis, Ohm\'s law, AC/DC fundamentals, and practical lab simulations for engineering students.',
        'lecturer_key': 'ibrahim_musa',
        'duration_hours': 28, 'level': 'ND1', 'departments': ['EE'], 'home_department': 'EE',
        'modules': [
            {'title': 'Basic Circuit Theory', 'desc': 'Ohm\'s Law and circuit fundamentals',
             'lectures': [("Ohm's Law", 45), ('Kirchhoff\'s Laws', 50), ('Series & Parallel Circuits', 40)]},
            {'title': 'AC & DC Systems', 'desc': 'Alternating and direct current concepts',
             'lectures': [('DC Fundamentals', 42), ('AC Fundamentals', 48), ('Power Calculations', 36)]},
        ],
        'quiz': None
    },
    {
        'title': 'Applied Mathematics I',
        'code': 'MTH101', 'credit_unit': 2,
        'icon': '🔢', 'color_start': '#0A2A15', 'color_end': '#0F4025',
        'category': 'Mathematics',
        'description': 'Calculus, linear algebra, statistics, and real-world problem-solving techniques for polytechnic students.',
        'lecturer_key': 'fatima_abubakar',
        'duration_hours': 24, 'level': 'ND1', 'departments': [], 'home_department': None,  # shared across ALL ND1 departments
        'modules': [
            {'title': 'Algebra & Functions', 'desc': 'Linear equations and functions',
             'lectures': [('Linear Equations', 38), ('Quadratic Equations', 42), ('Functions', 35)]},
            {'title': 'Calculus Fundamentals', 'desc': 'Differentiation and integration',
             'lectures': [('Limits & Continuity', 45), ('Differentiation', 50), ('Integration', 48)]},
        ],
        'quiz': None
    },
    {
        'title': 'Business Communication',
        'code': 'BUS101', 'credit_unit': 2,
        'icon': '💬', 'color_start': '#1A0A2A', 'color_end': '#350F58',
        'category': 'Business',
        'description': 'Professional writing, public speaking, report writing, and workplace communication. A Business Administration course also borrowed by Computer Science students.',
        'lecturer_key': 'khadija_suleiman',
        'duration_hours': 18, 'level': 'ND2',
        'departments': ['BA', 'CS'], 'home_department': 'BA',  # BORROWED COURSE demo: BA owns it, CS also takes it
        'modules': [
            {'title': 'Written Communication', 'desc': 'Professional writing and reports',
             'lectures': [('Business Writing', 40), ('Report Writing', 45), ('Email Etiquette', 30)]},
            {'title': 'Verbal Communication', 'desc': 'Public speaking and presentations',
             'lectures': [('Public Speaking', 42), ('Presentation Skills', 38), ('Meeting Management', 32)]},
        ],
        'quiz': None
    },
]

# Demo lecturer accounts, keyed so SAMPLE_COURSES can reference them by 'lecturer_key'.
DEMO_LECTURERS = {
    'aliyu_garba': {
        'username': 'a.garba@staff.alhikma', 'email': 'a.garba@staff.alhikma',
        'first_name': 'Aliyu', 'last_name': 'Garba', 'title': 'Dr.',
        'department': 'CS', 'staff_id': 'STAFF/CS/001',
    },
    'ibrahim_musa': {
        'username': 'i.musa@staff.alhikma', 'email': 'i.musa@staff.alhikma',
        'first_name': 'Ibrahim', 'last_name': 'Musa', 'title': 'Engr.',
        'department': 'EE', 'staff_id': 'STAFF/EE/001',
    },
    'fatima_abubakar': {
        'username': 'f.abubakar@staff.alhikma', 'email': 'f.abubakar@staff.alhikma',
        'first_name': 'Fatima', 'last_name': 'Abubakar', 'title': 'Mrs.',
        'department': 'OTH', 'staff_id': 'STAFF/MTH/001',
    },
    'khadija_suleiman': {
        'username': 'k.suleiman@staff.alhikma', 'email': 'k.suleiman@staff.alhikma',
        'first_name': 'Khadija', 'last_name': 'Suleiman', 'title': 'Dr.',
        'department': 'BA', 'staff_id': 'STAFF/BA/001',
    },
}


class Command(BaseCommand):
    help = 'Seeds the database with sample courses, modules, lectures, quizzes, and demo accounts'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n🌱 Seeding Al-Hikma LMS database...\n'))

        # --- Lecturer accounts first, so courses can reference them ---
        lecturers = {}
        created_lecturers = 0
        for key, l in DEMO_LECTURERS.items():
            lecturer, created = Student.objects.get_or_create(
                username=l['username'],
                defaults={
                    'email': l['email'], 'first_name': l['first_name'], 'last_name': l['last_name'],
                    'role': 'lecturer', 'title': l['title'], 'department': l['department'],
                    'staff_id': l['staff_id'],
                }
            )
            if created:
                lecturer.set_password(os.environ.get('SEED_PASSWORD', 'changeme123'))
                lecturer.save()
                created_lecturers += 1
            lecturers[key] = lecturer
        dflt = os.environ.get('SEED_PASSWORD', 'changeme123')
        self.stdout.write(f"  👨‍🏫  {created_lecturers} lecturer(s) created (password: {dflt})")

        created_courses = 0

        for data in SAMPLE_COURSES:
            # Category
            cat, _ = Category.objects.get_or_create(
                name=data['category'],
                defaults={'slug': slugify(data['category']), 'icon': '📚'}
            )

            # Course
            slug = slugify(data['title'])
            if Course.objects.filter(slug=slug).exists():
                self.stdout.write(f"  ⏭  Skipping existing course: {data['title']}")
                continue

            course = Course.objects.create(
                title=data['title'],
                slug=slug,
                category=cat,
                description=data['description'],
                icon=data['icon'],
                color_start=data['color_start'],
                color_end=data['color_end'],
                level=data['level'],
                semester=data.get('semester', '1'),
                lecturer=lecturers[data['lecturer_key']],
                duration_hours=data['duration_hours'],
                status='published',
                published_at=timezone.now(),
                code=data.get('code', ''),
                credit_unit=data.get('credit_unit', 3),
            )

            # Departments taking this course (empty list = shared by all departments at this level)
            for dept in data['departments']:
                CourseDepartment.objects.create(
                    course=course, department=dept,
                    is_home=(dept == data['home_department']),
                )

            # Modules & Lectures
            for week_num, mod_data in enumerate(data['modules'], start=1):
                module = Module.objects.create(
                    course=course,
                    title=mod_data['title'],
                    week_number=week_num,
                    description=mod_data['desc'],
                    order=week_num,
                )
                for lec_order, (lec_title, duration) in enumerate(mod_data['lectures'], start=1):
                    Lecture.objects.create(
                        module=module,
                        title=lec_title,
                        duration_minutes=duration,
                        order=lec_order,
                    )

            # Quiz (for first module)
            if data['quiz']:
                first_module = course.modules.first()
                quiz = Quiz.objects.create(
                    course=course,
                    module=first_module,
                    title=data['quiz']['title'],
                    quiz_type='weekly',
                    time_limit_minutes=data['quiz']['time_limit'],
                    pass_mark=data['quiz']['pass_mark'],
                )
                for q_order, (q_text, choices, correct_idx) in enumerate(data['quiz']['questions'], start=1):
                    question = Question.objects.create(
                        quiz=quiz, text=q_text, order=q_order
                    )
                    for c_order, choice_text in enumerate(choices):
                        Choice.objects.create(
                            question=question,
                            text=choice_text,
                            is_correct=(c_order == correct_idx),
                            order=c_order,
                        )

            created_courses += 1
            dept_note = f" [borrowed by {', '.join(data['departments'])}]" if len(data['departments']) > 1 else ''
            self.stdout.write(f"  ✅  Created: {course.title}{dept_note}")

            # Sample Official Exam — only for the CS course, so there's a concrete,
            # immediately-visible demo of the exam-taking flow (currently OPEN).
            if data.get('exam'):
                exam = Exam.objects.create(
                    course=course,
                    title=f"{course.title} — Semester Exam",
                    instructions='Answer all questions. You have one attempt — once submitted, it cannot be retaken.',
                    time_limit_minutes=data['exam']['time_limit'],
                    pass_mark=data['exam']['pass_mark'],
                    open_at=timezone.now() - timedelta(days=1),     # already open
                    close_at=timezone.now() + timedelta(days=14),   # closes in 2 weeks
                )
                for q_order, (q_text, choices, correct_idx) in enumerate(data['exam']['questions'], start=1):
                    question = ExamQuestion.objects.create(exam=exam, text=q_text, order=q_order)
                    for c_order, choice_text in enumerate(choices):
                        ExamChoice.objects.create(
                            question=question,
                            text=choice_text,
                            is_correct=(c_order == correct_idx),
                            order=c_order,
                        )
                self.stdout.write(f"     📝  + Official exam ({exam.question_count} questions, open now)")

        self.stdout.write(self.style.SUCCESS(
            f'\n✨ Done! Created {created_courses} courses with modules, lectures, and quizzes.\n'
        ))

        # Academic settings (current semester) — singleton, safe to call repeatedly
        settings_obj = AcademicSettings.get_current()
        self.stdout.write(f"  📅  Academic settings: {settings_obj}")

        # A lecturer DRAFT course awaiting admin approval, so the review workflow has
        # something concrete to look at immediately (log in as i.musa@staff.alhikma).
        draft_slug = 'power-electronics-fundamentals'
        if not Course.objects.filter(slug=draft_slug).exists():
            eng_cat, _ = Category.objects.get_or_create(name='Engineering', defaults={'slug': 'engineering', 'icon': '📚'})
            draft_course = Course.objects.create(
                title='Power Electronics Fundamentals',
                slug=draft_slug,
                category=eng_cat,
                description='A proposed follow-on course to Electrical Engineering Basics, covering power converters and motor drives.',
                icon='🔌', color_start='#2A1400', color_end='#5A3000',
                level='ND2', semester='1',
                lecturer=lecturers['ibrahim_musa'],
                duration_hours=20,
                status='pending', submitted_at=timezone.now(),
                code='EEC201', credit_unit=3,
            )
            CourseDepartment.objects.create(course=draft_course, department='EE', is_home=True)
            self.stdout.write(f"  📝  Created a course pending admin review: {draft_course.title}")

        # Demo students, one per academic level, so you can log in immediately and see
        # the dashboard correctly scoped to department + level + current semester.
        DEMO_STUDENTS = [
            {'username': 'cs.nd1@demo.alhikma', 'email': 'cs.nd1@demo.alhikma', 'first_name': 'Amina', 'last_name': 'Bello',
             'department': 'CS', 'academic_level': 'ND1', 'matric_number': 'CS/ND1/001'},
            {'username': 'ee.nd1@demo.alhikma', 'email': 'ee.nd1@demo.alhikma', 'first_name': 'Yusuf', 'last_name': 'Sani',
             'department': 'EE', 'academic_level': 'ND1', 'matric_number': 'EE/ND1/001'},
            {'username': 'ba.nd2@demo.alhikma', 'email': 'ba.nd2@demo.alhikma', 'first_name': 'Hauwa', 'last_name': 'Idris',
             'department': 'BA', 'academic_level': 'ND2', 'matric_number': 'BA/ND2/001'},
            {'username': 'cs.nd2@demo.alhikma', 'email': 'cs.nd2@demo.alhikma', 'first_name': 'Bashir', 'last_name': 'Lawal',
             'department': 'CS', 'academic_level': 'ND2', 'matric_number': 'CS/ND2/001'},
        ]
        created_students = 0
        for s in DEMO_STUDENTS:
            student, created = Student.objects.get_or_create(
                username=s['username'],
                defaults={
                    'email': s['email'], 'first_name': s['first_name'], 'last_name': s['last_name'],
                    'role': 'student',
                    'department': s['department'], 'academic_level': s['academic_level'],
                    'matric_number': s['matric_number'],
                }
            )
            if created:
                student.set_password(os.environ.get('SEED_PASSWORD', 'changeme123'))
                student.save()
                created_students += 1
            Enrollment.sync_for_student(student)
            self.stdout.write(f"  👤  {student.get_full_name()} — {student.get_department_display()} {student.get_academic_level_display()} ({student.username})")

        dflt = os.environ.get('SEED_PASSWORD', 'changeme123')
        self.stdout.write(self.style.SUCCESS(
            f'\n✨ Created {created_students} demo student account(s) and {created_lecturers} lecturer account(s). '
            f'Password for all: {dflt}\n'
            f'   cs.nd2@demo.alhikma will see "Business Communication" — a course borrowed from BA — '
            f'on their dashboard, demonstrating the borrowed-course feature.\n'
            f'   Run: python manage.py createsuperuser — to create an admin account.\n'
            f'   Then visit http://127.0.0.1:8000/ to see the site!\n'
        ))
