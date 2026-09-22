"""
Root conftest. Provides safe, non-secret defaults for required environment
variables so the test suite can run without a hand-authored .env - real
environments (CI, docker-compose) set these for real and take precedence
because we only use setdefault().
"""
import os

os.environ.setdefault("DJANGO_ENV", "test")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production-use")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

os.environ.setdefault("POSTGRES_DB", "infosecurs_test")
os.environ.setdefault("POSTGRES_USER", "infosecurs")
os.environ.setdefault("POSTGRES_PASSWORD", "test-only-password-not-for-production")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")

os.environ.setdefault("CUSTOMER_ZERO_USERNAME", "customerzero")
os.environ.setdefault("CUSTOMER_ZERO_EMAIL", "customerzero@example.test")
os.environ.setdefault("CUSTOMER_ZERO_PASSWORD", "test-only-password-not-for-production")
os.environ.setdefault("CUSTOMER_ZERO_ORGANISATION_NAME", "Infosecurs Limited")
