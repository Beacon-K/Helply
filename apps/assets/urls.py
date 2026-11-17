from django.urls import path

from . import views

app_name = "assets"

urlpatterns = [
    path("", views.asset_list, name="list"),
    path("export/", views.asset_export, name="export"),
    path("import/template/", views.asset_import_template, name="import_template"),
    path("import/", views.asset_import, name="import"),
    path("import/preview/", views.asset_import_preview, name="import_preview"),
    path("import/confirm/", views.asset_import_confirm, name="import_confirm"),
    path("import/cancel/", views.asset_import_cancel, name="import_cancel"),
    path("live/", views.asset_list_version, name="live"),
    path("new/", views.asset_create, name="create"),
    path("<int:pk>/edit/", views.asset_edit, name="edit"),
    path("<int:pk>/delete/", views.asset_delete, name="delete"),
    path("<int:pk>/", views.asset_detail, name="detail"),
    path("<int:pk>/live/", views.asset_detail_version, name="detail_live"),
]
