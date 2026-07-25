# Al-Hikma Polytechnic LMS

A full-featured Learning Management System built with **Django 6** for Al-Hikma Polytechnic students.

---

## 🗂 Project Structure

```
alhikma_lms/
├── alhikma_lms/          # Project config (settings, urls, wsgi)
├── accounts/             # Custom Student model, auth (register/login/profile)
├── courses/              # Categories, Courses, Modules, Lectures, Enrolments
├── quizzes/              # Quizzes, Questions, Choices, Attempts, Answers
├── certificates/         # Certificate issuance & verification
├── templates/            # All HTML templates
│   ├── base.html
│   ├── accounts/         # login.html, register.html, profile.html
│   ├── courses/          # landing.html, dashboard.html, course_detail.html …
│   ├── quizzes/          # quiz.html, result.html
│   └── certificates/     # detail.html, list.html, verify.html
├── static/
│   ├── css/main.css
│   └── js/main.js
├── manage.py
├── requirements.txt
└── README.md
```

---

## ⚡ Quick Start

### 1. Clone & create virtual environment
```bash
git clone <repo-url>
cd alhikma_lms
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Apply migrations
```bash
python manage.py migrate
```

### 4. Seed sample data (courses, modules, quizzes)
```bash
python manage.py seed
```

### 5. Create admin account
```bash
python manage.py createsuperuser
```

### 6. Run the development server
```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/** in your browser.

---

## 🔐 Admin Panel

Visit **http://127.0.0.1:8000/admin/** and log in with your superuser credentials.

From the admin panel you can:
- Create & publish courses
- Add modules and lectures (with video URLs or file uploads)
- Build quizzes with multiple-choice questions
- View student enrolments and quiz attempts
- Issue and manage certificates

---

## 📦 Key URLs

| URL | Description |
|-----|-------------|
| `/` | Landing page |
| `/accounts/register/` | Student registration |
| `/accounts/login/` | Login |
| `/dashboard/` | Student dashboard (login required) |
| `/courses/` | Browse all courses |
| `/courses/<slug>/` | Course detail |
| `/courses/<slug>/enroll/` | Enrol in a course |
| `/quizzes/<id>/` | Take a quiz |
| `/certificates/` | My certificates |
| `/certificates/<uuid>/` | View a certificate |
| `/certificates/verify/<uuid>/` | Public certificate verification |
| `/admin/` | Admin panel |

---

## 🧩 App Overview

### `accounts`
- **Model:** `Student` (extends `AbstractUser`)
- Extra fields: `matric_number`, `department`, `xp_points`, `streak_days`, `avatar`
- Auth forms: `RegisterForm`, `LoginForm`, `ProfileForm`

### `courses`
- **Models:** `Category`, `Course`, `Module`, `Lecture`, `Enrollment`, `LectureProgress`
- Students enrol in courses and watch lectures
- Progress is tracked per lecture and displayed as a percentage

### `quizzes`
- **Models:** `Quiz`, `Question`, `Choice`, `QuizAttempt`, `Answer`
- Weekly quizzes tied to modules; final exams tied to courses
- Timed, multiple-choice with configurable pass marks and attempt limits
- On passing a final exam, a certificate is automatically issued

### `certificates`
- **Model:** `Certificate` (UUID primary key)
- Auto-issued when a student passes a final exam
- Public verification page at `/certificates/verify/<uuid>/`

---

## 🎨 Frontend

- **No frameworks** — pure HTML, CSS, and vanilla JavaScript
- **Fonts:** Playfair Display (headings) + Outfit (body) + Dancing Script (certificate)
- **Design system:** CSS custom properties, consistent spacing, responsive grid
- Fully **mobile-responsive** with hamburger nav and stacked layouts on small screens
- **Scroll animations** via IntersectionObserver
- **Print-ready** certificate page

---

## 🚀 Production Checklist

Before deploying to production:

1. Set `DEBUG = False` in settings
2. Generate a strong `SECRET_KEY`
3. Set `ALLOWED_HOSTS` to your domain
4. Switch to PostgreSQL (update `DATABASES`)
5. Run `python manage.py collectstatic`
6. Serve media files via Nginx or a CDN
7. Use `gunicorn` or `uvicorn` as the WSGI server
8. Set up HTTPS (Let's Encrypt / Certbot)

---

## 🧪 Dev Credentials (after `seed` + `createsuperuser`)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@alhikma.edu.ng | admin1234 |
| Student | Register at `/accounts/register/` | — |

---

## 📄 License

Al-Hikma Polytechnic — Internal LMS Project © 2025
