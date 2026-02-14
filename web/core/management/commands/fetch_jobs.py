from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Job
from core.services import AIServiceError, fetch_jobs_auto, fetch_jsearch_jobs, fetch_muse_jobs, fetch_remotive_jobs


class Command(BaseCommand):
    help = "Fetch real jobs from external sources and populate the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            type=str,
            default="developer",
            help="Job search query (default: developer). Used by JSearch source.",
        )
        parser.add_argument(
            "--location",
            type=str,
            default="India",
            help="Job location (default: India). Used by JSearch source.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Number of jobs to fetch (default: 50)",
        )
        parser.add_argument(
            "--source",
            type=str,
            default="auto",
            choices=["auto", "jsearch", "themuse", "remotive"],
            help="Job source: auto|jsearch|themuse|remotive (default: auto)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing jobs before saving fetched jobs",
        )
        parser.add_argument(
            "--require-location-match",
            action="store_true",
            help="Only keep jobs whose location contains the provided --location text",
        )

    def _fetch_jobs(self, source: str, query: str, location: str, limit: int):
        if source == "jsearch":
            return fetch_jsearch_jobs(query=query, location=location, limit=limit), "jsearch"
        if source == "themuse":
            return fetch_muse_jobs(query=query, location=location, limit=limit), "themuse"
        if source == "remotive":
            return fetch_remotive_jobs(limit=limit), "remotive"
        return fetch_jobs_auto(query=query, location=location, limit=limit)

    def handle(self, *args, **options):
        query = options["query"]
        location = options["location"]
        limit = options["limit"]
        source = options["source"]
        clear = options["clear"]
        require_location_match = options["require_location_match"]

        try:
            jobs_data, chosen_source = self._fetch_jobs(source, query, location, limit)

            if require_location_match and location:
                location_l = location.lower()
                filtered_jobs = [
                    row for row in jobs_data if location_l in (row.get("location", "") or "").lower()
                ]
                removed = len(jobs_data) - len(filtered_jobs)
                jobs_data = filtered_jobs
                self.stdout.write(
                    f"Location filter '{location}' removed {removed} non-matching job(s)."
                )

            if not jobs_data:
                self.stdout.write(
                    self.style.WARNING("No jobs found. Check API configuration or search parameters.")
                )
                return

            if clear:
                count, _ = Job.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"Deleted {count} existing jobs"))

            if chosen_source == "jsearch":
                self.stdout.write(
                    f"\nFetching {limit} jobs from '{chosen_source}' for query '{query}' in {location}..."
                )
            else:
                self.stdout.write(f"\nFetching {limit} jobs from '{chosen_source}'...")

            created_count = 0
            updated_count = 0
            skipped_count = 0
            refresh_time = timezone.now()

            for job_data in jobs_data:
                try:
                    if not job_data.get("title") or not job_data.get("company"):
                        skipped_count += 1
                        continue

                    defaults = {
                        "level": job_data.get("level", "Mid"),
                        "salary_range": job_data.get("salary_range", ""),
                        "description": job_data.get("description", "No description available"),
                        "required_skills": job_data.get("required_skills", []),
                        "apply_link": job_data.get("apply_link", ""),
                        # Used to surface latest imports at the top of the jobs page.
                        "created_at": refresh_time,
                    }
                    _, created = Job.objects.update_or_create(
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data["location"],
                        defaults=defaults,
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(f"  + {job_data['title']} at {job_data['company']}")
                    else:
                        updated_count += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Error saving job: {exc}"))
                    continue

            total_jobs = Job.objects.count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully fetched jobs!\n"
                    f"  Source used: {chosen_source}\n"
                    f"  Created: {created_count}\n"
                    f"  Updated: {updated_count}\n"
                    f"  Skipped (duplicates): {skipped_count}\n"
                    f"  Total jobs in database: {total_jobs}\n"
                )
            )

        except AIServiceError as exc:
            self.stdout.write(self.style.ERROR(f"Failed to fetch jobs: {exc}"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Unexpected error: {exc}"))
