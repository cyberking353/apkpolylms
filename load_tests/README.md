# Al-Hikma LMS — Load Testing Suite

A production-grade Locust-based load testing suite for the Al-Hikma Polytechnic
LMS. Simulates realistic student behaviour during online examinations.

## Prerequisites

```bash
pip install locust  # or: pip install -r load_tests/requirements.txt
```

## Step 1: Seed test data

Create 210 test student accounts and ensure a published exam exists:

```bash
# Ensure you're in the Django project root (where manage.py lives)
python load_tests/seed_test_data.py --students 210
```

This will:
- Create 210 student accounts (`loadtest.student001@alhikma.edu.ng` … `210`)
- Assign them across departments and academic levels
- Auto-enrol them in matching courses
- Ensure one published course has an approved exam (20 questions, 30 min, proctoring disabled)
- Write credentials to `load_tests/students.csv`

## Step 2: Configure the load test

Set environment variables or edit `locustfile.py` defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `http://localhost:8000` | Target Django server |
| `EXAM_ID` | auto-detected | Specific exam ID (optional) |
| `COURSE_SLUG` | auto-detected | Specific course slug (optional) |

The locustfile auto-discovers the exam and course from the dashboard if not
explicitly configured.

## Step 3: Run scenarios

### Web UI (recommended for analysis)

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8000
```

Open http://localhost:8089 in your browser. Enter the number of users and
spawn rate, then start the test.

### Headless CLI (for automated runs)

```bash
# 70 students (your target load)
bash load_tests/run_scenario.sh 70

# All scenarios
for s in smoke 30 50 70 100 150 200; do
    bash load_tests/run_scenario.sh "$s"
done
```

### Using the scenarios module

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8000 \
    --users=70 --spawn-rate=14 --run-time=20m \
    --headless --html=report.html --csv=stats
```

## Student Simulation Flow

Each virtual student executes this exact flow:

1. **GET /** — Landing page
2. **GET /accounts/login/** — Extract CSRF token
3. **POST /accounts/login/** — Login with credentials
4. **GET /dashboard/** — Student dashboard (auto-syncs enrollments)
5. **GET /courses/** → **GET /courses/{slug}/** — Find a course with an exam
6. **GET /exams/{id}/** — Exam detail page (checks status)
7. **POST /exams/{id}/start/** — Start the exam (creates attempt)
8. Loop through questions (20–60s think time per question):
   - 15% probability of navigating back to a previous question
   - 30% probability of changing the previous answer when going back
   - Heartbeat POST every 3 questions
9. **POST /exams/{id}/submit/** — Submit all answers at once
10. **GET /exams/result/{attempt_id}/** — View result
11. **GET /accounts/logout/** — Log out

## Custom Metrics

The suite emits these custom events visible in the Locust UI and CSV reports:

| Event | Description |
|-------|-------------|
| `login_success` | Successful authentication |
| `exam_submission` | Exam answers submitted |
| `exam_result_view` | Result page loaded |
| `quick_exam_submission` | Quick-user exam submit |

## Architecture Notes

The suite has two user classes:

- **ExamStudentUser** (weight 1) — Full realistic flow with think times
- **QuickExamUser** (weight 2) — Minimal-delay flow for higher throughput

This lets you test both realistic behaviour and raw endpoint capacity
in a single run.

## Interpreting Results

Key thresholds for 70 concurrent students:

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| P95 login | <500ms | 500–1000ms | >1000ms |
| P95 dashboard | <800ms | 800–2000ms | >2000ms |
| P95 exam start | <1000ms | 1000–3000ms | >3000ms |
| P95 exam submit | <1500ms | 1500–4000ms | >4000ms |
| Failure rate | <1% | 1–5% | >5% |
| Login failures | <2% | 2–5% | >5% |
| Exam submissions | <1% | 1–3% | >3% |

## Troubleshooting

**"CSRF token not found"** — Ensure the Django server is running and
accessible. Check that `SESSION_COOKIE_DOMAIN` matches your host.

**"No questions found"** — Run the seed script first, or manually create
an exam with `enable_proctoring=False` via the admin panel.

**"Login failed for all users"** — Verify test students were created
(check `Student.objects.count()` in Django shell).
