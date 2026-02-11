from django.core.management.base import BaseCommand
from django.db import IntegrityError
from core.models import Job
from core.services import fetch_jsearch_jobs, AIServiceError


class Command(BaseCommand):
    help = "Fetch real jobs from JSearch API and populate the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            type=str,
            default="developer",
            help="Job search query (default: developer)",
        )
        parser.add_argument(
            "--location",
            type=str,
            default="India",
            help="Job location (default: India)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Number of jobs to fetch (default: 50)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing jobs before fetching new ones",
        )

    def handle(self, *args, **options):
        query = options["query"]
        location = options["location"]
        limit = options["limit"]
        clear = options["clear"]

        if clear:
            count, _ = Job.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} existing jobs"))

        try:
            self.stdout.write(f"\nFetching {limit} jobs for query '{query}' in {location}...")
            jobs_data = fetch_jsearch_jobs(query=query, location=location, limit=limit)

            if not jobs_data:
                self.stdout.write(self.style.WARNING("No jobs found. Check your API key or search parameters."))
                return

            created_count = 0
            skipped_count = 0

            for job_data in jobs_data:
                try:
                    # Avoid duplicates by checking title + company combination
                    existing = Job.objects.filter(
                        title=job_data["title"], company=job_data["company"]
                    ).exists()

                    if existing:
                        skipped_count += 1
                        continue

                    Job.objects.create(
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data["location"],
                        level=job_data["level"],
                        salary_range=job_data.get("salary_range", ""),
                        description=job_data["description"],
                        required_skills=job_data.get("required_skills", []),
                        apply_link=job_data.get("apply_link", ""),
                    )
                    created_count += 1
                    self.stdout.write(f"  ✓ {job_data['title']} at {job_data['company']}")
                except IntegrityError:
                    skipped_count += 1
                    continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  ✗ Error saving job: {e}"))
                    continue

            total_jobs = Job.objects.count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully fetched jobs!\n"
                    f"  Created: {created_count}\n"
                    f"  Skipped (duplicates): {skipped_count}\n"
                    f"  Total jobs in database: {total_jobs}\n"
                )
            )

        except AIServiceError as exc:
            self.stdout.write(
                self.style.ERROR(f"Failed to fetch jobs: {exc}")
            )
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(f"Unexpected error: {exc}")
            )
