"""Fail-closed production checks. Import-safe for Django tests (DEBUG=True)."""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

DANGEROUS_SECRET_MARKERS = ("django-insecure", "change-me", "dev-only", "insecure")
MIN_SECRET_LENGTH = 32
DEV_SECRET_KEY = "django-insecure-dev-only-key-change-me-in-production"


def is_production_environment(debug: bool, environ: dict | None = None) -> bool:
    env = environ if environ is not None else os.environ
    if env.get("DJANGO_ENV", "").strip().lower() == "production":
        return True
    if env.get("NORTHFLANK") or env.get("NF_PROJECT_ID"):
        return True
    return not debug


def secret_key_is_unsafe(secret_key: str) -> bool:
    key = (secret_key or "").strip()
    if not key or len(key) < MIN_SECRET_LENGTH:
        return True
    lowered = key.lower()
    return any(marker in lowered for marker in DANGEROUS_SECRET_MARKERS)


def validate_production_settings(
    *,
    debug: bool,
    secret_key: str,
    allowed_hosts: list[str] | None,
    environ: dict | None = None,
) -> None:
    """Refuse to boot an unsafe production configuration."""
    env = environ if environ is not None else os.environ
    if not is_production_environment(debug, env):
        return

    if debug:
        raise ImproperlyConfigured(
            "DEBUG must be False in production (set DEBUG=0)."
        )

    if secret_key_is_unsafe(secret_key):
        raise ImproperlyConfigured(
            "SECRET_KEY is missing, too short, or uses an insecure development value."
        )

    hosts = [h for h in (allowed_hosts or []) if str(h).strip()]
    if not hosts or "*" in hosts:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must be set in production and must not include '*'."
        )
