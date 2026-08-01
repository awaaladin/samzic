from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("", views.order_list, name="list"),
    path("success/<str:reference>/", views.order_success, name="success"),
    path("<str:reference>/", views.order_detail, name="detail"),
]
