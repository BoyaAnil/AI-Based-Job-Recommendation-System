import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.models import Job


class Command(BaseCommand):
    help = "Seed sample jobs and demo users"

    def handle(self, *args, **options):
        root_dir = Path(__file__).resolve().parents[4]
        jobs_path = root_dir / "sample_data" / "jobs.json"

        if jobs_path.exists():
            # Use utf-8-sig to gracefully handle files that include a UTF-8 BOM
            jobs_text = jobs_path.read_text(encoding="utf-8-sig")
            jobs_data = json.loads(jobs_text)
            for job in jobs_data:
                Job.objects.update_or_create(
                    title=job["title"],
                    company=job["company"],
                    defaults={
                        "location": job["location"],
                        "level": job["level"],
                        "salary_range": job.get("salary_range", ""),
                        "description": job["description"],
                        "required_skills": job.get("required_skills", []),
                        "apply_link": job.get("apply_link", ""),
                    }
                )
            self.stdout.write(self.style.SUCCESS(f"Seeded {len(jobs_data)} jobs."))
        else:
            self.stdout.write(self.style.WARNING("jobs.json not found; skipping job seed."))

        User = get_user_model()
        demo_user, _ = User.objects.get_or_create(username="demo", defaults={"email": "demo@example.com"})
        demo_user.set_password("demo1234")
        demo_user.save()

        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True}
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password("admin1234")
        admin_user.save()

        self.stdout.write(self.style.SUCCESS("Demo users created/updated."))
