# AI Based Job Recommendation System

Full-stack monorepo with Django web app and Flask AI microservice.

## Documentation
- Start here: `docs/README.md`
- Quickstart: `docs/quickstart.md`
- Architecture: `docs/architecture.md`
- API: `docs/api.md`
- Deployment: `docs/deployment.md`

## Project Structure
- `web/` Django app (UI, auth, database, dashboards)
- `ai/` Flask AI service (resume parsing, matching, recommendations)
- `sample_data/` seed jobs + sample resume

## Features
- User registration, login, OTP verification, password reset, and profile management
- Resume upload for PDF and DOCX files with extracted text, skills, education, projects, and experience
- ATS-style resume scoring with matched skills, missing skills, keyword coverage, and improvement tips
- Job browsing, detail pages, saved jobs, and resume-to-job match scoring
- Personalized job recommendations based on resume content and extracted skills
- Skill-gap analysis for specific jobs with targeted upskilling suggestions
- Fake job detection with risk signals, trust checks, and warning breakdowns
- Interview simulator with adaptive pressure prompts, scoring, and coaching feedback
- Admin dashboard with job management, analytics, and top-skills insights
- Daily job refresh workflow with external job sources and location filtering
- Offline-friendly NLP using TF-IDF-style similarity, regex extraction, and local fallback logic

## Skills And Technologies
- Backend: Python, Django 6, Flask 3
- Frontend: Django templates, HTML, CSS, JavaScript
- Database: SQLite for local development, optional PostgreSQL and MySQL support
- AI and NLP: TF-IDF-style similarity scoring, regex-based entity extraction, ATS-style scoring pipeline
- File processing: `pdfplumber`, `python-docx`, `Pillow`
- Integrations: `requests`, optional Google Gemini support, JSearch, The Muse, and Remotive job feeds
- DevOps: Docker, Docker Compose, `.env`-based configuration
- Testing: Django test suite and `pytest` for the AI service

## Prerequisites
- Python **3.12+** (required by Django 6.x)
- pip
- (Optional) PostgreSQL or MySQL
  - For MySQL: install `mysqlclient` and set `DATABASE_URL` to a MySQL connection string.
  - For PostgreSQL on Windows: install PostgreSQL locally so `pg_config` is available, or use Docker.

## Local Setup (Recommended)

### 1) Flask AI Service
```bash
cd ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app app run
```

Test the health endpoint:
```bash
curl http://127.0.0.1:5000/health
```

### 2) Django Web App
```bash
cd web
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open: `http://127.0.0.1:8000`

### Demo Users
- `demo / demo1234` (regular user)
- `admin / admin1234` (staff/superuser)

## Seed Data
Run:
```bash
python manage.py seed_demo
```
This loads `sample_data/jobs.json` and creates demo users.

A sample resume is in `sample_data/sample_resume.pdf`.

## Real Jobs (Latest)
To fetch real jobs (instead of sample jobs):
```bash
cd web
python manage.py fetch_jobs --source themuse --query "software" --location "India" --limit 100 --require-location-match --clear
```

- `--source auto`: uses JSearch if `JSEARCH_API_KEY` is set; otherwise falls back to The Muse, then Remotive.
- `--source jsearch`: force JSearch (requires RapidAPI key).
- `--source themuse`: use The Muse public jobs API (no key required).
- `--source remotive`: force Remotive (no key required).
- `--require-location-match`: only keeps jobs whose location contains the `--location` value.

Example for location-specific JSearch:
```bash
python manage.py fetch_jobs --source jsearch --query "python developer" --location "India" --limit 50 --clear
```

## Daily Auto Refresh (Windows)
The web app now supports built-in once-per-day auto refresh through AI when users open pages (Home, Jobs, or Recommendations).  
Configure in `web/.env`:

```bash
AUTO_DAILY_JOB_REFRESH=true
AUTO_DAILY_JOB_REFRESH_HOURS=24
AUTO_DAILY_JOB_REFRESH_RETRY_MINUTES=60
AUTO_DAILY_JOB_QUERY=software developer
AUTO_DAILY_JOB_LOCATION=Remote | India
AUTO_DAILY_JOB_LIMIT=100
AUTO_DAILY_JOB_REQUIRE_LOCATION_MATCH=true
```

You can still use the Windows scheduled task below if you want refreshes at an exact clock time.

The repo includes:
- `web/scripts/daily_job_refresh.bat`
- `web/scripts/register_daily_job_refresh_task.ps1`

Run once to create a scheduled task for 6:00 AM daily:
```powershell
Set-Location 'C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts'
.\register_daily_job_refresh_task.ps1
```

If you prefer manual task creation, use this instead:
```powershell
$taskName='AI Resume Analyzer Daily Job Refresh'
$script='C:\path\to\repo\web\scripts\daily_job_refresh.bat'
$action=New-ScheduledTaskAction -Execute $script
$trigger=New-ScheduledTaskTrigger -Daily -At 6:00AM
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Description 'Refresh latest real jobs daily for AI Resume Analyzer' -Force
```
The default batch script is preconfigured for remote foreign jobs plus India-wide jobs (`--location "Remote | India"`).

