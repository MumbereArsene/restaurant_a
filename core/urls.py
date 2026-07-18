from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("salle/tables/", views.table_board_partial, name="table_board"),
    path("contact/", views.contact, name="contact"),
    path("mentions-legales/", views.legal_mentions, name="legal"),
    path("politique-utilisation/", views.terms_of_use, name="terms"),
    path("health/", views.healthcheck, name="health"),
    path("staff/", views.dashboard, name="dashboard"),
    path("staff/settings/", views.restaurant_settings, name="settings"),
    path("staff/audit/", views.audit_log, name="audit"),
]
