"""Helpers for the staff action audit trail."""

from .models import AuditLog


def log_action(user, action: str, message: str, *, object_type: str = "", object_id="") -> AuditLog | None:
    """Record a staff action. Failures must never break the main flow."""
    try:
        return AuditLog.objects.create(
            actor=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            object_type=object_type or "",
            object_id=str(object_id) if object_id not in (None, "") else "",
            message=message,
        )
    except Exception:  # noqa: BLE001 — audit must not crash business logic
        return None
