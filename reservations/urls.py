from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    path("reservations/", views.reservation_create, name="create"),
    path("staff/reservations/", views.staff_reservations, name="staff_list"),
    path("staff/reservations/nouvelle/", views.staff_reservation_create, name="staff_create"),
    path(
        "staff/reservations/<int:pk>/modifier/",
        views.staff_reservation_update,
        name="staff_update",
    ),
    path(
        "staff/reservations/<int:pk>/supprimer/",
        views.staff_reservation_delete,
        name="staff_delete",
    ),
    path(
        "staff/reservations/<int:pk>/statut/<str:status>/",
        views.staff_reservation_set_status,
        name="staff_set_status",
    ),
]
