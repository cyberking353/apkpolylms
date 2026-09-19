from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ProfileForm


def _portal_login_url():
    """The Portal's sign-in page. The user starts login there; it redirects back
    to /sso/callback. Falls back to the LMS landing page if no Portal URL is
    configured (local dev)."""
    return settings.PORTAL_LOGIN_URL or reverse('courses:landing')


def login_view(request):
    """SSO-only. Identity sits with the Portal: anyone hitting the LMS login
    URL bounces straight to the Portal's sign-in page, which then redirects back
    to /sso/callback with a signed assertion. There is no LMS login form."""
    if request.user.is_authenticated:
        return redirect(_home_url_for(request.user))
    return redirect(_portal_login_url())


def _home_url_for(user):
    """Admins land on the portal dashboard; lecturers on their course dashboard;
    students on the student dashboard."""
    if getattr(user, 'is_staff', False):
        return reverse('portal:dashboard')
    if getattr(user, 'role', 'student') == 'lecturer':
        return reverse('courses:lecturer_dashboard')
    return reverse('courses:dashboard')


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect(_portal_login_url())


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})
