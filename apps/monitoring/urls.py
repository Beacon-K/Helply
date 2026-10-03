from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("", views.server_list, name="list"),
    path("data/", views.fleet_data, name="data"),
    path("new/", views.server_create, name="create"),
    path("api/report/", views.ingest, name="ingest"),
    path("agent/<str:name>", views.agent_file, name="agent_file"),
    path("<int:pk>/", views.server_detail, name="detail"),
    path("<int:pk>/data/", views.server_data, name="detail_data"),
    path("<int:pk>/edit/", views.server_edit, name="edit"),
    path("<int:pk>/install/", views.server_install, name="install"),
    path("<int:pk>/token/", views.server_token, name="token"),
    path("<int:pk>/maintenance/", views.server_maintenance, name="maintenance"),
    path("<int:pk>/delete/", views.server_delete, name="delete"),
]
