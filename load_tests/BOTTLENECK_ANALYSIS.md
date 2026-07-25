# Bottleneck Analysis & Optimization Recommendations

Based on a thorough inspection of every model, view, template, URL pattern,
and JavaScript file in the Al-Hikma LMS codebase.

---

## Critical Bottlenecks

### 1. `Result.sync_for_student()` — N+1 Query Explosion

**File:** `results/models.py:108-114`

```python
@classmethod
def sync_for_student(cls, student):
    from courses.models import Enrollment
    for enrollment in Enrollment.objects.filter(student=student).select_related('course'):
        cls.sync_for_student_course(e.student, e.course)
```

Each call to `sync_for_student_course()` calls `_calc_ca()` and `_calc_exam()`,
which execute their own queries:

```python
def _calc_ca(self):
    for quiz in quizzes:      # 1 query per quiz
        QuizAttempt.objects.filter(student=self.student, quiz=quiz, ...).first()

def _calc_exam(self):
    ExamAttempt.objects.get(student=self.student, exam__course=self.course, ...)
```

**Impact:** A student enrolled in 6 courses with 5 quizzes each = **1 + 6 + 30 = 37 queries** just for result sync.

**Fix:** Use `prefetch_related` with `Prefetch` objects to batch-load all
`QuizAttempt` and `ExamAttempt` records in 2-3 queries total.

---

### 2. Context Processors Run COUNT Queries on Every Page

**File:** `courses/context_processors.py`

```python
def message_counts(request):
    if role == 'student':
        count = CourseMessage.objects.filter(student=request.user, student_unread=True).count()
    if role == 'lecturer':
        count = CourseMessage.objects.filter(course__lecturer=request.user, status='open', lecturer_unread=True).count()
```

**Impact:** Every single page load fires at least one extra COUNT query.
With 70 concurrent students × dozens of page loads, this adds thousands of
wasted queries.

**Fix:** 
- Cache the count in the user's session with a 30-second TTL
- Or add the count to the user object via `@property` with `cached_property`
- Or defer to an HTMX snippet that lazy-loads the badge

---

### 3. Dashboard Calls `Enrollment.sync_for_student()` on Every Load

**File:** `courses/views.py:49-57`

```python
@student_required
def dashboard(request):
    Enrollment.sync_for_student(request.user)
```

This iterates over all matching courses and calls `get_or_create()` for each.
Called every time a student visits their dashboard.

**Impact:** Under load, 70 students hitting `/dashboard/` simultaneously each
trigger `sync_for_student` → N queries each.

**Fix:** Move synchronization to a signal post_login or a periodic background
task (Celery/django-q). The dashboard should be read-only.

---

### 4. `Course.for_student()` — Complex JOIN with DISTINCT

**File:** `courses/models.py:181-195`

```python
@classmethod
def for_student(cls, student):
    qs = cls.objects.filter(
        status='published',
        level=student.academic_level,
        semester=current_semester,
    ).distinct()
    if student.department:
        qs = qs.filter(
            Q(coursedepartment__department=student.department) |
            Q(coursedepartment__isnull=True)
        )
    return qs.distinct()
```

**Impact:** Called on dashboard and course list pages. The double `DISTINCT`
forces a sort on all joined columns. With 70 concurrent users, the database
recomputes this result set for each user.

**Fix:** Add a composite index on `(status, level, semester)`. Consider
caching the result per `(academic_level, semester)` since it changes
infrequently.

---

### 5. Announcement Filtering in Python (Not SQL)

**File:** `announcements/models.py:53-62`

```python
@classmethod
def for_student(cls, student):
    qs = cls.objects.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )
    return [a for a in qs if a.is_visible_to(student)]
```

Fetches ALL active announcements, then filters in Python. With many
department/level-targeted announcements, this loads unnecessary rows.

**Fix:** Push filtering into the database using `Q` expressions for the
audience logic.

---

### 6. Missing Database Indexes

The following foreign keys and filter fields lack explicit indexes.
Django auto-creates indexes for `ForeignKey` and `OneToOneField`, but
composite and query-specific indexes are missing:

| Table | Missing Index | Why Important |
|-------|---------------|---------------|
| `courses_course` | `(status, level, semester)` | `for_student()` filters on all three |
| `courses_enrollment` | `(student_id, course_id)` | Already has `unique_together` which creates an index |
| `exams_examattempt` | `(student_id, exam_id)` | `get_or_create` on start_exam, `unique_together` exists |
| `exams_examattempt` | `(exam_id, submitted_at)` | `_calc_exam()` filters by exam + submitted |
| `quizzes_quizattempt` | `(student_id, quiz_id, submitted_at)` | `_calc_ca()` filters by all three |
| `results_result` | `(student_id, course_id, academic_year, semester)` | `unique_together` exists |
| `courses_lectureprogress` | `(student_id, lecture_id)` | `unique_together` exists |

**All `unique_together` constraints already create database indexes** — these
are adequate for exact lookups but may not cover range scans (e.g.,
`submitted_at__isnull=False`).

---

### 7. `_finalize_attempt` — Grading Without Bulk Update

**File:** `exams/views.py` (around line 240)

