# Architecture

## High-Level Components

1. `web/` Django application
- User authentication and profile management
- Resume upload and parsed-result presentation
- Job browsing, match, skill-gap analysis, recommendations
- Admin dashboard and job CRUD
- Persistence layer (SQLite by default, can use Postgres/MySQL)

2. `ai/` Flask microservice
- Resume parsing for PDF/DOCX
- Skill extraction and heuristic entity extraction
- Match scoring and recommendation scoring
- Skill-gap suggestions

3. External job providers
- JSearch (RapidAPI)
- The Muse
- Remotive

## Runtime Communication

- Django calls Flask over HTTP using `AI_SERVICE_URL`.
- Calls are made for:
  - `POST /parse_resume`
  - `POST /match`
  - `POST /recommend_jobs`
  - `POST /skill_gap`
- If Flask is unreachable or returns 5xx and `AI_SERVICE_FALLBACK_LOCAL=true`, Django executes local fallback logic in `web/core/services.py`.

## Request Flow (Resume Match)

1. User uploads resume in Django (`/resumes/upload/`).
2. Django stores file under `media/resumes/`.
3. Django sends parse request to Flask (`/parse_resume`).
4. Parsed output is stored in `Resume.raw_text` and `Resume.extracted_json`.
5. User selects a job and triggers match (`/jobs/<id>/match/`).
6. Django calls Flask (`/match`) and persists a `MatchResult`.
7. UI renders score, matched skills, and missing skills.

## Request Flow (Recommendations)

1. User picks a resume on `/recommendations/`.
2. Django optionally refreshes job pool via external providers.
3. Django sends resume + job pool to Flask (`/recommend_jobs`).
4. Django stores top recommendations in `Recommendation`.
5. UI displays ranked job recommendations.

## Data Boundaries

- Flask is stateless and does not own application database records.
- Django owns persistence, auth, and user-facing business flows.
- Shared file data is the uploaded resume path and extracted JSON payload.
