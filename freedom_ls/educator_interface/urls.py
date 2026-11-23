from django.urls import re_path

from freedom_ls.educator_interface.panels.cohort import report_download
from freedom_ls.educator_interface.panels.learner import import_views

from . import views

app_name = "educator_interface"

urlpatterns = [
    # Must come first: without an organisation segment, "" would otherwise
    # be swallowed by the catch-all path_string below.
    re_path(r"^$", views.interface_root, name="root"),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/cohorts/(?P<cohort_pk>[0-9a-f-]{36})/reports/(?P<report_pk>[0-9a-f-]{36})/download/$",
        report_download.cohort_report_download,
        name="cohort_report_download",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/(?P<learner_pk>[0-9a-f-]{36})/conversations/(?P<conversation_pk>[0-9a-f-]{36})/older/$",
        import_views.partial_oversight_thread_older,
        name="oversight_thread_older",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/import/$",
        import_views.learner_import,
        name="learner_import",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/import/(?P<import_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$",
        import_views.learner_import_preview,
        name="learner_import_preview",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/import/template\.csv$",
        import_views.learner_import_template,
        name="learner_import_template",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/import/(?P<import_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/errors\.csv$",
        import_views.learner_import_errors,
        name="learner_import_errors",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/import/(?P<import_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/result/$",
        import_views.learner_import_result,
        name="learner_import_result",
    ),
    re_path(
        r"^organisations/(?P<organisation_slug>[-\w]+)/learners/import/(?P<import_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/status/$",
        import_views.partial_learner_import_status,
        name="learner_import_status",
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
