"""
Django settings for the Infosecurs Beta.

Configuration is externalised via environment variables (PID.md §6/§9,
docs/architecture/ARCHITECTURE.md "Configuration"). No secrets, hosts or
environment-specific values are hard-coded here. Required configuration
raises loudly instead of silently defaulting - see config/env.py.
"""
from pathlib import Path

from config.env import optional_env, require_env, require_env_choice, require_env_int

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment mode
# ---------------------------------------------------------------------------
# DJANGO_ENV is required and explicit - there is no silent default. This
# doubles as the source of DEBUG, satisfying "debug/environment mode" as
# externalised configuration (PID.md §11) without a raw boolean default.
DJANGO_ENV = require_env_choice("DJANGO_ENV", ("development", "test", "production"))
DEBUG = DJANGO_ENV == "development"

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = require_env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = [
    host.strip()
    for host in require_env("DJANGO_ALLOWED_HOSTS").split(",")
    if host.strip()
]

_csrf_origins = optional_env("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.microsoft",
    "core",
    "organisations",
    "security_baseline",
    "key_assets",
    "ai_platform",
    "risk_register",
    "evidence",
    "remediation",
    "activity",
    "security_state",
    "governance",
    "workplace",
    "identity",
    "policy",
    "questionnaire",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

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
                "core.context_processors.product",
                "core.context_processors.active_nav",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": require_env("POSTGRES_DB"),
        "USER": require_env("POSTGRES_USER"),
        "PASSWORD": require_env("POSTGRES_PASSWORD"),
        "HOST": require_env("POSTGRES_HOST"),
        "PORT": require_env_int("POSTGRES_PORT"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth / sessions
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "organisations:list"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# Federated sign-in (M004 - ADR-0002 "Authentication", identity app)
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

SOCIALACCOUNT_ADAPTER = "identity.adapters.CustomSocialAccountAdapter"

ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_PREVENT_ENUMERATION = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_LOGIN_ON_GET = True

# Google's scope deliberately excludes "openid" - with it, Google returns a
# signed id_token that allauth JWT-decodes expecting a non-blank `aud`
# (=client_id) claim, which can never pass with a blank client_id (the
# normal CI/dev state per PID §28). Dropping "openid" makes Google use the
# same plain REST userinfo-fetch shape Microsoft's Graph-based provider
# already uses - see identity/testing.py's module docstring for the full
# reasoning and how the fake-provider test seam mirrors this exact shape.
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APPS": [
            {
                "client_id": optional_env("GOOGLE_OAUTH_CLIENT_ID", ""),
                "secret": optional_env("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            }
        ],
    },
    "microsoft": {
        "SCOPE": ["User.Read"],
        "APPS": [
            {
                "client_id": optional_env("MICROSOFT_OAUTH_CLIENT_ID", ""),
                "secret": optional_env("MICROSOFT_OAUTH_CLIENT_SECRET", ""),
            }
        ],
    },
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Django's own forms need the CSRF cookie readable for the token
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Secure cookies/transport for anything that isn't local development.
if DJANGO_ENV == "production":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    # M006 PID §12 finding, documented not fixed here (PID §25 defers real
    # deployment/proxy topology decisions to a later production-readiness
    # gate; this project is not yet authorised to choose one):
    #
    # SECURE_SSL_REDIRECT=True makes Django redirect any request it thinks
    # is plain HTTP to an https:// URL. Django decides "is this HTTPS"
    # via request.is_secure(), which - with no SECURE_PROXY_SSL_HEADER set
    # (there is none, anywhere in this codebase, today) - looks ONLY at the
    # literal connection scheme Django's own process received. In the
    # extremely common real deployment shape where a reverse proxy
    # terminates TLS and forwards plain HTTP internally to this app, every
    # request arrives here as plain HTTP regardless of what the end client
    # used - so Django would redirect it, the client would come back on
    # HTTPS, the proxy would again forward plain HTTP internally, and
    # Django would redirect again: an infinite redirect loop, not a
    # one-off misconfiguration. This was reproduced live (not just reasoned
    # about) during the M006 Round 4 dispatch by terminating TLS with a
    # throwaway self-signed-cert proxy in front of a disposable
    # DJANGO_ENV=production stack and forwarding plaintext to Django
    # underneath, with no SECURE_PROXY_SSL_HEADER configured - see
    # docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md for the exact
    # reproduction and captured output.
    #
    # The fix, when this project is actually authorised to choose a real
    # deployment/proxy topology, is Django's own SECURE_PROXY_SSL_HEADER
    # setting (e.g. ("HTTP_X_FORWARDED_PROTO", "https")) - but ONLY once
    # it is verified that every request path to this app is guaranteed to
    # go through a proxy that (a) always sets that header itself, and
    # (b) is never reachable by a client that could set/spoof it directly,
    # since a wrongly-trusted header is a request-forgery vector the other
    # way. Choosing and verifying that is explicitly out of scope for
    # M006 (PID §25) - not decided here.
    #
    # `manage.py check --deploy` separately flags security.W004
    # (SECURE_HSTS_SECONDS unset) under this same DJANGO_ENV=production
    # configuration. HSTS is the same class of decision: safe only once the
    # real deployment topology guarantees the entire site (including every
    # subdomain, if INCLUDE_SUBDOMAINS is ever added) is HTTPS-only, and a
    # long max-age is not easily reversible if that assumption turns out to
    # be wrong. Documented here for the same reason, not enabled.

# ---------------------------------------------------------------------------
# Internationalisation / time
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Logging - never log sensitive values (PID.md §9.8)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
