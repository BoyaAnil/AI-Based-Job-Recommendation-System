# Deployment

## Option 1: Docker Compose (Recommended for Full Stack)

From repo root:

```powershell
docker compose up --build
```

Expected services:

- Django: `http://localhost:8000`
- Flask: `http://localhost:5000`
- Postgres: `localhost:5432`

## Option 2: Deploy Services Separately

1. Deploy `ai/` Flask service first.
2. Validate AI health endpoint (`/health`).
3. Deploy `web/` Django app.
4. Set `AI_SERVICE_URL` in Django to the deployed AI service URL.

## Option 3: Django-Only Deployment with Local Fallback

If AI service is not deployed separately:

- Keep `AI_SERVICE_FALLBACK_LOCAL=true` in Django config.
- Django will execute local parsing/matching logic when remote AI is unavailable.

## Production Environment Checklist

- `DJANGO_DEBUG=false`
- Set strong `DJANGO_SECRET_KEY`
- Configure `DJANGO_ALLOWED_HOSTS`
- Configure `DJANGO_CSRF_TRUSTED_ORIGINS`
- Use managed DB (`DATABASE_URL`)
- Set stable email configuration
- Provide `AI_SERVICE_URL` if deploying Flask externally
- Configure static/media persistence strategy

## Dockerfiles in Repo

- Root `Dockerfile`: Django web build path from repository root
- `web/Dockerfile`: Django app from subfolder context
- `ai/Dockerfile`: Flask AI service

## Post-Deploy Verification

1. Open web home page.
2. Register/login.
3. Upload sample resume and verify parse output.
4. Run one match and one recommendation flow.
5. Confirm admin dashboard is accessible for admin user.
