# Data Model

Source: `web/core/models.py`

## Core Entities

### `Resume`

- `user` -> FK to Django user
- `original_file` -> uploaded PDF/DOCX
- `uploaded_at`
- `raw_text`
- `extracted_json`

Purpose: Stores uploaded resume plus parsed output.

### `Job`

- `title`, `company`, `location`, `level`
- `salary_range`
- `description`
- `required_skills` (JSON list)
- `apply_link`
- `created_at`

Purpose: Normalized job posting catalog for browsing/matching.

### `MatchResult`

- `resume` -> FK `Resume`
- `job` -> FK `Job`
- `score`
- `matched_skills` (JSON list)
- `missing_skills` (JSON list)
- `created_at`

Purpose: Stores persisted match outcomes.

### `Recommendation`

- `resume` -> FK `Resume`
- `job` -> FK `Job`
- `score`
- `reason`
- `created_at`

Purpose: Stores ranked recommendations for a resume.

### `SavedJob`

- `user` -> FK Django user
- `job` -> FK `Job`
- `created_at`
- Unique constraint on (`user`, `job`)

Purpose: User bookmark list.

### `UserProfile`

- `user` -> OneToOne Django user (`related_name="profile"`)
- `profile_photo`
- `bio`, `phone`, `location`
- `linkedin_url`, `github_url`, `website`
- `updated_at`

Purpose: Extended profile metadata.

## Relationship Summary

- One user -> many resumes
- One user -> many saved jobs
- One resume -> many match results
- One resume -> many recommendations
- One job -> many match results/recommendations/saved records

## Data Notes

- Resume parsed output is denormalized JSON (`extracted_json`) for simple rendering and export.
- `created_at` in `Job` is used to prioritize freshly imported jobs in UI ordering.
