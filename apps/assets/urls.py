from django.urls import path

from . import views

app_name = "assets"

urlpatterns = [
    path("", views.asset_list, name="list"),
    path("live/", views.asset_list_version, name="live"),
    path("<int:pk>/", views.asset_detail, name="detail"),
    path("<int:pk>/live/", views.asset_detail_version, name="detail_live"),
]
