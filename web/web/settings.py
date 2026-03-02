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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() == "true"


def _normalize_host(value: str) -> str:
    if "://" in value:
        host = urlparse(value).netloc.strip()
    else:
        host = value.split("/")[0].strip()
    # Django ALLOWED_HOSTS expects hostnames, not host:port.
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


allowed_hosts = [_normalize_host(value) for value in _csv_env("DJANGO_ALLOWED_HOSTS")]
for env_name in (
    "RENDER_EXTERNAL_HOSTNAME",
    "RAILWAY_PUBLIC_DOMAIN",
    "VERCEL_URL",
    "BACK4APP_APP_HOST",
    "BACK4APP_PUBLIC_DOMAIN",
    "BACK4APP_URL",
):
    host = _normalize_host(os.getenv(env_name, ""))
    if host:
        allowed_hosts.append(host)

if not allowed_hosts:
    if DEBUG:
        allowed_hosts = ["localhost", "127.0.0.1"]
    else:
        # Back4App container runtime hostnames are typically <node>.containers.back4app.com.
        allowed_hosts = [".containers.back4app.com"]

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

database_url = os.getenv("DATABASE_URL", "").strip()
if database_url:
    default_db = dj_database_url.parse(database_url, conn_max_age=600)
else:
    default_db = dj_database_url.parse(f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600)

# Keep SQLite path stable even when DATABASE_URL contains a relative path.
if default_db.get("ENGINE") == "django.db.backends.sqlite3":
    db_name = str(default_db.get("NAME", "")).strip()
    if db_name and not Path(db_name).is_absolute():
        default_db["NAME"] = str((BASE_DIR / db_name).resolve())

DATABASES = {"default": default_db}

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
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "").strip()
_smtp_credentials_configured = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)

EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "").strip()
_email_port_raw = os.getenv("DJANGO_EMAIL_PORT", "").strip()
EMAIL_USE_TLS = _env_bool("DJANGO_EMAIL_USE_TLS", False)
EMAIL_USE_SSL = _env_bool("DJANGO_EMAIL_USE_SSL", False)

if _smtp_credentials_configured and not EMAIL_HOST and EMAIL_HOST_USER.lower().endswith("@gmail.com"):
    EMAIL_HOST = "smtp.gmail.com"
    if not _email_port_raw:
        _email_port_raw = "587"
    if os.getenv("DJANGO_EMAIL_USE_TLS") is None and os.getenv("DJANGO_EMAIL_USE_SSL") is None:
        EMAIL_USE_TLS = True
        EMAIL_USE_SSL = False

if not EMAIL_HOST:
    EMAIL_HOST = "localhost"
if not _email_port_raw:
    _email_port_raw = "465" if EMAIL_USE_SSL else "25"
EMAIL_PORT = int(_email_port_raw)

if _email_backend_env:
    EMAIL_BACKEND = _email_backend_env
elif _smtp_credentials_configured:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "noreply@localhost")
EMAIL_FILE_PATH = os.getenv("DJANGO_EMAIL_FILE_PATH", str(BASE_DIR / "sent_emails"))
if EMAIL_BACKEND == "django.core.mail.backends.filebased.EmailBackend":
    Path(EMAIL_FILE_PATH).mkdir(parents=True, exist_ok=True)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:5000")
AI_SERVICE_FALLBACK_LOCAL = os.getenv("AI_SERVICE_FALLBACK_LOCAL", "true").lower() == "true"
RESUME_MAX_FILE_SIZE_MB = int(os.getenv("RESUME_MAX_FILE_SIZE_MB", "2"))
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY", "")
AUTO_DAILY_JOB_REFRESH = _env_bool("AUTO_DAILY_JOB_REFRESH", True)
AUTO_DAILY_JOB_REFRESH_HOURS = int(os.getenv("AUTO_DAILY_JOB_REFRESH_HOURS", "24"))
AUTO_DAILY_JOB_REFRESH_RETRY_MINUTES = int(os.getenv("AUTO_DAILY_JOB_REFRESH_RETRY_MINUTES", "60"))
AUTO_DAILY_JOB_QUERY = os.getenv("AUTO_DAILY_JOB_QUERY", "software developer")
AUTO_DAILY_JOB_LOCATION = os.getenv("AUTO_DAILY_JOB_LOCATION", "India")
AUTO_DAILY_JOB_LIMIT = int(os.getenv("AUTO_DAILY_JOB_LIMIT", "100"))
AUTO_DAILY_JOB_REQUIRE_LOCATION_MATCH = _env_bool("AUTO_DAILY_JOB_REQUIRE_LOCATION_MATCH", True)

csrf_origins = _csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")
for host in ALLOWED_HOSTS:
    if not host or host in ("localhost", "127.0.0.1", "0.0.0.0", "*"):
        continue
    if host.startswith("."):
        csrf_origins.append(f"https://*{host}")
    else:
        csrf_origins.append(f"https://{host}")
CSRF_TRUSTED_ORIGINS = sorted(set(csrf_origins))