```python
def _finalize_attempt(attempt, auto_submitted, terminated_reason='normal'):
    questions = attempt.exam.questions.all()
    correct = attempt.answers.filter(selected_choice__is_correct=True).count()
    total = questions.count()
    score = (correct / total * 100) if total else 0
    attempt.score = round(score, 2)
    attempt.passed = score >= attempt.exam.pass_mark
    attempt.submitted_at = timezone.now()
    attempt.auto_submitted = auto_submitted
    attempt.terminated_reason = terminated_reason
    attempt.save()
```

This does:
1. One query for questions count
2. One aggregate query for correct count
3. One UPDATE

These are efficient individually, but `attempt.save()` writes ALL fields
(not just changed ones). Use `save(update_fields=[...])`.

---

### 8. Exam Submit Re-saves Answers Twice

**File:** `exams/views.py` (submit_exam view)

The submit view loops through questions and calls
`ExamAnswer.objects.update_or_create(...)` for EACH question (N queries),
then `_finalize_attempt()` re-counts via `attempt.answers.filter(...)`.

For a 20-question exam: **20 UPSERTs + 2 SELECTs + 1 UPDATE**. Under 70
concurrent submissions, that's ~1,610 queries in a short burst.

**Fix:** Bulk-create answers with `ExamAnswer.objects.bulk_create(...)`
after collecting all selections, then do a single aggregate COUNT.

---

### 9. Exam Start Page Loads All Questions with Full Choice Data

**File:** `exams/models.py:170-173`

```python
def shuffled_questions(self):
    questions = list(self.exam.questions.prefetch_related('choices').all())
    rng = random.Random(self.id)
    rng.shuffle(questions)
    for question in questions:
        choices = list(question.choices.all())  # already prefetched, but forces evaluation
        rng.shuffle(choices)
        question.shuffled_choices = choices
    return questions
```

This is fine for 20 questions, but if exams grow to 100+ questions, sending
all of them in a single HTML response creates a large payload.

**Impact:** Larger page size → higher response time → longer TTFB.

**Fix:** Consider paginating the exam (render N questions at a time using
HTMX or a JS-driven carousel that lazy-loads from an API endpoint).

---

### 10. Template Rendering — N+1 in Result Template

**File:** `templates/exams/exam_result.html:71`

```django
{% for choice in answer.question.choices.all %}
  {% if choice.is_correct %}<strong>{{ choice.text }}</strong>{% endif %}
{% endfor %}
```

Even though the view uses `prefetch_related('question__choices')`, the
template access `answer.question.choices.all` triggers a new query because
`Answer`'s `select_related('question')` returns a different `Question`
instance than the one used in the view's prefetch.

**Fix:** Pass a pre-built dict `{question_id: correct_choice_text}` to the
template context instead of iterating in template.

---

## Medium-Priority Issues

### 11. `ExamAttempt.active_session_token` — Regenerated on Every Page Refresh

**File:** `exams/views.py:start_exam`

Each page load regenerates the token. Multiple heartbeats from stale tabs
are rejected, which is correct. But the token logic doesn't invalidate old
tokens — a student with 2 tabs open gets serial session conflicts.

**Performance impact:** Negligible, but UX impact during load testing means
some attempts appear "lost."

---

### 12. `portal_counts` Context Processor — Unnecessary Queries

**File:** `portal/context_processors.py`

```python
'pending_courses_count': Course.objects.filter(status='pending').count(),
'pending_exams_count':   Exam.objects.filter(exam_status='pending').count(),
'open_messages_count':   CourseMessage.objects.filter(status='open').count(),
```

Three aggregate queries on every portal page. These should be cached.

---

### 13. Static Files — No Cache Busting Strategy

**File:** `templates/base.html:10`

```html
<link rel="stylesheet" href="{% static 'css/main.css' %}?v=2">
```

The `?v=2` is manual. Should use Django's `ManifestStaticFilesStorage` or
a proper version hash.

---

### 14. No pagination on Any List View

The following views load ALL records:
- `course_list` (portal)
- `result_list` (portal)
- `student_list` (portal)
- `lecturer_message_list`
- `message_list` (student)
- `certificate_list`

As the student base grows, these will become slower.

---

## Recommendations Summary

### Before going to production with 70+ concurrent exam-takers:

1. **Add composite indexes** for `courses_course(status, level, semester)` and `quizzes_quizattempt(student_id, quiz_id, submitted_at)` via a new migration.

2. **Defer `Enrollment.sync_for_student()`** — call it only on login or via a
   management cron job, not on every dashboard view.

3. **Cache context processor counts** using Django's `cache` framework with
   a short TTL (30s).

4. **Use `update_fields`** in `_finalize_attempt` and other save calls to
   reduce write overhead.

5. **Bulk-create exam answers** instead of `update_or_create` per question.

6. **Replace Python-level announcement filtering** with database `Q` expressions.

7. **Profile with Django Debug Toolbar** under load to identify any
   additional N+1 queries unique to your deployed data.

8. **Switch from SQLite to PostgreSQL** for production — SQLite serializes
   all writes, which will be the #1 bottleneck under 70 concurrent exam
   submissions. PostgreSQL handles concurrent writers gracefully.

9. **Run with Gunicorn + multiple workers:**
   ```
   gunicorn alhikma_lms.wsgi:application --workers=4 --threads=4 --worker-class=gthread
   ```
   SQLite won't benefit from multiple workers (file-level lock), but
   PostgreSQL will scale linearly up to ~4-8 workers.

10. **Add Redis caching** for:
    - Course listings (per level/semester)
    - Dashboard stats (short TTL)
    - Context processor counts
