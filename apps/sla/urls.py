from django.urls import path

from . import views

app_name = "sla"

urlpatterns = [
    path("", views.policy_settings, name="settings"),
]