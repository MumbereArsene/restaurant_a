"""Role-based access helpers for staff views."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


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


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """CBV mixin: set `allowed_roles` (admin/superuser always pass)."""

    allowed_roles: tuple = ()

    def test_func(self):
        return _has_role(self.request.user, self.allowed_roles)
