# Al-Hikma LMS

A full-featured Learning Management System for Al-Hikma Polytechnic, built with **Django 4.2**.

## Overview

Al-Hikma LMS provides course delivery, assessments, result management, and communication tools for students and lecturers:

- **Courses & lectures** — courses organised by department and semester, with lecture notes, video, and progress tracking.
- **Assessments** — quizzes and exams with question banking, scoring, rescheduling, and proctoring flags.
- **Results** — gradebooks, GPA/CGPA computation, classification, and export.
- **Student & lecturer dashboards** — progress monitoring, course messages, notifications, and announcements.
- **Role-based access** — student, lecturer, and portal admin interfaces.
- **PWA** — installable, offline-capable, with an animated splash screen.

## Integration

The LMS integrates with an external Portal/SMS system over a token-authenticated REST API:

- **Sync** — courses, staff, and student registrations are pulled/pushed via `POST /api/v1/sync/*` and the `sync_portal` management command.
- **SSO** — users authenticate via signed short-lived JWT assertions (`/sso/callback`) shared with the Portal.

## Deployment

The project is Dockerized and deploys to a VPS as a four-container Docker Compose stack (nginx, Gunicorn/Django, PostgreSQL, Redis).

See **[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)** for the full VPS deployment guide.