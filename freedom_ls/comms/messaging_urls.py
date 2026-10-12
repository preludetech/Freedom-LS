from django.urls import path

from freedom_ls.comms import messaging_views

app_name = "conversations"

urlpatterns = [
    path("", messaging_views.inbox, name="inbox"),
    path("unread-badge/", messaging_views.partial_unread_badge, name="unread_badge"),
    path("<uuid:pk>/", messaging_views.thread, name="thread"),
    path("<uuid:pk>/send/", messaging_views.send, name="send"),
]
