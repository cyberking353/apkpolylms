from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Student


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email Address')


class ProfileForm(forms.ModelForm):
    """
    Students can edit their own personal info only.
    Department and academic_level are intentionally NOT here — those are
    admin-controlled (see accounts.admin.StudentAdmin) since they determine
    which courses the student sees.
    """
    class Meta:
        model  = Student
        fields = ('first_name', 'last_name', 'matric_number', 'bio', 'avatar')
