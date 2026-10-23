from django.urls import re_path

from . import views

app_name = "educator_interface"

urlpatterns = [
    # Must come first: without an organisation segment, "" would otherwise
    # be swallowed by the catch-all path_string below.
    re_path(r"^$", views.interface_root, name="root"),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/messages/unread-count/$",
        views.messages_unread_count,
        name="messages_unread_count",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/cohorts/(?P<cohort_pk>[0-9a-f-]{36})/members-csv/$",
        views.cohort_members_csv,
        name="cohort_members_csv",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/cohorts/(?P<cohort_pk>[0-9a-f-]{36})/reports/(?P<report_pk>[0-9a-f-]{36})/download/$",
        views.cohort_report_download,
        name="cohort_report_download",
    ),
    # Django's slug path converters belong to path(), which cannot express a
    # trailing catch-all — so the class is spelled out here instead. It matches
    # the unicode converter rather than the ASCII one, because an organisation
    # slug keeps the script its name was written in.
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/(?P<path_string>.*)$",
        views.interface,
        name="interface",
    ),
]
