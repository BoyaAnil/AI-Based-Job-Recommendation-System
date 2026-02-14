from pathlib import Path
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"


def _csv_env(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def _normalize_host(value: str) -> str:
    if "://" in value:
        return urlparse(value).netloc.strip()
    return value.split("/")[0].strip()


allowed_hosts = [_normalize_host(value) for value in _csv_env("DJANGO_ALLOWED_HOSTS")]
for env_name in ("RENDER_EXTERNAL_HOSTNAME", "RAILWAY_PUBLIC_DOMAIN", "VERCEL_URL"):
    host = _normalize_host(os.getenv(env_name, ""))
    if host:
        allowed_hosts.append(host)

if not allowed_hosts:
    allowed_hosts = ["localhost", "127.0.0.1"] if DEBUG else []

ALLOWED_HOSTS = sorted(set(allowed_hosts))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "web.wsgi.application"
ASGI_APPLICATION = "web.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "profile"
LOGOUT_REDIRECT_URL = "home"

_email_backend_env = os.getenv("DJANGO_EMAIL_BACKEND", "").strip()
if _email_backend_env:
    EMAIL_BACKEND = _email_backend_env
elif os.getenv("DJANGO_EMAIL_HOST_USER", "").strip() and os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "").strip():
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "noreply@localhost")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "false").lower() == "true"
EMAIL_USE_SSL = os.getenv("DJANGO_EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_FILE_PATH = os.getenv("DJANGO_EMAIL_FILE_PATH", str(BASE_DIR / "sent_emails"))
if EMAIL_BACKEND == "django.core.mail.backends.filebased.EmailBackend":
    Path(EMAIL_FILE_PATH).mkdir(parents=True, exist_ok=True)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:5000")
AI_SERVICE_FALLBACK_LOCAL = os.getenv("AI_SERVICE_FALLBACK_LOCAL", "true").lower() == "true"
RESUME_MAX_FILE_SIZE_MB = int(os.getenv("RESUME_MAX_FILE_SIZE_MB", "2"))
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY", "")

csrf_origins = _csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")
for host in ALLOWED_HOSTS:
    if host and host not in ("localhost", "127.0.0.1", "0.0.0.0"):
        csrf_origins.append(f"https://{host}")
CSRF_TRUSTED_ORIGINS = sorted(set(csrf_origins))
