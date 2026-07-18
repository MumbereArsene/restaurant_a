from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Staff user with a single role driving back-office permissions."""

    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrateur")
        MANAGER = "manager", _("Manager")
        CAISSIER = "caissier", _("Caissier")
        SERVEUR = "serveur", _("Serveur")
        CUISINE = "cuisine", _("Cuisine")

    role = models.CharField(
        _("rôle"), max_length=20, choices=Role.choices, default=Role.SERVEUR
    )
    phone = models.CharField(_("téléphone"), max_length=30, blank=True)

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_manager_role(self) -> bool:
        return self.role == self.Role.MANAGER

    @property
    def is_caissier_role(self) -> bool:
        return self.role == self.Role.CAISSIER

    @property
    def is_serveur_role(self) -> bool:
        return self.role == self.Role.SERVEUR

    @property
    def is_cuisine_role(self) -> bool:
        return self.role == self.Role.CUISINE

    # ----- Capability helpers (templates + views) -----

    @property
    def can_encaisser(self) -> bool:
        """Take cash payments for orders."""
        return self.is_admin_role or self.role in (
            self.Role.MANAGER,
            self.Role.CAISSIER,
            self.Role.SERVEUR,
        )

    @property
    def can_access_cash(self) -> bool:
        """Cash ledger, manual entries, closures."""
        return self.is_admin_role or self.role in (self.Role.MANAGER, self.Role.CAISSIER)

    @property
    def can_manage_personnel(self) -> bool:
        return self.is_admin_role or self.is_manager_role

    @property
    def can_approve_discount(self) -> bool:
        return self.is_admin_role or self.is_manager_role

    @property
    def can_manage_menu(self) -> bool:
        return self.is_admin_role or self.is_manager_role

    @property
    def can_free_tables(self) -> bool:
        return self.is_admin_role or self.role in (self.Role.MANAGER, self.Role.SERVEUR)

    @property
    def can_manage_reservations(self) -> bool:
        return self.is_admin_role or self.role in (self.Role.MANAGER, self.Role.SERVEUR)

    @property
    def can_view_audit(self) -> bool:
        return self.is_admin_role or self.is_manager_role

    @property
    def can_edit_settings(self) -> bool:
        return self.is_admin_role

    @property
    def can_view_dashboard(self) -> bool:
        """Full KPI dashboard (not redirected elsewhere)."""
        return self.is_admin_role or self.is_manager_role

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
