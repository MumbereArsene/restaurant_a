from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.security import (
    DEV_SECRET_KEY,
    validate_production_settings,
)


class ProductionSettingsTests(SimpleTestCase):
    def test_dev_debug_allows_insecure_secret(self):
        validate_production_settings(
            debug=True,
            secret_key=DEV_SECRET_KEY,
            allowed_hosts=["localhost"],
            environ={},
        )

    def test_debug_false_rejects_missing_secret(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_settings(
                debug=False,
                secret_key="",
                allowed_hosts=["example.com"],
                environ={},
            )

    def test_debug_false_rejects_insecure_secret(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_settings(
                debug=False,
                secret_key=DEV_SECRET_KEY,
                allowed_hosts=["example.com"],
                environ={},
            )

    def test_debug_false_rejects_short_secret(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_settings(
                debug=False,
                secret_key="short-but-not-marked-insecure",
                allowed_hosts=["example.com"],
                environ={},
            )

    def test_northflank_rejects_debug_true(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_settings(
                debug=True,
                secret_key="a" * 50,
                allowed_hosts=["example.com"],
                environ={"NORTHFLANK": "1"},
            )

    def test_django_env_production_rejects_debug(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_settings(
                debug=True,
                secret_key="a" * 50,
                allowed_hosts=["example.com"],
                environ={"DJANGO_ENV": "production"},
            )

    def test_production_rejects_wildcard_hosts(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_settings(
                debug=False,
                secret_key="a" * 50,
                allowed_hosts=["*"],
                environ={},
            )

    def test_production_accepts_safe_config(self):
        validate_production_settings(
            debug=False,
            secret_key="a" * 50,
            allowed_hosts=["restaurant.example.com"],
            environ={"DJANGO_ENV": "production"},
        )
