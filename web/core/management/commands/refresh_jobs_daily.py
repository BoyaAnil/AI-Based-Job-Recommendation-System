from django.core.management.base import BaseCommand

from core.job_refresh import refresh_jobs_daily_if_needed
from core.services import AIServiceError


class Command(BaseCommand):
    help = "Refresh the job catalog using the daily refresh rules. Safe for cron or Task Scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run immediately even if the daily refresh window has not elapsed.")
        parser.add_argument("--query", type=str, default="", help="Override the daily job query for this run.")
        parser.add_argument("--location", type=str, default="", help="Override the daily job location for this run.")
        parser.add_argument("--limit", type=int, default=0, help="Override the daily job fetch limit for this run.")
        parser.add_argument("--require-location-match", action="store_true", help="Only keep jobs whose location contains the provided location text.")
        parser.add_argument("--allow-any-location", action="store_true", help="Do not filter fetched jobs by location.")

    def handle(self, *args, **options):
        if options["require_location_match"] and options["allow_any_location"]:
            self.stderr.write(self.style.ERROR("Use either --require-location-match or --allow-any-location, not both."))
            return

        require_location_match = None
        if options["require_location_match"]:
            require_location_match = True
        elif options["allow_any_location"]:
            require_location_match = False

        try:
            result = refresh_jobs_daily_if_needed(
                force=options["force"],
                query=options["query"] or None,
                location=options["location"] or None,
                limit=options["limit"] or None,
                require_location_match=require_location_match,
            )
        except AIServiceError as exc:
            self.stderr.write(self.style.ERROR(f"Daily job refresh failed: {exc}"))
            return
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Unexpected daily job refresh error: {exc}"))
            return

        if not result.get("executed"):
            reason = result.get("reason", "not executed")
            self.stdout.write(self.style.WARNING(f"Daily job refresh skipped: {reason}"))
            if result.get("last_success_at"):
                self.stdout.write(f"Last success: {result['last_success_at']}")
            if result.get("next_refresh_at"):
                self.stdout.write(f"Next eligible refresh: {result['next_refresh_at']}")
            return

        self.stdout.write(self.style.SUCCESS(
            "Daily job refresh complete\n"
            f"  Source: {result.get('source', '')}\n"
            f"  Query: {result.get('query', '')}\n"
            f"  Location: {result.get('location', '')}\n"
            f"  Added: {result.get('added', 0)}\n"
            f"  Updated: {result.get('updated', 0)}\n"
            f"  Total jobs: {result.get('total', 0)}"
        ))
