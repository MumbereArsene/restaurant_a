"""Delete media files (Cloudinary or local disk) no longer referenced.

Used both when an ImageField is replaced by a new upload and when its
record is deleted, so orphan files never pile up in Cloudinary storage.
"""

import logging

logger = logging.getLogger("core.media_cleanup")


def delete_replaced_file(instance, field_name: str) -> None:
    """On save: remove the previously stored file when a new one replaced it.

    The current record is refetched so the old state is compared against the
    new one. If the field was cleared by the caller (form ``clear_image``) the
    file has already been deleted and the previous value stays untouched.
    """
    if not instance.pk:
        return
    try:
        previous = type(instance)._default_manager.get(pk=instance.pk)
    except type(instance).DoesNotExist:
        return
    old = getattr(previous, field_name, None)
    new = getattr(instance, field_name, None)
    old_name = getattr(old, "name", "") or ""
    new_name = getattr(new, "name", "") or ""
    if old_name and new_name and old_name != new_name:
        _delete_file(old)


def delete_file(instance, *field_names: str) -> None:
    """On delete: remove every stored file for the given field names."""
    for field_name in field_names:
        field = getattr(instance, field_name, None)
        _delete_file(field)


def _delete_file(field) -> None:
    if field is None or not getattr(field, "name", ""):
        return
    try:
        field.delete(save=False)
    except Exception:  # noqa: BLE001 — best effort; storage may already be gone
        logger.info("Could not delete orphan file %s", getattr(field, "name", ""), exc_info=True)