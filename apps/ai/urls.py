from django.urls import path

from . import views

app_name = "ai"
urlpatterns = [
    path("ask/", views.ask, name="ask"),
    path("chat/", views.chat, name="chat"),
    path("insights/refresh/", views.insights_refresh, name="insights_refresh"),
    path("ticket/<int:pk>/", views.ticket_copilot, name="copilot"),
    path("feedback/<int:pk>/", views.feedback, name="feedback"),
]
