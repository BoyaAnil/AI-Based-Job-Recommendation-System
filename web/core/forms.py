import re
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, AuthenticationForm
from django.core.validators import URLValidator

from .models import Resume, Job, UserProfile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "placeholder": "Choose a username",
            "autocomplete": "username",
        })
        self.fields["email"].widget.attrs.update({
            "placeholder": "name@company.com",
            "autocomplete": "email",
        })
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Create a strong password",
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirm your password",
            "autocomplete": "new-password",
        })


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "placeholder": "Username or email",
            "autocomplete": "username",
        })
        self.fields["password"].widget.attrs.update({
            "placeholder": "Password",
            "autocomplete": "current-password",
        })


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


class FakeJobDetectionForm(forms.Form):
    job_title = forms.CharField(max_length=200, required=False, label="Job Title")
    company = forms.CharField(max_length=200, required=False)
    location = forms.CharField(max_length=200, required=False)
    salary_range = forms.CharField(max_length=100, required=False, label="Salary")
    apply_link = forms.CharField(
        required=False,
        label="Job Link",
        help_text="Paste the job post URL. A missing https:// will be added automatically.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text="Paste the job description, recruiter message, or both.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "job_title": "Backend Developer",
            "company": "Acme Technologies",
            "location": "Bengaluru / Remote",
            "salary_range": "12-18 LPA",
            "apply_link": "company.com/careers/backend-developer",
            "description": "Paste the full job description or recruiter message here...",
        }
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs.setdefault("placeholder", placeholder)

    def clean_apply_link(self):
        raw_value = (self.cleaned_data.get("apply_link") or "").strip()
        if not raw_value:
            return ""

        normalized = raw_value
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", normalized):
            normalized = f"https://{normalized}"

        validator = URLValidator(schemes=["http", "https"])
        validator(normalized)
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        description = (cleaned_data.get("description") or "").strip()
        apply_link = (cleaned_data.get("apply_link") or "").strip()
        if not description and not apply_link:
            raise forms.ValidationError("Provide a job description, a job link, or both.")
        return cleaned_data


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


class ProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("profile_photo",)


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
