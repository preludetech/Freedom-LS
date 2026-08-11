from django.urls import re_path

from . import views

app_name = "educator_interface"

urlpatterns = [
    # Must come first: without an organisation segment, "" would otherwise
    # be swallowed by the catch-all path_string below.
    re_path(r"^$", views.interface_root, name="root"),
    # Django's `slug` path converter belongs to path(), which cannot express
    # a trailing catch-all — so the same character class it uses is spelled
    # out here instead.
    re_path(
        r"^organisations/(?P<organisation_slug>[-a-zA-Z0-9_]+)/(?P<path_string>.*)$",
        views.interface,
        name="interface",
    ),
]
