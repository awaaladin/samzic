"""
Django settings for Samzic Foods Empire.

Local development uses SQLite. Deployments on Vercel use PostgreSQL, read from
DATABASE_URL. See the Database section below and .env.example.
"""

from pathlib import Path
import secrets

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_SECRET_KEY = secrets.token_urlsafe(64)

env = environ.Env(
    DJANGO_DEBUG=(bool, True),
    DJANGO_SECRET_KEY=(str, DEFAULT_SECRET_KEY),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "[::1]"]),
)
environ.Env.read_env(BASE_DIR / ".env")

# Vercel sets these on every deployment and neither exists on a laptop, so they
# are the signal for "am I deployed?". Drives DEBUG, host checking, and the
# SQLite/PostgreSQL choice further down.
ON_VERCEL = bool(env("VERCEL", default="")) or bool(env("VERCEL_ENV", default=""))

# SECURITY WARNING: set DJANGO_SECRET_KEY in .env before deploying.
SECRET_KEY = env("DJANGO_SECRET_KEY")

# Forced off when deployed, whatever the environment says: a stray
# DJANGO_DEBUG=True in the Vercel dashboard would otherwise publish tracebacks
# and a full settings dump to anyone who triggers an error.
DEBUG = False if ON_VERCEL else env("DJANGO_DEBUG")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = []

if ON_VERCEL:
    # VERCEL_URL is the per-deployment host, the production alias is separate,
    # and both arrive as bare hostnames with no scheme.
    for _host in (
        env("VERCEL_URL", default=""),
        env("VERCEL_PROJECT_PRODUCTION_URL", default=""),
    ):
        # The two are the same string on a production deployment, so guard
        # against listing the host twice.
        if _host and _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)
            CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

    # TLS terminates at Vercel's edge and the request reaches Django over plain
    # http, so without this Django reads every request as insecure.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    # Branded admin. Replaces "django.contrib.admin" so admin.site is our
    # SamzicAdminSite; see config/admin.py. All default behaviour is retained.
    "config.apps.SamzicAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

LOCAL_APPS = [
    "accounts",
    "menu",
    "cart",
    "orders",
    "pages",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Last on purpose: it must wrap the view closely enough that MessageMiddleware
    # still runs afterwards, or flash messages read during the re-render would be
    # marked consumed without ever being written back.
    "config.middleware.BrandedErrorPagesMiddleware",
]

# With DEBUG on, Django answers a missing URL with its own debug page and the
# custom handlers below never fire — so templates/404.html is invisible in
# development. This makes 400/403/404 render the site's pages locally too.
# Set to False in .env to get Django's "Using the URLconf defined in..." page
# back while debugging a routing problem. No effect when DEBUG is False: the
# real handlers are already serving these templates.
BRANDED_ERROR_PAGES = env.bool("DJANGO_BRANDED_ERROR_PAGES", default=True)

ROOT_URLCONF = "config.urls"

# Replaces Django's unstyled CSRF failure page. The 400/403/404/500 handlers
# live in config/urls.py; this one is a setting rather than a handler.
CSRF_FAILURE_VIEW = "config.views.csrf_failure"

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
                "django.template.context_processors.media",
                # Exposes cart totals to every template (navbar badge).
                "cart.context_processors.cart",
                # Exposes SITE_NAME and friends.
                "config.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
# ASGI_APPLICATION is deliberately not set. Every view here is synchronous, and
# Vercel picks the ASGI entrypoint over the WSGI one whenever both are defined —
# which would not match the entrypoint vercel.json configures. config/asgi.py is
# still present for `daphne`/`uvicorn` if it is ever wanted locally.

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# SQLite locally, PostgreSQL on Vercel.
#
# The switch is ON_VERCEL (set near the top from Vercel's own env vars), not the
# presence of DATABASE_URL: that lives in .env so one file serves both, and
# keying off it would silently drag production Postgres into local development.
#
# To exercise Postgres locally (a migration, a data check), set USE_POSTGRES=True
# in .env for the length of that task. Requires psycopg — see requirements.txt.
USE_POSTGRES = ON_VERCEL or env.bool("USE_POSTGRES", default=False)

if USE_POSTGRES:
    database_url = env("DATABASE_URL", default="")
    if not database_url:
        raise ImproperlyConfigured(
            "DATABASE_URL must be set when running on Vercel. Add it under "
            "Project Settings > Environment Variables."
        )
    DATABASES = {"default": env.db_url_config(database_url)}
    _db = DATABASES["default"]

    # Managed Postgres (Supabase, Neon, RDS) requires TLS. setdefault so an
    # explicit ?sslmode= in the URL wins.
    _db.setdefault("OPTIONS", {}).setdefault("sslmode", "require")

    if ON_VERCEL:
        # Each serverless invocation is its own short-lived process, so a
        # persistent connection cannot be reused and only holds a slot open
        # against Postgres' connection limit. Close on completion instead.
        _db["CONN_MAX_AGE"] = 0
    else:
        _db["CONN_MAX_AGE"] = 60

    if ":6543" in database_url or "pooler" in database_url:
        # Supabase's transaction-mode pooler multiplexes one backend across many
        # clients, so anything tied to a session breaks: psycopg's prepared
        # statements collide, and server-side cursors outlive their connection.
        _db["DISABLE_SERVER_SIDE_CURSORS"] = True
        _db["OPTIONS"]["prepare_threshold"] = None
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "menu:home"

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Vercel runs collectstatic during the build and serves STATIC_ROOT from its CDN,
# so no extra storage backend or middleware is needed. Locally, runserver serves
# from STATICFILES_DIRS and this directory stays empty.
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
# NOTE: Vercel's filesystem is read-only apart from /tmp, and every deployment
# starts fresh — so images uploaded through the admin do NOT survive there.
# Moving MEDIA to object storage (S3, Supabase Storage) is the fix; until then
# food images should be committed under static/ rather than uploaded.
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Messages — map Django levels to Tailwind classes used in base.html
# ---------------------------------------------------------------------------
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}

# ---------------------------------------------------------------------------
# Project-specific
# ---------------------------------------------------------------------------
SITE_NAME = "Samzic Foods Empire"
SITE_TAGLINE = "Hot, homemade Nigerian meals delivered fast."
SITE_PHONE = "+234 800 000 0000"
DELIVERY_FEE = "500.00"  # Decimal-safe string; parsed in orders.services.
FREE_DELIVERY_THRESHOLD = "20000.00"
MENU_PAGE_SIZE = 9

# Cart session key.
CART_SESSION_ID = "cart"

# ---------------------------------------------------------------------------
# Security — hardened automatically when DEBUG is off
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"
    # Extend rather than replace: the Vercel block near the top has already put
    # the deployment's own hostnames in here, and assigning would drop them.
    CSRF_TRUSTED_ORIGINS += [
        origin
        for origin in env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
        if origin not in CSRF_TRUSTED_ORIGINS
    ]
