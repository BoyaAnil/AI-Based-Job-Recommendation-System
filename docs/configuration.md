# Configuration

## Environment Files

- `web/.env` for Django settings
- `ai/.env` for Flask settings
- Root `.env.example` shows both service sections in one reference file

## Django (`web/.env`)

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes (prod) | `unsafe-dev-key` | Django secret key |
| `DJANGO_DEBUG` | No | `true` | Enable debug mode |
| `DJANGO_ALLOWED_HOSTS` | Yes (prod) | `localhost,127.0.0.1` in debug | Comma-separated allowed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Yes (prod) | Auto-derived + env | Trusted origins for CSRF |
| `DATABASE_URL` | No | `sqlite:///db.sqlite3` | DB URL (`sqlite`, `postgres`, `mysql`) |
| `AI_SERVICE_URL` | No | `http://localhost:5000` | Flask base URL |
| `AI_SERVICE_FALLBACK_LOCAL` | No | `true` | Use local AI fallback in Django on AI failures |
| `RESUME_MAX_FILE_SIZE_MB` | No | `2` | Max resume upload size |
| `JSEARCH_API_KEY` | Optional | empty | RapidAPI key for JSearch source |
| `DJANGO_EMAIL_BACKEND` | No | auto | Email backend override |
| `DJANGO_DEFAULT_FROM_EMAIL` | No | `noreply@localhost` | Default from address |
| `DJANGO_EMAIL_HOST` | No | `localhost` | SMTP host |
| `DJANGO_EMAIL_PORT` | No | `25` | SMTP port |
| `DJANGO_EMAIL_HOST_USER` | Optional | empty | SMTP username |
| `DJANGO_EMAIL_HOST_PASSWORD` | Optional | empty | SMTP password |
| `DJANGO_EMAIL_USE_TLS` | No | `false` | Enable TLS |
| `DJANGO_EMAIL_USE_SSL` | No | `false` | Enable SSL |
| `DJANGO_EMAIL_FILE_PATH` | No | `web/sent_emails` | File backend output path |

## Flask (`ai/.env`)

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FLASK_DEBUG` | No | `1` (example) | Flask debug mode |
| `AI_LOG_LEVEL` | No | `INFO` (example) | AI service log level |
| `PORT` | No | `5000` | Port used by `app.py` |

## Production Baseline

- Set `DJANGO_DEBUG=false`.
- Set a strong `DJANGO_SECRET_KEY`.
- Configure `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` for your domain.
- Prefer Postgres/MySQL over SQLite in production.
- Use real SMTP or transactional email provider.
- Keep secrets out of git; use platform secret manager.
