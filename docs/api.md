# API Reference

This project exposes:

1. Flask AI service endpoints (`ai/app.py`)
2. Django JSON endpoints used by the web UI (`web/core/views.py`)

## Flask AI Service

Base URL (local): `http://127.0.0.1:5000`

### `GET /health`

Response `200`:

```json
{"status":"ok"}
```

### `POST /parse_resume`

Request:

```json
{
  "file_path": "C:/path/to/resume.pdf",
  "file_type": "pdf"
}
```

Success `200`:

```json
{
  "raw_text": "...",
  "name": "...",
  "email": "...",
  "phone": "...",
  "skills": ["python", "sql"],
  "education": [],
  "experience": [],
  "projects": []
}
```

Errors:

- `400` if `file_path`/`file_type` missing
- `400` for unsupported file type or parse failure

### `POST /match`

Request:

```json
{
  "resume_text": "...",
  "job": {
    "title": "...",
    "description": "...",
    "required_skills": ["python", "django"]
  }
}
```

Success `200`:

```json
{
  "score": 0,
  "matched_skills": [],
  "missing_skills": [],
  "summary": "...",
  "improvement_tips": []
}
```

Errors:

- `400` if `resume_text` or `job` is missing

### `POST /recommend_jobs`

Request:

```json
{
  "resume_text": "...",
  "jobs": [
    {
      "id": 1,
      "title": "...",
      "description": "...",
      "required_skills": ["python"]
    }
  ],
  "top_n": 10
}
```

Success `200`:

```json
{
  "recommendations": [
    {"job_id": 1, "score": 85, "reason": "..."}
  ]
}
```

Errors:

- `400` if `resume_text` or `jobs` is missing

### `POST /skill_gap`

Request:

```json
{
  "resume_text": "...",
  "job": {
    "title": "...",
    "description": "...",
    "required_skills": ["python", "sql"]
  }
}
```

Success `200`:

```json
{
  "matched_skills": [],
  "missing_skills": [],
  "suggestions": []
}
```

Errors:

- `400` if `resume_text` or `job` is missing

## Django JSON Endpoints

Base URL (local): `http://127.0.0.1:8000`

### `POST /jobs/<job_id>/match/`

- Auth required
- Accepts form data or JSON with `resume_id`
- Returns match payload plus persisted `match_id` and `match_url`
- Returns `502` if AI service call fails and fallback is unavailable

### `POST /jobs/<job_id>/skill-gap/`

- Auth required
- Accepts form data or JSON with `resume_id`
- Returns skill gap analysis JSON

### `POST /jobs/<job_id>/save/`

- Auth required
- Toggles saved-job state
- Returns:

```json
{"saved": true}
```

or

```json
{"saved": false}
```

### `GET /resumes/<resume_id>/download/`

- Auth required
- Downloads extracted resume JSON as attachment
