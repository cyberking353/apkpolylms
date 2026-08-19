"""
Management command: python manage.py sync_portal

Bootstraps an empty LMS from the Portal's initialization endpoints
(GET <PORTAL_BACKEND_URL>/api/v1/lms/sync/init/*). Pulls departments,
programmes, sessions, courses, students and registrations in dependency order
so students can be placed in their departments and enrolled in their courses.

Configuration (via .env or environment):
  PORTAL_BACKEND_URL   e.g. https://api-demo.auxilax.com
  LMS_API_TOKEN        the shared server-to-server token (Bearer)
"""
import os

import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api import sync as sync_helpers
from api.management.commands.sync_students import _records


class Command(BaseCommand):
    help = 'Pull all Portal bootstrap data (departments, programmes, sessions, courses, students, registrations)'

    # Dependency order: departments -> programmes -> sessions -> courses -> staffs
    # -> students -> registrations
    RESOURCES = [
        ('departments',   sync_helpers.upsert_department),
        ('programmes',    sync_helpers.upsert_programme),
        ('sessions',      sync_helpers.upsert_session),
        ('courses',       sync_helpers.upsert_course),
        ('staffs',        sync_helpers.upsert_staff),
        ('students',      sync_helpers.upsert_student),
        ('registrations', sync_helpers.upsert_registration),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url', default=None,
            help='Portal backend URL (overrides PORTAL_BACKEND_URL)')
        parser.add_argument(
            '--token', default=None,
            help='Portal API token (overrides settings.LMS_API_TOKEN)')
        parser.add_argument(
            '--only', nargs='+', default=None,
            help='Only sync these resources, e.g. --only courses students')

    def handle(self, *args, **options):
        base_url = (options.get('base_url')
                    or os.environ.get('SMS_API_URL')
                    or getattr(settings, 'PORTAL_BACKEND_URL', '') or '').rstrip('/')
        token = (options.get('token')
                 or os.environ.get('SMS_API_TOKEN')
                 or getattr(settings, 'LMS_API_TOKEN', '') or '')

        if not base_url:
            raise CommandError('No Portal URL configured. Set PORTAL_BACKEND_URL in .env or pass --base-url.')
        if not token or token.endswith('change-me'):
            raise CommandError('No Portal API token configured. Set LMS_API_TOKEN in .env or pass --token.')

        only = options.get('only')
        resources = [(name, func) for name, func in self.RESOURCES
                     if only is None or name in only]

        headers = {'Authorization': f'Bearer {token}'}
        for name, func in resources:
            url = f'{base_url}/api/v1/lms/sync/init/{name}'
            self.stdout.write(f'Fetching {name} from {url} ...')
            try:
                resp = requests.get(url, headers=headers, timeout=60)
            except requests.RequestException as exc:
                self.stdout.write(self.style.WARNING(f'  ⚠️  request failed: {exc}'))
                continue
            if resp.status_code == 401:
                raise CommandError('Unauthorized: check the LMS_API_TOKEN.')
            if resp.status_code != 200:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠️  HTTP {resp.status_code}: {resp.text[:200]}'))
                continue

            records = _records(resp.json())
            self.stdout.write(f'  {len(records)} record(s) received.')
            errors = 0
            for row in records:
                if not isinstance(row, dict):
                    continue
                try:
                    func(row)
                except ValueError as exc:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  {exc}'))
                    errors += 1
            self.stdout.write(f'  Done (skipped {errors} bad record(s)).')

            # The init list is authoritative: deactivate sms-synced staff who
            # are no longer on it (removed/denied LMS access on the SMS).
            if name == 'staffs':
                for staff_id in sync_helpers.reconcile_staff(records):
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️  Deactivated {staff_id} (absent from Portal staff list)'))

        self.stdout.write(self.style.SUCCESS('\nPortal bootstrap complete.'))
