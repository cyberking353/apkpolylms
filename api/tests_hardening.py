"""Regression tests for production hardening (VPS deploy prep).

Covers the loopholes closed before shipping:
  - /healthz liveness probe with DB check
  - constant-time Authoriziation token compare (wrong token never accepted)
  - oversized request body guard on sync/SSO endpoints
  - upload validation (docs, images)
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse

TEST_TOKEN = 'test-lms-api-token'
AUTH = {'HTTP_AUTHORIZATION': f'Bearer {TEST_TOKEN}'}


class HealthzTests(TestCase):
    def test_healthz_returns_ok_and_db_status(self):
        resp = self.client.get(reverse('healthz'))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['db'], 'ok')


@override_settings(LMS_API_TOKEN=TEST_TOKEN)
class SyncEndpointHardeningTests(TestCase):
    URL = '/api/v1/sync/students'

    def test_wrong_token_is_rejected(self):
        resp = self.client.post(self.URL, data=json.dumps({}),
                                content_type='application/json',
                                HTTP_AUTHORIZATION='Bearer not-the-token')
        self.assertEqual(resp.status_code, 401)

    def test_oversized_content_length_is_413(self):
        resp = self.client.post(self.URL, data={},
                                content_type='application/json',
                                CONTENT_LENGTH='99999999', **AUTH)
        self.assertEqual(resp.status_code, 413)

    def test_valid_token_passes_guard(self):
        resp = self.client.post(self.URL, data=json.dumps({}),
                                content_type='application/json', **AUTH)
        self.assertNotEqual(resp.status_code, 401)
        self.assertNotEqual(resp.status_code, 413)


class UploadValidationTests(TestCase):
    def test_doc_upload_rejects_bad_extension(self):
        from alhikma_lms.uploads import validate_doc_upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile('notes.exe', b'MZxxxx')
        with self.assertRaises(ValueError):
            validate_doc_upload(bad)

    def test_doc_upload_accepts_pdf(self):
        from alhikma_lms.uploads import validate_doc_upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        good = SimpleUploadedFile('notes.pdf', b'%PDF-1.4')
        validate_doc_upload(good)  # must not raise

    def test_doc_upload_rejects_oversized_file(self):
        from alhikma_lms.uploads import validate_doc_upload, MAX_DOC_BYTES
        from django.core.files.uploadedfile import SimpleUploadedFile
        big = SimpleUploadedFile('notes.pdf', b'a' * (MAX_DOC_BYTES + 1))
        with self.assertRaises(ValueError):
            validate_doc_upload(big)

    def test_image_upload_rejects_script_file(self):
        from alhikma_lms.uploads import validate_image_upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile('pic.php', b'<?php ...')
        with self.assertRaises(ValueError):
            validate_image_upload(bad)