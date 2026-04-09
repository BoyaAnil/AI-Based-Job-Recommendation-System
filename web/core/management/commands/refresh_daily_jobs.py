from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from core.job_refresh import refresh_jobs_daily_if_needed

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh jobs in database daily from job APIs (India-focused)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if refresh window not reached',
        )
        parser.add_argument(
            '--query',
            type=str,
            default=None,
            help='Job query (default: software developer)',
        )
        parser.add_argument(
            '--location',
            type=str,
            default=None,
            help='Job location (default: India)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Max jobs to fetch (default: 100)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'Starting daily job refresh at {timezone.now()}...')
        )

        try:
            result = refresh_jobs_daily_if_needed(
                force=options['force'],
                query=options['query'],
                location=options['location'],
                limit=options['limit'],
            )

            if result.get('executed'):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Refresh successful!\n"
                        f"  Source: {result.get('source')}\n"
                        f"  Query: {result.get('query')}\n"
                        f"  Location: {result.get('location')}\n"
                        f"  Added: {result.get('added')} jobs\n"
                        f"  Updated: {result.get('updated')} jobs\n"
                        f"  Total in DB: {result.get('total')} jobs"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⊘ Refresh skipped\n"
                        f"  Reason: {result.get('reason')}\n"
                        f"  Status: {result.get('status')}"
                    )
                )

        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(f"✗ Refresh failed: {exc}")
            )
            raise
