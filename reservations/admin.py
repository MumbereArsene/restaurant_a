from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "date", "time", "guests", "status")
    list_filter = ("status", "date")
