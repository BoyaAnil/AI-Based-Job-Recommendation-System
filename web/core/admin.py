from django import forms
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Job, MatchResult, Recommendation, Resume, SavedJob


def _parse_skills_text(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    parts = [part.strip().lower() for part in raw_value.replace("\n", ",").split(",")]
    return [part for part in parts if part]


class JobAdminForm(forms.ModelForm):
    required_skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "python, sql, django"}),
        help_text="Enter comma-separated skills.",
    )

    class Meta:
        model = Job
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["required_skills"].initial = ", ".join(self.instance.required_skills or [])

    def clean_required_skills(self):
        return _parse_skills_text(self.cleaned_data.get("required_skills", ""))


class MatchResultAdminForm(forms.ModelForm):
    matched_skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "python, sql"}),
        help_text="Enter comma-separated matched skills.",
    )
    missing_skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "docker, aws"}),
        help_text="Enter comma-separated missing skills.",
    )

    class Meta:
        model = MatchResult
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["matched_skills"].initial = ", ".join(self.instance.matched_skills or [])
            self.fields["missing_skills"].initial = ", ".join(self.instance.missing_skills or [])

    def clean_matched_skills(self):
        return _parse_skills_text(self.cleaned_data.get("matched_skills", ""))

    def clean_missing_skills(self):
        return _parse_skills_text(self.cleaned_data.get("missing_skills", ""))


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "uploaded_at", "has_text")
    search_fields = ("user__username",)
    readonly_fields = ("uploaded_at",)

    def has_text(self, obj):
        return bool(obj.raw_text)

    has_text.short_description = "Text Parsed"
    has_text.boolean = True


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    form = JobAdminForm
    list_display = ("title", "company", "location", "level", "salary_display", "skills_count", "has_apply_link", "created_status")
    list_filter = ("location", "level", "created_at")
    search_fields = ("title", "company", "location", "description")
    readonly_fields = ("created_at", "skills_preview")

    fieldsets = (
        ("Job Details", {
            "fields": ("title", "company", "location", "level"),
            "classes": ("wide",)
        }),
        ("Compensation", {
            "fields": ("salary_range",),
            "classes": ("wide",)
        }),
        ("Description and Skills", {
            "fields": ("description", "required_skills", "skills_preview"),
            "classes": ("wide",)
        }),
        ("Application Link", {
            "fields": ("apply_link",),
            "classes": ("wide",)
        }),
        ("Metadata", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )

    actions = ["mark_verified", "clear_skills"]

    def salary_display(self, obj):
        if obj.salary_range:
            return format_html('<span style="color: #10b981; font-weight: 600;">{}</span>', obj.salary_range)
        return format_html('<span style="color: #6b7280;">Not specified</span>')

    salary_display.short_description = "Salary"

    def skills_count(self, obj):
        count = len(obj.required_skills) if obj.required_skills else 0
        if count > 0:
            return format_html(
                '<span style="background: #6366f1; color: white; padding: 3px 8px; border-radius: 12px; font-weight: 600;">{} skills</span>',
                count,
            )
        return format_html('<span style="color: #9ca3af;">None</span>')

    skills_count.short_description = "Skills"

    def has_apply_link(self, obj):
        if obj.apply_link:
            return format_html('<a href="{}" target="_blank" style="color: #6366f1; text-decoration: none;">Link</a>', obj.apply_link)
        return format_html('<span style="color: #ef4444;">No Link</span>')

    has_apply_link.short_description = "Apply Link"

    def created_status(self, obj):
        if not obj.created_at:
            return format_html('<span style="color: #f59e0b;">Unsaved</span>')
        delta = timezone.now() - obj.created_at
        if delta.days == 0:
            return format_html('<span style="color: #10b981; font-weight: 600;">Today</span>')
        if delta.days == 1:
            return format_html('<span style="color: #3b82f6;">Yesterday</span>')
        if delta.days < 7:
            return format_html('<span style="color: #8b5cf6;">{} days ago</span>', delta.days)
        return format_html('<span style="color: #6b7280;">{} days ago</span>', delta.days)

    created_status.short_description = "Added"

    def skills_preview(self, obj):
        if obj.required_skills:
            skills_html = " ".join([
                f'<span style="background: #0ea5e9; color: white; padding: 4px 10px; border-radius: 20px; margin: 3px; display: inline-block; font-size: 12px;">{skill}</span>'
                for skill in obj.required_skills[:10]
            ])
            if len(obj.required_skills) > 10:
                skills_html += f'<br/><small style="color: #6b7280;">+{len(obj.required_skills) - 10} more skills</small>'
            return format_html(skills_html)
        return "No skills specified"

    skills_preview.short_description = "Skills Preview"

    def mark_verified(self, request, queryset):
        count = queryset.count()
        self.message_user(request, f"{count} job(s) marked.", level=25)

    mark_verified.short_description = "Mark as verified"

    def clear_skills(self, request, queryset):
        count = 0
        for job in queryset:
            if job.required_skills:
                job.required_skills = []
                job.save()
                count += 1
        self.message_user(request, f"Cleared skills from {count} job(s).")

    clear_skills.short_description = "Clear required skills"

    def save_model(self, request, obj, form, change):
        if not obj.created_at:
            obj.created_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    form = MatchResultAdminForm
    list_display = ("resume", "job", "score", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("resume__user__username", "job__title", "job__company")
    readonly_fields = ("created_at",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("resume", "job", "score", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("resume__user__username", "job__title")
    readonly_fields = ("created_at",)


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "job__title", "job__company")
    readonly_fields = ("created_at",)
