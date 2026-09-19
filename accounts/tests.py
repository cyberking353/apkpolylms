from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Student

PORTAL_URL = 'https://portal.example.com/sso'


@override_settings(PORTAL_LOGIN_URL=PORTAL_URL)
class LoginRedirectTests(TestCase):
    def test_anonymous_login_redirects_to_portal(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertRedirects(resp, PORTAL_URL, fetch_redirect_response=False)

    def test_authenticated_student_redirects_to_dashboard(self):
        user = Student.objects.create_user(username='a', password='x')
        self.client.force_login(user)
        resp = self.client.get(reverse('accounts:login'))
        self.assertRedirects(resp, reverse('courses:dashboard'))

    def test_authenticated_staff_redirects_to_portal(self):
        user = Student.objects.create_user(
            username='boss', password='x', role='student', is_staff=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('accounts:login'))
        self.assertRedirects(resp, reverse('portal:dashboard'))

    def test_login_required_page_bounces_through_lms_login_to_portal(self):
        # @login_required sends to LOGIN_URL first (with ?next=), and that URL
        # then 302s to the Portal — so the full chain lands on the Portal.
        resp = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
                             fetch_redirect_response=False)
        resp2 = self.client.get(resp.url)
        self.assertRedirects(resp2, PORTAL_URL, fetch_redirect_response=False)


@override_settings(PORTAL_LOGIN_URL=PORTAL_URL)
class LogoutRedirectTests(TestCase):
    def test_logout_redirects_to_portal(self):
        user = Student.objects.create_user(username='a', password='x')
        self.client.force_login(user)
        resp = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(resp, PORTAL_URL, fetch_redirect_response=False)