from django.urls import path

from . import views

app_name = "kb"

urlpatterns = [
    path("", views.article_list, name="list"),
    path("new/", views.article_create, name="create"),
    path("<slug:slug>/", views.article_detail, name="detail"),
    path("<slug:slug>/edit/", views.article_edit, name="edit"),
    path("<slug:slug>/delete/", views.article_delete, name="delete"),
    path("<slug:slug>/vote/", views.article_vote, name="vote"),
    path("<slug:slug>/suggestions/<int:pk>/done/", views.suggestion_done, name="suggestion_done"),
    path("<slug:slug>/suggest/", views.article_suggest, name="suggest"),
]
