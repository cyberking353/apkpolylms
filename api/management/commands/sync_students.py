"""
Management command: python manage.py sync_students

Pulls the full list of online students from the Portal and upserts each one
into the LMS. Used for the initial one-time load and nightly reconciliation.
Idempotent — safe to run repeatedly.

Configuration (via .env or environment):
  PORTAL_BACKEND_URL   e.g. https://api-demo.auxilax.com
  LMS_API_TOKEN        the shared server-to-server token (Bearer)
"""
import os

import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api import sync as sync_helpers


def _records(payload):
    """Extract a list of records from an init endpoint response."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ('students', 'data', 'results', 'records'):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


class Command(BaseCommand):
    help = 'Pull students from the Portal and upsert them into the LMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url', default=None,
            help='Portal students init URL (overrides PORTAL_BACKEND_URL)')
        parser.add_argument(
            '--token', default=None,
            help='Portal API token (overrides settings.LMS_API_TOKEN)')

    def handle(self, *args, **options):
        base_url = (options.get('url')
                    or os.environ.get('SMS_API_URL')
                    or getattr(settings, 'PORTAL_BACKEND_URL', '') or '')
        if base_url:
            if 'lms/sync/init' in base_url:
                url = base_url
            else:
                url = f'{base_url.rstrip("/")}/api/v1/lms/sync/init/students'
        else:
            url = ''

        token = (options.get('token')
                 or os.environ.get('SMS_API_TOKEN')
                 or getattr(settings, 'LMS_API_TOKEN', '') or '')

        if not url:
            raise CommandError(
                'No Portal URL configured. Set PORTAL_BACKEND_URL in .env or pass --url.')
        if not token or token.endswith('change-me'):
            raise CommandError(
                'No Portal API token configured. Set LMS_API_TOKEN in .env or pass --token.')

        self.stdout.write(f'Fetching students from {url} ...')
        resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=60)
        if resp.status_code == 401:
            raise CommandError('Unauthorized: check the LMS_API_TOKEN.')
        if resp.status_code != 200:
            raise CommandError(f'Portal returned HTTP {resp.status_code}: {resp.text[:300]}')

        students = _records(resp.json())
        total = len(students)
        self.stdout.write(f'  {total} student record(s) received.')

        created = updated = skipped = 0
        warnings = []
        for row in students:
            if not isinstance(row, dict):
                skipped += 1
                continue
            try:
                student, was_created, field_errors = sync_helpers.upsert_student(row)
            except ValueError as exc:
                warnings.append(f'{row.get("matric_number", "?")}: {exc}')
                skipped += 1
                continue
            if was_created:
                created += 1
            else:
                updated += 1
            for message in field_errors.values():
                warnings.append(f'{student.matric_number}: {message}')
            from courses.models import Enrollment
            Enrollment.sync_for_student(student)

        self.stdout.write(f'  ✅ Created {created}, updated {updated}, skipped {skipped}.')
        for w in warnings:
            self.stdout.write(self.style.WARNING(f'  ⚠️  {w}'))
        self.stdout.write(self.style.SUCCESS('\nDone.'))
