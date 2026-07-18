from django.contrib import admin

from .models import AuditLog, ContactMessage, Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "color_accent")
    fieldsets = (
        (None, {"fields": ("name", "description_fr", "description_en", "logo", "cover_image")}),
        ("Contact", {"fields": ("address", "phone", "email", "opening_hours_fr", "opening_hours_en")}),
        (
            "Palette",
            {
                "fields": (
                    "color_ink",
                    "color_paper",
                    "color_surface",
                    "color_accent",
                    "color_accent_dark",
                )
            },
        ),
    )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "subject", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "phone", "subject", "message")
    readonly_fields = ("created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_id", "message")
    list_filter = ("action", "object_type")
    search_fields = ("message", "action", "object_id")
    readonly_fields = ("created_at", "actor", "action", "object_type", "object_id", "message")
    date_hierarchy = "created_at"
