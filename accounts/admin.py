from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied

from .models import User
from .permissions import can_manage_staff_user


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Rôle", {"fields": ("role", "phone")}),)
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "role" in form.base_fields:
            allowed = User.assignable_staff_roles(request.user)
            form.base_fields["role"].choices = [
                c for c in User.Role.choices if c[0] in allowed
            ]
        return form

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is None:
            return True
        if obj.role == User.Role.CLIENT:
            return request.user.is_admin_role
        return can_manage_staff_user(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if obj is None:
            return True
        if obj.is_protected_last_admin():
            return False
        return can_manage_staff_user(request.user, obj)

    def save_model(self, request, obj, form, change):
        allowed = User.assignable_staff_roles(request.user)
        if obj.role not in allowed and obj.role != User.Role.CLIENT:
            raise PermissionDenied
        if change:
            previous = User.objects.filter(pk=obj.pk).first()
            if previous and previous.is_protected_last_admin():
                if not obj.is_active:
                    raise PermissionDenied
                if obj.role != User.Role.ADMIN and not obj.is_superuser:
                    raise PermissionDenied
        super().save_model(request, obj, form, change)
