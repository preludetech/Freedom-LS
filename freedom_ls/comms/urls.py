from django.urls import path

from freedom_ls.comms import views

app_name = "comms"

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("<uuid:pk>/open/", views.notification_open, name="notification_open"),
]
