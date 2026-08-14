from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, MatricLoginForm, ProfileForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_home_url_for(request.user))
    if request.method == 'POST':
        form = MatricLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # The SMS gates LMS access; the LMS enforces it too.
            if not getattr(user, 'lms_access', True):
                messages.error(request, 'Your LMS access is disabled. Please contact the school office.')
                return render(request, 'accounts/login.html', {'form': form})
            if not user.is_active:
                messages.error(request, 'This account has been deactivated. Please contact the school office.')
                return render(request, 'accounts/login.html', {'form': form})
            login(request, user)
            next_url = request.GET.get('next') or _home_url_for(user)
            messages.success(request, f'Welcome back, {user.first_name}! 👋')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid matric number/email or password.')
    else:
        form = MatricLoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def _home_url_for(user):
    """Lecturers land on their own course dashboard; students land on the student dashboard."""
    if getattr(user, 'role', 'student') == 'lecturer':
        return reverse('courses:lecturer_dashboard')
    return reverse('courses:dashboard')


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('courses:landing')


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
