from django.urls import re_path
from . import views

app_name = "educator_interface"

urlpatterns = [
    re_path(r"^(?P<path_string>.*)$", views.interface, name="interface"),
]
