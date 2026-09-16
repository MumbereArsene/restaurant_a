from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Staff user with a single role driving back-office permissions."""

    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrateur")
        MANAGER = "manager", _("Manager")
        CAISSIER = "caissier", _("Caissier")
        SERVEUR = "serveur", _("Serveur")
        CUISINE = "cuisine", _("Cuisine")
        CLIENT = "client", _("Client")

    # Manager may only assign floor / cash / kitchen roles — never admin or manager.
    MANAGER_ASSIGNABLE_ROLES = (Role.CAISSIER, Role.SERVEUR, Role.CUISINE)
    ADMIN_ASSIGNABLE_ROLES = (
        Role.ADMIN,
        Role.MANAGER,
        Role.CAISSIER,
        Role.SERVEUR,
        Role.CUISINE,
    )

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

    @property
    def is_client_role(self) -> bool:
        return self.role == self.Role.CLIENT

    @property
    def is_staff_member(self) -> bool:
        return self.is_authenticated and not self.is_client_role

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

    @property
    def can_view_analytics(self) -> bool:
        """Financial analytics (admin / manager only)."""
        return self.is_admin_role or self.is_manager_role

    @classmethod
    def assignable_staff_roles(cls, actor) -> tuple[str, ...]:
        """Roles `actor` is allowed to assign when creating/updating staff."""
        if actor is None or not getattr(actor, "is_authenticated", False):
            return ()
        if actor.is_admin_role:
            return cls.ADMIN_ASSIGNABLE_ROLES
        if actor.is_manager_role:
            return cls.MANAGER_ASSIGNABLE_ROLES
        return ()

    @classmethod
    def active_admins(cls, exclude_pk=None):
        qs = cls.objects.filter(is_active=True).filter(
            Q(role=cls.Role.ADMIN) | Q(is_superuser=True)
        )
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs

    def is_protected_last_admin(self) -> bool:
        """True if deactivating, deleting, or demoting this user would leave zero admins."""
        if not self.pk or not self.is_active:
            return False
        if not (self.role == self.Role.ADMIN or self.is_superuser):
            return False
        return not self.__class__.active_admins(exclude_pk=self.pk).exists()

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
