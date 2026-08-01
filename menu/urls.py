from django.urls import path

from . import views

app_name = "menu"

urlpatterns = [
    path("", views.home, name="home"),
    path("menu/", views.menu, name="menu"),
    path("menu/<slug:slug>/", views.food_detail, name="food_detail"),
]
