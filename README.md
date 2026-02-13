# AI-Powered Resume Analyzer & Job Recommendation System

Full-stack monorepo with Django web app and Flask AI microservice.

## Project Structure
- `web/` Django app (UI, auth, database, dashboards)
- `ai/` Flask AI service (resume parsing, matching, recommendations)
- `sample_data/` seed jobs + sample resume

## Features
- User registration/login and profile
- Upload PDF/DOCX resumes and view extracted data
- Job list/search, job detail, and match scoring
- Recommended jobs for a selected resume
- Save jobs to a personal list
- Admin job CRUD and analytics dashboard
- Offline-friendly NLP (TF-IDF + regex-based skill extraction)

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

## Deployment Notes
- Use Python `3.12+` in your host runtime (Django 6.0.2 requires it).
- Set these environment variables in production:
  - `DJANGO_DEBUG=false`
  - `DJANGO_SECRET_KEY=<long-random-secret>`
  - `DJANGO_ALLOWED_HOSTS=<your-domain>,<your-platform-domain>`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-domain>,https://<your-platform-domain>`
  - `DATABASE_URL=<postgres-or-mysql-url>`
  - `AI_SERVICE_URL=<public-url-of-ai-service>`
- If deploying services separately:
  - Deploy `ai/` first and verify `/health`.
  - Point Django `AI_SERVICE_URL` to that live AI URL.

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
