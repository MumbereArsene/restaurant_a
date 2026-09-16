"""Role-based access helpers for staff views."""

from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


def _has_role(user, roles) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == "admin":
        return True
    return user.role in roles


def role_required(*roles):
    """Decorator: restrict a view to given roles (admin always allowed)."""

    def check(user):
        return _has_role(user, roles)

    def wrapper(view_func):
        return login_required(user_passes_test(check)(view_func))

    return wrapper


def capability_required(attr: str):
    """Decorator: require a User capability property (e.g. can_encaisser)."""

    def check(user):
        if not user.is_authenticated:
            return False
        return bool(getattr(user, attr, False))

    def wrapper(view_func):
        return login_required(user_passes_test(check)(view_func))

    return wrapper


# Role groups
admin_required = role_required()  # admin / superuser only
manager_or_admin = role_required("manager")
cash_access = role_required("caissier", "manager")
serveur_floor = role_required("serveur", "manager")  # tables / reservations / free
# Backward-compatible alias
serveur_or_admin = serveur_floor
staff_any = role_required("serveur", "cuisine", "caissier", "manager")

# Capability shortcuts
encaisser_required = capability_required("can_encaisser")
discount_approve_required = capability_required("can_approve_discount")
personnel_required = capability_required("can_manage_personnel")
menu_required = capability_required("can_manage_menu")
audit_required = capability_required("can_view_audit")


def analytics_required(view_func):
    """Admin/manager only. Logged-in staff without access get 403."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not getattr(request.user, "can_view_analytics", False):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """CBV mixin: set `allowed_roles` (admin/superuser always pass)."""

    allowed_roles: tuple = ()

    def test_func(self):
        return _has_role(self.request.user, self.allowed_roles)


def can_manage_staff_user(actor, target) -> bool:
    """Server-side hierarchy: who may create/edit/delete a given staff account.

    - Admin: any non-client staff user.
    - Manager: caissier, serveur, cuisine only (never admin, manager, or client).
    """
    if actor is None or not getattr(actor, "is_authenticated", False):
        return False
    if not getattr(actor, "can_manage_personnel", False):
        return False
    if target is None:
        return True
    if getattr(target, "is_client_role", False):
        return False
    if actor.is_admin_role:
        return True
    if actor.is_manager_role:
        return target.role in ("caissier", "serveur", "cuisine")
    return False
