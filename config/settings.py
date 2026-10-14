"""Single-origin Django configuration with explicit production safeguards."""

import os
import re
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_DEBUG=false")
    secret_path = BASE_DIR / ".local-secret"
    if not secret_path.exists():
        try:
            with secret_path.open("x", encoding="utf-8") as secret_file:
                secret_file.write(secrets.token_urlsafe(64))
        except FileExistsError:
            pass
    SECRET_KEY = secret_path.read_text(encoding="utf-8").strip()
ALLOWED_HOSTS = list(
    dict.fromkeys(
        host.strip()
        for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(
            ","
        )
        if host.strip()
    )
)
# Render supplies its public hostname; this is a hostname, never a URL or '*'.
# Custom domains remain explicit entries in DJANGO_ALLOWED_HOSTS.
# https://render.com/docs/environment-variables#render_external_hostname
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
if RENDER_EXTERNAL_HOSTNAME:
    if not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com", RENDER_EXTERNAL_HOSTNAME
    ):
        raise ImproperlyConfigured(
            "RENDER_EXTERNAL_HOSTNAME must be a valid onrender.com hostname."
        )
    if RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
RENDER_TLS = os.environ.get("RENDER", "").lower() == "true" and bool(RENDER_EXTERNAL_HOSTNAME)
# Only Render's private application listener sits behind the managed HTTPS edge.
# Local/Docker requests never gain HTTPS trust from caller-supplied headers.
# Waitress must also preserve the trusted scheme (see config.serve).
# https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if RENDER_TLS else None
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "ledger",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
# DRF's standalone API explorer uses the installed package's Django templates.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get(
            "SQLITE_PATH", os.environ.get("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3"))
        ),
        "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"},
    }
}
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", str(not DEBUG)).lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_TRUSTED_ORIGINS = [
    v for v in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if v
]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = not DEBUG and os.environ.get("DJANGO_HTTPS", "true").lower() == "true"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "ledger.errors.exception_handler",
    "DEFAULT_PARSER_CLASSES": ["ledger.serializers.ExactJSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Splitly Expense Sharing API",
    "DESCRIPTION": "Anonymous workspace and group capabilities, exact INR allocations, explained balances, and recorded settlements. Amounts are decimal rupees; storage and calculations use integer paise.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "POSTPROCESSING_HOOKS": ["drf_spectacular.hooks.postprocess_schema_enums"],
}
SPECTACULAR_SETTINGS.update(
    {
        "PREPROCESSING_HOOKS": ["ledger.schema.normalize_paths"],
        "POSTPROCESSING_HOOKS": [
            "drf_spectacular.hooks.postprocess_schema_enums",
            "ledger.schema.normalize_ids",
        ],
        "ENUM_NAME_OVERRIDES": {
            "ScopeTypeEnum": ["workspace", "group"],
            "RecordTypeEnum": ["expense", "settlement"],
        },
    }
)
