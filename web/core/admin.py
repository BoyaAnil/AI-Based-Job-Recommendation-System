from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Resume, Job, MatchResult, Recommendation, SavedJob


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
    list_display = ("title", "company", "location", "level", "salary_display", "skills_count", "has_apply_link", "created_status")
    list_filter = ("location", "level", "created_at")
    search_fields = ("title", "company", "location", "description")
    readonly_fields = ("created_at", "skills_preview")
    
    fieldsets = (
        ("📋 Job Details", {
            "fields": ("title", "company", "location", "level"),
            "classes": ("wide",)
        }),
        ("💰 Compensation", {
            "fields": ("salary_range",),
            "classes": ("wide",)
        }),
        ("📝 Description & Skills", {
            "fields": ("description", "required_skills", "skills_preview"),
            "classes": ("wide", "collapse")
        }),
        ("🔗 Application Link", {
            "fields": ("apply_link",),
            "classes": ("wide",)
        }),
        ("📊 Metadata", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )
    
    actions = ["mark_verified", "clear_skills"]
    
    class Media:
        css = {
            'all': ('admin/css/job_admin.css',)
        }
    
    def salary_display(self, obj):
        """Display salary range with styling."""
        if obj.salary_range:
            return format_html(
                '<span style="color: #10b981; font-weight: 600;">{}</span>',
                obj.salary_range
            )
        return format_html('<span style="color: #6b7280;">Not specified</span>')
    salary_display.short_description = "Salary"
    
    def skills_count(self, obj):
        """Show number of required skills."""
        count = len(obj.required_skills) if obj.required_skills else 0
        if count > 0:
            return format_html(
                '<span style="background: #6366f1; color: white; padding: 3px 8px; border-radius: 12px; font-weight: 600;">{} skills</span>',
                count
            )
        return format_html('<span style="color: #9ca3af;">None</span>')
    skills_count.short_description = "Skills"
    
    def has_apply_link(self, obj):
        """Show if job has apply link."""
        if obj.apply_link:
            return format_html(
                '<a href="{}" target="_blank" style="color: #6366f1; text-decoration: none;">✓ Link</a>',
                obj.apply_link
            )
        return format_html('<span style="color: #ef4444;">No Link</span>')
    has_apply_link.short_description = "Apply Link"
    
    def created_status(self, obj):
        """Show when job was created."""
        import datetime
        
        # Handle None created_at (newly created jobs not yet saved)
        if not obj.created_at:
            return format_html('<span style="color: #f59e0b;">Unsaved</span>')
        
        now = datetime.datetime.now(obj.created_at.tzinfo) if obj.created_at.tzinfo else datetime.datetime.now()
        delta = now - obj.created_at
        
        if delta.days == 0:
            return format_html('<span style="color: #10b981; font-weight: 600;">Today</span>')
        elif delta.days == 1:
            return format_html('<span style="color: #3b82f6;">Yesterday</span>')
        elif delta.days < 7:
            return format_html('<span style="color: #8b5cf6;">{} days ago</span>', delta.days)
        else:
            return format_html('<span style="color: #6b7280;">{} days ago</span>', delta.days)
    created_status.short_description = "Added"
    
    def skills_preview(self, obj):
        """Preview skills in a nicely formatted way."""
        if obj.required_skills:
            skills_html = " ".join([
                f'<span style="background: #ec4899; color: white; padding: 4px 10px; border-radius: 20px; margin: 3px; display: inline-block; font-size: 12px;">{skill}</span>'
                for skill in obj.required_skills[:10]
            ])
            if len(obj.required_skills) > 10:
                skills_html += f'<br/><small style="color: #6b7280;">+{len(obj.required_skills) - 10} more skills</small>'
            return format_html(skills_html)
        return "No skills specified"
    skills_preview.short_description = "Skills Preview"
    
    def mark_verified(self, request, queryset):
        """Bulk action to mark jobs as verified (example action)."""
        count = queryset.count()
        self.message_user(request, f"{count} job(s) marked.", level=25)
    mark_verified.short_description = "✓ Mark as verified"
    
    def clear_skills(self, request, queryset):
        """Bulk action to clear skills from selected jobs."""
        count = 0
        for job in queryset:
            if job.required_skills:
                job.required_skills = []
                job.save()
                count += 1
        self.message_user(request, f"Cleared skills from {count} job(s).")
    clear_skills.short_description = "Clear required skills"


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display = ("resume", "job", "score", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("resume__user__username", "job__title", "job__company")
    readonly_fields = ("created_at", "score", "matched_skills", "missing_skills")


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
