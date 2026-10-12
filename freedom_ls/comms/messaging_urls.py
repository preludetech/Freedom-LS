from django.urls import path

from freedom_ls.comms import messaging_views

app_name = "conversations"

urlpatterns = [
    path("", messaging_views.inbox, name="inbox"),
    path("<uuid:pk>/", messaging_views.thread, name="thread"),
    path("<uuid:pk>/send/", messaging_views.send, name="send"),
]
