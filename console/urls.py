from django.urls import path

from . import views

app_name = "console"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.order_list, name="orders"),
    path("orders/<str:reference>/", views.order_detail, name="order_detail"),
    path("menu/categories/", views.category_list, name="categories"),
    path("menu/categories/add/", views.category_form_view, name="category_add"),
    path("menu/categories/<int:pk>/edit/", views.category_form_view, name="category_edit"),
    path("menu/categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("menu/food-items/", views.food_item_list, name="food_items"),
    path("menu/food-items/add/", views.food_item_form_view, name="food_item_add"),
    path("menu/food-items/<int:pk>/edit/", views.food_item_form_view, name="food_item_edit"),
    path("menu/food-items/<int:pk>/delete/", views.food_item_delete, name="food_item_delete"),
    path("catering/", views.catering_list, name="catering"),
    path("catering/<int:pk>/", views.catering_detail, name="catering_detail"),
    path("messages/", views.message_list, name="messages"),
    path("messages/<int:pk>/", views.message_detail, name="message_detail"),
]
