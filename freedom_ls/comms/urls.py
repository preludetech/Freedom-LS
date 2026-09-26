from django.urls import path

from freedom_ls.comms import views

app_name = "comms"

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("badge/", views.notification_badge, name="notification_badge"),
    path("<uuid:pk>/open/", views.notification_open, name="notification_open"),
    path(
        "<uuid:pk>/read/", views.notification_mark_read, name="notification_mark_read"
    ),
    path(
        "<uuid:pk>/unread/",
        views.notification_mark_unread,
        name="notification_mark_unread",
    ),
    path(
        "read-all/", views.notification_mark_all_read, name="notification_mark_all_read"
    ),
]
