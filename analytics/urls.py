from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("staff/analytics/", views.dashboard, name="dashboard"),
    path("staff/analytics/export.xlsx", views.export_xlsx, name="export_xlsx"),
    path("staff/analytics/export.pdf", views.export_pdf, name="export_pdf"),
]
