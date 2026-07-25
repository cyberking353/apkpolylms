"""
Al-Hikma Polytechnic LMS — Load Test Suite

Simulates realistic student behaviour:
  login → dashboard → course → exam detail → start exam →
  answer questions (with think-time delays) → submit → view result → logout

Usage:
    locust -f load_tests/locustfile.py --host=http://localhost:8000
"""

import csv
import logging
import random
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from locust import HttpUser, task, between, events

sys.path.insert(0, str(Path(__file__).parent))
from helpers import extract_csrf, extract_question_ids, extract_session_token, extract_attempt_id

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent / 'students.csv'
EXAM_ID = 2
COURSE_SLUG = 'business-communication'

QUESTION_DELAY_MIN = 20
QUESTION_DELAY_MAX = 60


def load_credentials(path):
    if not Path(path).exists():
        logger.warning('Credentials file %s not found. Using fallback credentials.', path)
        return [
            {'email': f'loadtest.student{i:03d}@alhikma.edu.ng', 'password': 'testpass123'}
            for i in range(1, 211)
        ]
    with open(path) as f:
        return list(csv.DictReader(f))


_CREDENTIALS = load_credentials(CSV_PATH)


class ExamStudentUser(HttpUser):
    host = 'http://localhost:8000'
    wait_time = between(0.5, 2.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credential_index = None
        self.credentials = None
        self.csrf_token = None
        self.session_token = None
        self.attempt_id = None
        self.exam_id = None
        self.course_slug = None
        self.questions = []
        self.exam_started = False
        self.exam_completed = False

    def on_start(self):
        self._pick_credentials()

    def _pick_credentials(self):
        idx = random.randrange(len(_CREDENTIALS))
        self.credentials = _CREDENTIALS[idx]
        self.credential_index = idx

    # ── CSRF helpers ────────────────────────────────────────────────────

    def _get_csrf(self, url):
        with self.client.get(url, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f'GET {url} returned {resp.status_code}')
                return None
            csrf = extract_csrf(resp.content)
            if not csrf:
                resp.failure(f'No CSRF token found on {url}')
                return None
            resp.success()
            return csrf

    def _post_with_csrf(self, url, data=None, headers=None,
                    allow_redirects=True, name=None):
        if headers is None:
            headers = {}
        headers.setdefault('X-CSRFToken', self.csrf_token or '')
        data = data or {}
        data.setdefault('csrfmiddlewaretoken', self.csrf_token or '')
        return self.client.post(
            url, data, headers=headers,
            allow_redirects=allow_redirects, name=name,
        )

    # ── Flow steps ──────────────────────────────────────────────────────

    def _landing(self):
        with self.client.get('/', catch_response=True, name='01_landing') as resp:
            if resp.status_code != 200:
                resp.failure(f'Landing page: {resp.status_code}')

    def _login(self):
        csrf = self._get_csrf('/accounts/login/')
        if not csrf:
            return False
        self.csrf_token = csrf

        with self._post_with_csrf(
            '/accounts/login/',
            {'username': self.credentials['email'], 'password': self.credentials['password']},
            allow_redirects=True, name='02_login_submit',
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f'Login failed: {resp.status_code}')
                return False
            if b'Sign In' in resp.content or b'Invalid' in resp.content:
                resp.failure(f'Login rejected for {self.credentials["email"]}')
                return False
            self.csrf_token = extract_csrf(resp.content)
            events.request.fire(
                request_type='CUSTOM', name='login_success',
                response_time=int(resp.elapsed.total_seconds() * 1000),
                response_length=len(resp.content), context={},
                exception=None,
            )
            return True

    def _dashboard(self):
        with self.client.get('/dashboard/', catch_response=True, name='03_dashboard') as resp:
            if resp.status_code != 200:
                resp.failure(f'Dashboard: {resp.status_code}')
                return False
            if not self.csrf_token:
                self.csrf_token = extract_csrf(resp.content)
            return True

    def _find_course_with_exam(self):
        return COURSE_SLUG, EXAM_ID

    def _exam_detail(self) -> bool:
        if not self.exam_id:
            return False
        with self.client.get(f'/exams/{self.exam_id}/', catch_response=True,
                             name='05_exam_detail') as resp:
            if resp.status_code != 200:
                resp.failure(f'Exam detail: {resp.status_code}')
                return False
            self.csrf_token = extract_csrf(resp.content)
            if b'Already submitted' in resp.content or b'You already submitted' in resp.content:
                self.exam_completed = True
                return False
            if b'scheduled' in resp.content or b'opens on' in resp.content.lower():
                return False
            return True

    def _start_exam(self):
        if not self.exam_id:
            return False
        csrf = self._get_csrf(f'/exams/{self.exam_id}/')
        if not csrf:
            return False
        self.csrf_token = csrf

        resp = self._post_with_csrf(
            f'/exams/{self.exam_id}/start/',
            {'js_check': '1'},
            allow_redirects=True, name='05_start_exam',
        )
        if resp.status_code != 200:
            return False
        if b'JavaScript must be enabled' in resp.content:
            return False
        if b'Time ran out' in resp.content:
            self.exam_completed = True
            return False
        self.session_token = extract_session_token(resp.content)
        self.questions = extract_question_ids(resp.content)
        if not self.questions:
            return False
        self.csrf_token = extract_csrf(resp.content)
        self.exam_started = True
        return True

    def _heartbeat(self):
        if not self.exam_id or not self.session_token or self.exam_completed:
            return
        resp = self._post_with_csrf(
            f'/exams/{self.exam_id}/heartbeat/',
            {'token': self.session_token},
            name='06_heartbeat',
        )
        if resp.status_code != 200:
            return
        try:
            data = resp.json()
            if data.get('status') == 'submitted':
                self.exam_completed = True
            elif data.get('status') == 'invalid_session':
                self.exam_completed = True
        except Exception:
            pass

    def _simulate_answering(self):
        if not self.questions or self.exam_completed:
            return

        answers = {}
        nav_back_prob = 0.15

        for idx, (qid, choices) in enumerate(self.questions):
            delay = random.uniform(QUESTION_DELAY_MIN, QUESTION_DELAY_MAX)
            self.wait_time = lambda: delay
            self.wait()

            pick = random.choice(choices)
            answers[f'question_{qid}'] = pick

            if random.random() < nav_back_prob and idx > 0:
                self.wait_time = lambda: random.uniform(3, 8)
                self.wait()
                prev_qid, prev_choices = self.questions[idx - 1]
                if random.random() < 0.3:
                    prev_pick = random.choice(prev_choices)
                    answers[f'question_{prev_qid}'] = prev_pick

            if idx > 0 and idx % 3 == 0:
                self._heartbeat()

        self.user_answers = answers

    def _submit_exam(self):
        if not self.exam_id or not hasattr(self, 'user_answers'):
            return False
        if not self.csrf_token:
            csrf = self._get_csrf(f'/exams/{self.exam_id}/')
            if not csrf:
                return False
            self.csrf_token = csrf

        data = dict(self.user_answers)
        resp = self._post_with_csrf(
            f'/exams/{self.exam_id}/submit/',
            data, allow_redirects=True, name='07_submit_exam',
        )
        if resp.status_code != 200:
            return False
        self.attempt_id = extract_attempt_id(resp.content)
        events.request.fire(
            request_type='CUSTOM', name='exam_submission',
            response_time=int(resp.elapsed.total_seconds() * 1000),
            response_length=len(resp.content), context={},
            exception=None,
        )
        self.exam_completed = True
        return True

    def _view_result(self):
        if not self.attempt_id:
            return
        with self.client.get(f'/exams/result/{self.attempt_id}/',
                             catch_response=True, name='08_exam_result') as resp:
            if resp.status_code != 200:
                resp.failure(f'Exam result: {resp.status_code}')
            events.request.fire(
                request_type='CUSTOM', name='exam_result_view',
                response_time=int(resp.elapsed.total_seconds() * 1000),
                response_length=len(resp.content), context={},
                exception=None,
            )

    def _logout(self):
        with self.client.get('/accounts/logout/', catch_response=True,
                             allow_redirects=True, name='09_logout') as resp:
            if resp.status_code != 200:
                resp.failure(f'Logout: {resp.status_code}')

    # ── Main task ───────────────────────────────────────────────────────

    @task
    def full_exam_flow(self):
        self.exam_started = False
        self.exam_completed = False
        self.attempt_id = None
        self.session_token = None
        self.user_answers = {}
        self.exam_id = EXAM_ID
        self.course_slug = COURSE_SLUG

        self._landing()
        if not self._login():
            return
        self._dashboard()

        if not self._exam_detail():
            self._logout()
            return

        if not self._start_exam():
            self._logout()
            return

        self._simulate_answering()

        if not self._submit_exam():
            self._logout()
            return

        self._view_result()
        self._logout()


class QuickExamUser(HttpUser):
    """
    Lightweight user — same flow as ExamStudentUser but with minimal think
    time and no back-navigation. Designed for higher throughput.
    """
    host = 'http://localhost:8000'
    wait_time = between(0.1, 0.5)
    weight = 2

    def _login(self, creds):
        r = self.client.get('/accounts/login/')
        csrf = extract_csrf(r.content)
        if not csrf:
            return None
        r = self.client.post('/accounts/login/', {
            'csrfmiddlewaretoken': csrf,
            'username': creds['email'],
            'password': creds['password'],
        }, name='q_login')
        if b'Sign In' in r.content:
            return None
        slug, eid = self._find_exam()
        if not eid:
            return None
        r = self.client.get(f'/exams/{eid}/', name='q_exam_detail')
        csrf = extract_csrf(r.content)
        if not csrf:
            return None
        return csrf

    def _find_exam(self):
        return COURSE_SLUG, EXAM_ID

    @task
    def quick_exam_flow(self):
        creds = random.choice(_CREDENTIALS)

        csrf = self._login(creds)
        if not csrf:
            return

        slug, eid = self._find_exam()
        if not eid:
            self.client.get('/accounts/logout/')
            return

        r = self.client.post(
            f'/exams/{eid}/start/',
            {'csrfmiddlewaretoken': csrf, 'js_check': '1'},
            name='q_start_exam',
        )

        questions = extract_question_ids(r.content)
        if not questions:
            self.client.get('/accounts/logout/')
            return

        data = {f'question_{qid}': random.choice(choices) for qid, choices in questions}
        data['csrfmiddlewaretoken'] = csrf

        r = self.client.post(f'/exams/{eid}/submit/', data, name='q_submit_exam')

        events.request.fire(
            request_type='CUSTOM', name='quick_exam_submission',
            response_time=int(r.elapsed.total_seconds() * 1000),
            response_length=len(r.content), context={},
            exception=None,
        )

        self.client.get('/accounts/logout/')
