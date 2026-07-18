"""Bootstrap production essentials (restaurant singleton + optional admin)."""

import os

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from core.models import Restaurant


class Command(BaseCommand):
    help = (
        "Ensure Restaurant singleton exists and optionally create an admin "
        "from ADMIN_USERNAME / ADMIN_PASSWORD env vars (idempotent)."
    )

    def handle(self, *args, **options):
        resto = Restaurant.get_solo()
        self.stdout.write(self.style.SUCCESS(f"Restaurant prêt : {resto.name}"))

        username = os.getenv("ADMIN_USERNAME", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "").strip()
        email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()

        if not username or not password:
            self.stdout.write(
                "Pas de ADMIN_USERNAME/ADMIN_PASSWORD — admin non créé automatiquement."
            )
            return

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": User.Role.ADMIN,
                    "is_staff": True,
                    "is_superuser": True,
                    "first_name": "Admin",
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Admin créé : {username}"))
            else:
                # Keep role elevated if env bootstrap re-run
                changed = False
                if user.role != User.Role.ADMIN:
                    user.role = User.Role.ADMIN
                    changed = True
                if not user.is_staff:
                    user.is_staff = True
                    changed = True
                if not user.is_superuser:
                    user.is_superuser = True
                    changed = True
                if changed:
                    user.save()
                    self.stdout.write(self.style.WARNING(f"Admin existant mis à jour : {username}"))
                else:
                    self.stdout.write(f"Admin déjà présent : {username}")
