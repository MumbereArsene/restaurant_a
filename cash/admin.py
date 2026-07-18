from django.contrib import admin

from .models import CashClosure, CashEntry


@admin.register(CashEntry)
class CashEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "type", "amount", "reason", "order", "created_by")
    list_filter = ("type",)
    date_hierarchy = "created_at"


@admin.register(CashClosure)
class CashClosureAdmin(admin.ModelAdmin):
    list_display = (
        "closed_at",
        "total_in",
        "total_out",
        "expected_amount",
        "counted_amount",
        "difference",
        "closed_by",
    )
    date_hierarchy = "closed_at"
