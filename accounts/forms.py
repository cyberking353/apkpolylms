from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Student


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email Address')


class MatricLoginForm(AuthenticationForm):
    """
    Lets students log in with their matric number OR email. The SMS owns
    identity, so a student may not remember the LMS email — matric number
    is the key they always know.
    """
    username = forms.CharField(label='Matric Number or Email')

    def clean_username(self):
        raw = self.cleaned_data.get('username', '').strip()
        if '@' in raw:
            return raw
        # Not an email → treat it as a matric number and resolve to the
        # matching account's email (the username field is the email).
        try:
            student = Student.objects.get(matric_number=raw)
        except Student.DoesNotExist:
            raise forms.ValidationError('No account found with that matric number.')
        except Student.MultipleObjectsReturned:
            raise forms.ValidationError('Multiple accounts found for that matric number.')
        return student.email


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
