import logging
import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .location_filters import deduplicate_jobs, filter_jobs_by_location_targets, split_location_targets
from .models import Job, JobRefreshState
from .services import AIServiceError, fetch_jobs_auto

logger = logging.getLogger(__name__)
DAILY_REFRESH_STATE_KEY = "daily_jobs_auto_refresh"


def fetch_jobs_for_location_targets(*, query, location, limit, require_location_match=True):
    location_targets = split_location_targets(location) or [""]
    per_target_limit = max(5, math.ceil(limit / len(location_targets)))
    collected_jobs = []
    sources = []

    for target in location_targets:
        jobs_batch, source = fetch_jobs_auto(
            query=query,
            location=target,
            limit=per_target_limit,
        )
        if require_location_match and target:
            jobs_batch = filter_jobs_by_location_targets(jobs_batch, target)
        collected_jobs.extend(jobs_batch)
        if source and source not in sources:
            sources.append(source)

    return deduplicate_jobs(collected_jobs)[:limit], ", ".join(sources)


def merge_jobs_into_database(fetched_jobs, default_location, refresh_time=None):
    api_jobs_added = 0
    api_jobs_updated = 0
    refresh_time = refresh_time or timezone.now()

    for job_data in fetched_jobs:
        if not job_data.get("title") or not job_data.get("company"):
            continue

        defaults = {
            "level": job_data.get("level", "Mid"),
            "salary_range": job_data.get("salary_range", ""),
            "description": job_data.get("description", "No description available"),
            "required_skills": job_data.get("required_skills", []),
            "apply_link": job_data.get("apply_link", ""),
            "created_at": refresh_time,
        }
        _, created = Job.objects.update_or_create(
            title=job_data["title"],
            company=job_data["company"],
            location=(job_data.get("location") or default_location or "Remote"),
            defaults=defaults,
        )
        if created:
            api_jobs_added += 1
        else:
            api_jobs_updated += 1

    return api_jobs_added, api_jobs_updated


def refresh_jobs_daily_if_needed(*, force=False, query=None, location=None, limit=None, require_location_match=None):
    if not force and not getattr(settings, "AUTO_DAILY_JOB_REFRESH", True):
        return {
            "executed": False,
            "status": "disabled",
            "reason": "auto refresh disabled",
        }

    now = timezone.now()
    refresh_window = timedelta(hours=max(1, int(getattr(settings, "AUTO_DAILY_JOB_REFRESH_HOURS", 24))))
    retry_window = timedelta(minutes=max(5, int(getattr(settings, "AUTO_DAILY_JOB_REFRESH_RETRY_MINUTES", 60))))

    state, _ = JobRefreshState.objects.get_or_create(key=DAILY_REFRESH_STATE_KEY)

    if not force and state.last_success_at and (now - state.last_success_at) < refresh_window:
        return {
            "executed": False,
            "status": "skipped",
            "reason": "refresh window not reached",
            "last_success_at": state.last_success_at,
            "next_refresh_at": state.last_success_at + refresh_window,
            "source": state.last_source,
        }

    if not force and state.last_attempted_at and (now - state.last_attempted_at) < retry_window:
        return {
            "executed": False,
            "status": "skipped",
            "reason": "retry window not reached",
            "last_attempted_at": state.last_attempted_at,
            "source": state.last_source,
        }

    state.last_attempted_at = now
    state.save(update_fields=["last_attempted_at", "updated_at"])

    api_query = (query or getattr(settings, "AUTO_DAILY_JOB_QUERY", "software developer") or "software developer").strip()
    api_location = (location or getattr(settings, "AUTO_DAILY_JOB_LOCATION", "Remote | India") or "Remote | India").strip()
    api_limit = max(5, min(int(limit or getattr(settings, "AUTO_DAILY_JOB_LIMIT", 100)), 150))
    if require_location_match is None:
        require_location_match = getattr(settings, "AUTO_DAILY_JOB_REQUIRE_LOCATION_MATCH", True)

    try:
        fetched_jobs, api_source = fetch_jobs_for_location_targets(
            query=api_query,
            location=api_location,
            limit=api_limit,
            require_location_match=require_location_match,
        )

        added, updated = merge_jobs_into_database(fetched_jobs, api_location, refresh_time=now)
        state.last_success_at = timezone.now()
        state.last_source = api_source
        state.last_error = ""
        state.save(update_fields=["last_success_at", "last_source", "last_error", "updated_at"])
        logger.info(
            "Daily jobs refresh complete. Source=%s Added=%s Updated=%s",
            api_source,
            added,
            updated,
        )
        return {
            "executed": True,
            "status": "refreshed",
            "source": api_source,
            "query": api_query,
            "location": api_location,
            "limit": api_limit,
            "added": added,
            "updated": updated,
            "total": Job.objects.count(),
            "last_success_at": state.last_success_at,
        }
    except AIServiceError as exc:
        state.last_error = str(exc)[:1000]
        state.save(update_fields=["last_error", "updated_at"])
        logger.warning("Daily jobs refresh failed: %s", exc)
        raise
    except Exception as exc:
        state.last_error = str(exc)[:1000]
        state.save(update_fields=["last_error", "updated_at"])
        logger.exception("Unexpected error during daily jobs refresh: %s", exc)
        raise
