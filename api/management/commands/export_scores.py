"""
Management command: python manage.py export_scores

Re-exports this LMS's final Result rows to the Portal (SMS) so the Portal owns
the authoritative scorecard. The Portal exposes this endpoint for the LMS to
call — direction is LMS -> Portal:

    POST <PORTAL_BACKEND_URL>/api/v1/lms/sync/scores
    Authorization: Bearer <LMS_API_TOKEN>

Configuration (via .env or environment):
  PORTAL_BACKEND_URL   e.g. https://api-demo.auxilax.com
  LMS_API_TOKEN        the shared server-to-server token (Bearer)

Options:
  --academic-year   year to export (default: current school settings)
  --semester        1 or 2 (default: current school settings)
  --course          limit the export to one course code
  --staff-id        informational: record which exam officer submitted
  --dry-run         build and print the payload without POSTing
"""
import json

from django.core.management.base import BaseCommand, CommandError

from api import sync as sync_helpers
from courses.models import AcademicSettings


class Command(BaseCommand):
    help = 'Export final Result rows to the Portal (POST /api/v1/lms/sync/scores)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url', default=None,
            help='Portal backend URL (overrides PORTAL_BACKEND_URL)')
        parser.add_argument(
            '--token', default=None,
            help='Portal API token (overrides settings.LMS_API_TOKEN)')
        parser.add_argument(
            '--academic-year', default=None,
            help='Year to export, e.g. 2025/2026 (default: current)')
        parser.add_argument(
            '--semester', default=None,
            help='Semester to export, 1 or 2 (default: current)')
        parser.add_argument(
            '--course', default=None,
            help='Limit the export to one course code (e.g. CSC101)')
        parser.add_argument(
            '--staff-id', default='',
            help='Informational: which exam officer submitted the scores')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print the payload without POSTing')

    def handle(self, *args, **options):
        school = AcademicSettings.get_current()
        academic_year = options.get('academic_year') or school.academic_year
        semester = str(options.get('semester') or school.current_semester).strip()
        if semester not in ('1', '2'):
            raise CommandError('--semester must be "1" or "2".')

        if options.get('dry_run'):
            try:
                payload, warnings = sync_helpers.build_scores_payload(
                    academic_year, semester,
                    staff_id=options.get('staff_id') or '',
                    course_code=options.get('course') or None)
            except ValueError as exc:
                raise CommandError(str(exc))
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f'  ⚠️  {warning}'))
            self.stdout.write(self.style.SUCCESS('Dry run — payload:'))
            self.stdout.write(json.dumps(payload, indent=2))
            return

        base_url = options.get('base_url')
        token = options.get('token')
        ok, info = sync_helpers.export_scores_to_portal(
            academic_year, semester,
            staff_id=options.get('staff_id') or '',
            course_code=options.get('course') or None,
            base_url=base_url, token=token)

        for warning in info.get('warnings', []):
            self.stdout.write(self.style.WARNING(f'  ⚠️  {warning}'))

        if not ok:
            raise CommandError(info.get('error') or 'Scores export failed.')

        self.stdout.write(self.style.SUCCESS(
            f'Exported {info["exported"]} result row(s) for '
            f'{academic_year} semester {semester} to the Portal.'))