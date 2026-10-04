from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.people_list, name="list"),
    path("new/", views.people_create, name="create"),
    path("<int:pk>/", views.people_edit, name="edit"),
    path("<int:pk>/toggle/", views.people_toggle, name="toggle"),
    path("<int:pk>/reset/", views.people_reset, name="reset"),
]