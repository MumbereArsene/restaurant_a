from django.contrib import admin

from .models import Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "public_code", "capacity", "status")
    readonly_fields = ("public_code", "qr_token")
    list_filter = ("status",)
