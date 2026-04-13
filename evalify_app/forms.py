
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .validators import validate_student_email, validate_faculty_email

class CustomUserCreationForm(UserCreationForm):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('faculty', 'Faculty'),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)
    email = forms.EmailField()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        role = self.cleaned_data.get('role')
        
        if role == 'student':
            validate_student_email(email)
        elif role == 'faculty':
            validate_faculty_email(email)
        else:
            raise forms.ValidationError('Please select a valid role')
        
        return email

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password1', 'password2']