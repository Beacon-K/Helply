from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path("new/for/<int:user_id>/", views.ticket_create_for, name="create_for"),
    path("<int:pk>/", views.ticket_detail, name="detail"),
    path("<int:pk>/action/<slug:action>/", views.ticket_action, name="action"),
    path("<int:pk>/assign/", views.ticket_assign, name="assign"),
    path("<int:pk>/category/", views.ticket_categorize, name="categorize"),
    path("<int:pk>/comment/", views.ticket_comment, name="comment"),
    path("<int:pk>/survey/", views.ticket_survey, name="survey"),
]