## API Contracts (Django -> Flask)

### 1) GET `/health`
Response:
```json
{ "status": "ok" }
```

### 2) POST `/parse_resume`
Input:
```json
{ "file_path": "...", "file_type": "pdf|docx" }
```
Output:
```json
{
  "raw_text": "...",
  "name": "...",
  "email": "...",
  "phone": "...",
  "skills": ["python", "sql"],
  "education": [{"degree": "...", "institute": "...", "year": "..."}],
  "experience": [{"title": "...", "company": "...", "years": "...", "details": "..."}],
  "projects": [{"name": "...", "details": "...", "tech": ["..."]}]
}
```

### 3) POST `/match`
Input:
```json
{
  "resume_text": "...",
  "job": { "title": "...", "description": "...", "required_skills": ["..."] }
}
```
Output:
```json
{
  "score": 0-100,
  "matched_skills": ["..."],
  "missing_skills": ["..."],
  "summary": "...",
  "improvement_tips": ["...", "..."]
}
```

### 4) POST `/recommend_jobs`
Input:
```json
{
  "resume_text": "...",
  "jobs": [ {"id": 1, "title": "...", "description": "...", "required_skills": ["..."] } ],
  "top_n": 10
}
```
Output:
```json
{ "recommendations": [ {"job_id": 1, "score": 85, "reason": "..."} ] }
```

### 5) POST `/skill_gap`
Input:
```json
{
  "resume_text": "...",
  "job": { "title": "...", "description": "...", "required_skills": ["..."] }
}
```
Output:
```json
{
  "matched_skills": ["..."],
  "missing_skills": ["..."],
  "suggestions": ["...", "..."]
}
```

## Docker (Optional)
```bash
docker compose up --build
```
This starts:
- Django on `http://localhost:8000`
- Flask on `http://localhost:5000`
- Postgres on `localhost:5432`
The compose file mounts a shared `/app/media` volume so the Flask service can read uploaded resumes.

If your platform builds Docker from repo root, this repo now includes a root `Dockerfile` that runs the Django web app.

## Deployment Notes
- Use Python `3.12+` in your host runtime (Django 6.0.2 requires it).
- Set these environment variables in production:
  - `DJANGO_DEBUG=false`
  - `DJANGO_SECRET_KEY=<long-random-secret>`
  - `DJANGO_ALLOWED_HOSTS=<your-domain>,<your-platform-domain>`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-domain>,https://<your-platform-domain>`
  - `DATABASE_URL=<postgres-or-mysql-url>`
  - `AI_SERVICE_URL=<public-url-of-ai-service>`
  - `AI_SERVICE_FALLBACK_LOCAL=true` (recommended if AI microservice may be unavailable)
- If deploying services separately:
  - Deploy `ai/` first and verify `/health`.
  - Point Django `AI_SERVICE_URL` to that live AI URL.
- If you deploy only the Django web service, keep `AI_SERVICE_FALLBACK_LOCAL=true` so resume parsing/matching still works without the Flask AI service.
- Docker build targets:
  - Web app from repo root: uses `Dockerfile` (default).
  - Web app from subfolder: use `web/Dockerfile`.
  - AI service: use `ai/Dockerfile`.

## Tests
```bash
cd ai
pytest

cd web
python manage.py test
```

## Troubleshooting (Windows)
- If a virtualenv install failed, delete and recreate it:
```bash
Remove-Item -Recurse -Force .venv
python -m venv .venv
```
- If you use PostgreSQL locally on Windows, make sure PostgreSQL is installed so `pg_config` is on your PATH.
- Password reset email not arriving:
  - In local debug mode, emails may be written to `web/sent_emails` instead of sent via SMTP.
  - For real Gmail delivery, set:
    - `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
    - `DJANGO_EMAIL_HOST=smtp.gmail.com`
    - `DJANGO_EMAIL_PORT=587`
    - `DJANGO_EMAIL_USE_TLS=true`
    - `DJANGO_EMAIL_HOST_USER=<your-gmail>`
    - `DJANGO_EMAIL_HOST_PASSWORD=<gmail-app-password>`

## Demo Script (Click-by-Click)
1. Start Flask (`ai/`) and Django (`web/`).
2. Visit `/register` and create a user (or login with demo).
3. Upload `sample_data/sample_resume.pdf`.
4. Open the resume detail page and verify extracted skills.
5. Go to Jobs and open a job detail page.
6. Click “Check Match” to see score + missing skills.
7. Click “Analyze Skill Gaps” for targeted suggestions.
8. Save a job to see it under “Saved Jobs”.
9. Open “Recommendations” and generate top jobs for the resume.
10. Login as `admin` to view Admin Dashboard and manage jobs.

## Screenshots Instructions
- Capture the Home page, Resume Detail, Job Detail (match result), Recommendations, and Admin Dashboard.
- Save screenshots in a `/screenshots` folder (create it if needed).
