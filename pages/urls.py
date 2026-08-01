"""URLs for the marketing pages."""

from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("about/", views.about, name="about"),
    path("catering/", views.catering, name="catering"),
    path("contact/", views.contact, name="contact"),
]
