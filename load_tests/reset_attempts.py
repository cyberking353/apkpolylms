"""
Reset all exam attempts (run between load tests).
Usage: python load_tests/reset_attempts.py
"""
import sys; sys.path.insert(0, '.')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhikma_lms.settings')
django.setup()
from exams.models import ExamAttempt, ExamAnswer, ExamViolation
count = ExamAttempt.objects.count()
ExamAnswer.objects.all().delete()
ExamViolation.objects.all().delete()
ExamAttempt.objects.all().delete()
print(f'Cleared {count} exam attempts. Ready for next load test run.')
