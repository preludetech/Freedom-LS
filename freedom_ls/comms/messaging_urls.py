from django.urls import path

from freedom_ls.comms import messaging_views

app_name = "conversations"

urlpatterns = [
    path("", messaging_views.inbox, name="inbox"),
    path("unread-badge/", messaging_views.partial_unread_badge, name="unread_badge"),
    path("new/", messaging_views.start, name="start"),
    path(
        "new/search/",
        messaging_views.partial_recipient_search,
        name="recipient_search",
    ),
    path("<uuid:pk>/", messaging_views.thread, name="thread"),
    path("<uuid:pk>/send/", messaging_views.send, name="send"),
]
