from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice_code", "table", "status", "payment_method", "total", "created_at", "paid_at")
    readonly_fields = ("invoice_token", "invoice_code")
    list_filter = ("status", "table", "payment_method")
    inlines = [OrderItemInline]
