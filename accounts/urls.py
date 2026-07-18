from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("staff/login/", views.StaffLoginView.as_view(), name="login"),
    path("staff/logout/", views.StaffLogoutView.as_view(), name="logout"),
    path("staff/personnel/", views.personnel_list, name="personnel_list"),
    path("staff/personnel/nouveau/", views.personnel_create, name="personnel_create"),
    path("staff/personnel/<int:pk>/modifier/", views.personnel_update, name="personnel_update"),
    path("staff/personnel/<int:pk>/supprimer/", views.personnel_delete, name="personnel_delete"),
]
