from django.urls import path

from . import views

app_name = "kb"

urlpatterns = [
    path("", views.article_list, name="list"),
    path("<slug:slug>/", views.article_detail, name="detail"),
    path("<slug:slug>/vote/", views.article_vote, name="vote"),
    path("<slug:slug>/suggest/", views.article_suggest, name="suggest"),
]
