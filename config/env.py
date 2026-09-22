"""
Environment configuration loading.

Rule (PID §11 / ARCHITECTURE.md "Configuration"): no environment-specific
configuration is embedded in source. Required configuration must fail loudly
- never fall back to a silent, potentially-insecure default.
"""
import os

from django.core.exceptions import ImproperlyConfigured


class MissingEnvironmentVariable(ImproperlyConfigured):
    pass


def require_env(name: str) -> str:
    """Return the named environment variable, or raise loudly if unset/blank."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise MissingEnvironmentVariable(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and provide a real value."
        )
    return value


def optional_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value


def require_env_choice(name: str, choices: tuple) -> str:
    value = require_env(name)
    if value not in choices:
        raise MissingEnvironmentVariable(
            f"Environment variable '{name}' must be one of {choices!r}, got {value!r}."
        )
    return value


def require_env_int(name: str) -> int:
    value = require_env(name)
    try:
        return int(value)
    except ValueError as exc:
        raise MissingEnvironmentVariable(
            f"Environment variable '{name}' must be an integer, got {value!r}."
        ) from exc
