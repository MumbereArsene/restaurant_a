from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("staff/login/", views.StaffLoginView.as_view(), name="login"),
    path("staff/logout/", views.StaffLogoutView.as_view(), name="logout"),
    path("compte/connexion/", views.ClientLoginView.as_view(), name="client_login"),
    path("compte/deconnexion/", views.ClientLogoutView.as_view(), name="client_logout"),
    path("compte/inscription/", views.client_register, name="client_register"),
    path("staff/personnel/", views.personnel_list, name="personnel_list"),
    path("staff/personnel/nouveau/", views.personnel_create, name="personnel_create"),
    path("staff/personnel/<int:pk>/modifier/", views.personnel_update, name="personnel_update"),
    path("staff/personnel/<int:pk>/supprimer/", views.personnel_delete, name="personnel_delete"),
    # Password reset (Django signed tokens + expiry)
    path(
        "staff/mot-de-passe/",
        views.StaffPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "staff/mot-de-passe/envoye/",
        views.StaffPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "compte/mot-de-passe/",
        views.ClientPasswordResetView.as_view(),
        name="client_password_reset",
    ),
    path(
        "compte/mot-de-passe/envoye/",
        views.ClientPasswordResetDoneView.as_view(),
        name="client_password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/termine/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
