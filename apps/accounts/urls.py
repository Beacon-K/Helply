from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.people_list, name="list"),
    path("new/", views.people_create, name="create"),
    path("organization/", views.organization, name="organization"),
    path("departments/new/", views.department_create, name="department_create"),
    path("departments/<int:pk>/rename/", views.department_rename, name="department_rename"),
    path("departments/<int:pk>/delete/", views.department_delete, name="department_delete"),
    path("teams/new/", views.team_create, name="team_create"),
    path("teams/<int:pk>/", views.team_edit, name="team_edit"),
    path("teams/<int:pk>/delete/", views.team_delete, name="team_delete"),
    path("categories/new/", views.category_create, name="category_create"),
    path("categories/<int:pk>/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("<int:pk>/", views.people_edit, name="edit"),
    path("<int:pk>/toggle/", views.people_toggle, name="toggle"),
    path("<int:pk>/reset/", views.people_reset, name="reset"),
]