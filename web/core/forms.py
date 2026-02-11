from pathlib import Path
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm

from .models import Resume, Job, UserProfile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ("original_file",)

    def clean_original_file(self):
        uploaded_file = self.cleaned_data["original_file"]
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in (".pdf", ".docx"):
            raise forms.ValidationError("Only PDF or DOCX files are allowed.")
        max_size_mb = settings.RESUME_MAX_FILE_SIZE_MB
        if uploaded_file.size > max_size_mb * 1024 * 1024:
            raise forms.ValidationError(f"File size must be under {max_size_mb}MB.")
        return uploaded_file


class JobForm(forms.ModelForm):
    required_skills = forms.CharField(
        required=False,
        help_text="Comma-separated skills (e.g., python, sql, django)"
    )

    class Meta:
        model = Job
        fields = ("title", "company", "location", "level", "salary_range", "description", "required_skills", "apply_link")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["required_skills"].initial = ", ".join(self.instance.required_skills)

    def clean_required_skills(self):
        skills_raw = self.cleaned_data.get("required_skills", "")
        skills = [skill.strip().lower() for skill in skills_raw.split(",") if skill.strip()]
        return skills


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label="First Name")
    last_name = forms.CharField(max_length=150, required=False, label="Last Name")
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ("profile_photo", "bio", "phone", "location", "linkedin_url", "github_url", "website")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.instance and self.instance.user:
            profile.user.first_name = self.cleaned_data.get("first_name", "")
            profile.user.last_name = self.cleaned_data.get("last_name", "")
            profile.user.email = self.cleaned_data.get("email", "")
            if commit:
                profile.user.save()
        if commit:
            profile.save()
        return profile


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Current password"}),
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "New password"}),
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Confirm new password"}),
    )
