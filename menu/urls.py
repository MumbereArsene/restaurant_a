from django.urls import path

from . import views

app_name = "menu"

urlpatterns = [
    path("menu/", views.public_menu, name="public"),
    path("menu/plat/<int:pk>/", views.dish_detail, name="dish_detail"),
    path("staff/menu/", views.staff_menu, name="staff"),
    path("staff/menu/categories/nouvelle/", views.category_create, name="category_create"),
    path("staff/menu/categories/<int:pk>/modifier/", views.category_update, name="category_update"),
    path("staff/menu/categories/<int:pk>/supprimer/", views.category_delete, name="category_delete"),
    path("staff/menu/plats/nouveau/", views.dish_create, name="dish_create"),
    path("staff/menu/plats/<int:pk>/modifier/", views.dish_update, name="dish_update"),
    path("staff/menu/plats/<int:pk>/basculer/", views.dish_toggle, name="dish_toggle"),
    path("staff/menu/plats/<int:pk>/supprimer/", views.dish_delete, name="dish_delete"),
]
