from django.urls import path

from . import views

app_name = "cash"

urlpatterns = [
    path("staff/cash/", views.cash_ledger, name="ledger"),
    path("staff/cash/nouveau/", views.cash_entry_create, name="create"),
    path("staff/cash/cloture/", views.cash_close, name="close"),
    path("staff/cash/cloture/<int:pk>/", views.cash_closure_detail, name="closure_detail"),
]
