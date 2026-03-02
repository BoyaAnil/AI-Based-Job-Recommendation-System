import re
from pathlib import Path

from django.conf import settings
from django.db import models

STORAGE_SUFFIX_RE = re.compile(r"^(?P<base>.+)_[A-Za-z0-9]{7}$")


def _strip_storage_suffix(file_name: str) -> str:
    base_name = Path(file_name).name
    stem = Path(base_name).stem
    suffix = Path(base_name).suffix
    match = STORAGE_SUFFIX_RE.match(stem)
    if match:
        stem = match.group("base")
    return f"{stem}{suffix}"


class Resume(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    original_file = models.FileField(upload_to="resumes/")
    original_filename = models.CharField(max_length=255, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    raw_text = models.TextField(blank=True)
    extracted_json = models.JSONField(default=dict, blank=True)

    @property
    def display_name(self) -> str:
        if self.original_filename:
            if self.original_file and self.original_filename == Path(self.original_file.name).name:
                return _strip_storage_suffix(self.original_filename)
            return self.original_filename
        if self.original_file:
            return _strip_storage_suffix(self.original_file.name)
        return f"Resume {self.id}"

    def __str__(self) -> str:
        return f"{self.display_name} for {self.user.username}"


class Job(models.Model):
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    level = models.CharField(max_length=100)
    salary_range = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    required_skills = models.JSONField(default=list, blank=True)
    apply_link = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.title} at {self.company}"


class MatchResult(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    score = models.IntegerField()
    matched_skills = models.JSONField(default=list, blank=True)
    missing_skills = models.JSONField(default=list, blank=True)
    analysis_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Match {self.score} for Resume {self.resume_id}"


class Recommendation(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    score = models.IntegerField()
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Recommendation {self.score} for Resume {self.resume_id}"


class SavedJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "job"], name="unique_saved_job")
        ]

    def __str__(self) -> str:
        return f"Saved {self.job.title} for {self.user.username}"


class JobRefreshState(models.Model):
    key = models.CharField(max_length=64, unique=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_source = models.CharField(max_length=32, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Job refresh state ({self.key})"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    bio = models.TextField(blank=True, help_text="Tell us about yourself")
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=200, blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile for {self.user.username}"
