from django.urls import path

from . import views

app_name = "tables"

urlpatterns = [
    path("staff/serveur/", views.serveur_home, name="serveur_home"),
    path("staff/tables/", views.table_list, name="list"),
    path("staff/tables/liberer/", views.table_free_scan, name="free_scan"),
    path("staff/tables/liberer/valider/", views.table_free_by_token, name="free_by_token"),
    path("staff/tables/liberer/<str:token>/", views.table_free_confirm, name="free_confirm"),
    path("staff/tables/<int:pk>/liberer/", views.table_free_by_pk, name="free_by_pk"),
    path("staff/tables/nouvelle/", views.table_create, name="create"),
    path("staff/tables/<int:pk>/modifier/", views.table_update, name="update"),
    path("staff/tables/<int:pk>/supprimer/", views.table_delete, name="delete"),
    path("staff/tables/<int:pk>/qr/", views.table_qr_view, name="qr_view"),
    path("staff/tables/<int:pk>/qr.png", views.table_qr_png, name="qr_png"),
    path("staff/tables/<int:pk>/qr/regenerer/", views.table_regenerate_token, name="qr_regen"),
]
