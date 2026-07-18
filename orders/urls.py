from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    # Public cart + QR checkout
    path("menu/ajouter/", views.cart_add, name="cart_add"),
    path("menu/panier/", views.cart_view, name="cart"),
    path("menu/panier/modifier/", views.cart_update, name="cart_update"),
    path("menu/commander/", views.checkout_scan, name="checkout_scan"),
    path("menu/commander/valider/", views.checkout_submit, name="checkout_submit"),
    # Printed table QR still points here
    path("order/<str:token>/", views.order_qr_landing, name="menu"),
    path("order/<str:token>/confirmation/<int:pk>/", views.order_confirmation, name="confirmation"),
    # Staff
    path("staff/orders/", views.staff_orders, name="staff_list"),
    path("staff/orders/<int:pk>/", views.staff_order_detail, name="staff_detail"),
    path("staff/orders/<int:pk>/ticket/", views.staff_order_ticket, name="staff_ticket"),
    path("staff/orders/<int:pk>/encaisser/", views.staff_order_pay_confirm, name="staff_pay"),
    path("staff/orders/<int:pk>/avancer/", views.staff_order_advance, name="staff_advance"),
    path("staff/orders/<int:pk>/encaisser/confirmer/", views.staff_order_mark_paid, name="staff_mark_paid"),
    path("staff/orders/<int:pk>/remise/", views.staff_order_discount, name="staff_discount"),
    path("staff/orders/<int:pk>/remise/decision/", views.staff_order_discount_decide, name="staff_discount_decide"),
    path("staff/orders/<int:pk>/annuler/", views.staff_order_cancel, name="staff_cancel"),
]
