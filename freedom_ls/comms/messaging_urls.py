from django.urls import path

from freedom_ls.comms import messaging_views

app_name = "conversations"

urlpatterns = [
    path("", messaging_views.inbox, name="inbox"),
    path("poll/", messaging_views.partial_inbox_poll, name="inbox_poll"),
    path("unread-badge/", messaging_views.partial_unread_badge, name="unread_badge"),
    path("new/", messaging_views.start, name="start"),
    path(
        "new/search/",
        messaging_views.partial_recipient_search,
        name="recipient_search",
    ),
    path("<uuid:pk>/", messaging_views.thread, name="thread"),
    path(
        "<uuid:pk>/older/",
        messaging_views.partial_thread_older,
        name="thread_older",
    ),
    path(
        "<uuid:pk>/poll/",
        messaging_views.partial_thread_poll,
        name="thread_poll",
    ),
    path("<uuid:pk>/send/", messaging_views.send, name="send"),
]
