from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Model
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.panels.audit_log.config import AuditLogConfig
from freedom_ls.educator_interface.panels.cohort.config import CohortConfig
from freedom_ls.educator_interface.panels.cohort.report_panels import (
    DOWNLOAD_COHORT_REPORT,
)
from freedom_ls.educator_interface.panels.common.request import (
    LAST_ORGANISATION_SESSION_KEY,
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.course.config import CourseConfig
from freedom_ls.educator_interface.panels.dashboard.config import DashboardConfig
from freedom_ls.educator_interface.panels.learner.config import LearnerConfig
from freedom_ls.educator_interface.panels.staff.config import StaffConfig
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    Cohort,
)
from freedom_ls.learner_management.queries import (
    organisations_accessible_to,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.views import (
    NavGroup,
    build_menu_items,
    first_visible_section,
    panel_framework_view,
    sections_by_url_name,
)
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.services import report_file_response

# TODO
# Data Tables
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Bulk delete
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


interface_config = [
    NavGroup(
        "Teaching",
        [DashboardConfig, CohortConfig, LearnerConfig, CourseConfig],
    ),
    NavGroup("Administration", [StaffConfig, AuditLogConfig]),
]


@login_required
def interface_root(request: HttpRequest) -> HttpResponse:
    """Redirect a bare /educator/ to a concrete organisation URL.

    The session remembers the last-visited organisation only to decide this
    redirect, and that value is re-authorised on every use — once a URL
    names an organisation, the URL always wins over the session.
    """
    accessible = organisations_accessible_to(request.user)
    remembered_slug = request.session.get(LAST_ORGANISATION_SESSION_KEY)
    organisation = (
        accessible.filter(slug=remembered_slug).first() if remembered_slug else None
    ) or accessible.first()  # accessible is ordered by name
    if organisation is None:
        raise Http404
    # Which sections show depends on the viewer's roles in this organisation:
    # someone who sees the staff list and nothing else has no Dashboard.
    _attach_organisation(request, organisation.slug)
    section = first_visible_section(interface_config, request)
    if section is None:
        raise Http404
    return redirect(
        "educator_interface:interface",
        organisation_slug=organisation.slug,
        path_string=section.url_name,
    )


def _resolve_organisation(user: User, organisation_slug: str) -> Organisation:
    """The organisation named by `organisation_slug`, if `user` can access it.

    "No such slug" and "slug exists but you have no access" both 404
    identically.
    """
    organisation = get_object_or_404(Organisation, slug=organisation_slug)
    if not organisations_accessible_to(user).filter(pk=organisation.pk).exists():
        raise Http404
    return organisation


def _attach_organisation(request: HttpRequest, organisation_slug: str) -> Organisation:
    """Resolve and authorise the organisation once and put it on the request.

    Everything the section configs list in required_request_attrs is set
    here, so a page and a file download start from the same scoped request.
    """
    organisation = _resolve_organisation(cast(User, request.user), organisation_slug)
    scoped_request = cast(OrganisationScopedRequest, request)
    scoped_request.organisation = organisation
    scoped_request.panel_scope_name = organisation.name
    scoped_request.panel_url_kwargs = {"organisation_slug": organisation.slug}
    return organisation


def _scoped_cohort(
    request: HttpRequest, organisation_slug: str, cohort_pk: str
) -> Cohort:
    """The cohort named in a file URL, after the organisation and cohort checks a page runs."""
    _attach_organisation(request, organisation_slug)
    return cast(Cohort, CohortConfig.get_instance_view(request, cohort_pk).instance)


@login_required
def cohort_report_download(
    request: HttpRequest, organisation_slug: str, cohort_pk: str, report_pk: str
) -> FileResponse:
    cohort = _scoped_cohort(request, organisation_slug, cohort_pk)
    report = get_object_or_404(
        GeneratedReport.objects.select_related("cohort__organisation"),
        pk=report_pk,
        cohort=cohort,
    )
    if not can(request.user, DOWNLOAD_COHORT_REPORT, cohort):
        raise Http404
    return report_file_response(report)


def scope_request(
    request: HttpRequest, organisation_slug: str
) -> OrganisationScopedRequest:
    """Resolve and authorise the organisation named in the URL, and set the
    attributes the shell and the panels read off the request.

    Selecting an organisation is an authorisation decision, not a filter:
    unlike Site, which is derived from the request host and cannot be
    forged, an organisation comes from user-supplied URL input. "No such
    slug" and "slug exists but you have no access" both 404 identically — a
    403 would confirm the slug is real and let an attacker enumerate a
    Site's organisation names.
    """
    _attach_organisation(request, organisation_slug)
    scoped_request = cast(OrganisationScopedRequest, request)
    scoped_request.accessible_organisations = list(
        organisations_accessible_to(request.user)
    )
    # Rendered into the same OOB bundle panel_framework already assembles
    # for breadcrumbs/sidebar/title/announcer (panel_framework/views.py) —
    # on every navigation, not only a switch, because the switcher's
    # per-organisation links embed the current path_string, which changes
    # on every navigation and would otherwise go stale the moment the user
    # moves to a different section without switching organisation.
    scoped_request.panel_extra_oob = [
        "educator_interface/partials/organisation_switcher.html"
    ]
    return scoped_request


def standalone_page_context(
    request: OrganisationScopedRequest, heading: str, section: str
) -> dict[str, object]:
    """The shell context for a page outside the panel framework: the menu
    with `section` marked, and a trail back to the section, shaped like the
    one an instance page gets so the shell renders it as a back link."""
    extra_url_kwargs = request.panel_url_kwargs
    url_name = "educator_interface:interface"
    # The switcher links to the same path in another organisation; a run or
    # import belongs to one organisation, so the other lands on the section.
    request.path_string = section
    section_config = sections_by_url_name(interface_config)[section]
    return {
        "menu_groups": build_menu_items(
            interface_config,
            url_name,
            request,
            active_section=section,
            extra_url_kwargs=extra_url_kwargs,
        ),
        "breadcrumbs": [
            {
                "label": section_config.menu_label,
                "url": reverse(
                    url_name, kwargs={"path_string": section, **extra_url_kwargs}
                ),
            },
            {"label": heading},
        ],
        "heading": heading,
    }


@login_required
def interface(
    request: HttpRequest, organisation_slug: str, path_string: str = ""
) -> HttpResponse | StreamingHttpResponse:
    """Serve the panel framework for the organisation named in the URL."""
    scoped_request = scope_request(request, organisation_slug)
    organisation = scoped_request.organisation
    scoped_request.path_string = path_string
    # Guarded so the session store is only written when the value actually
    # changes — an unconditional assignment would mark the session dirty on
    # every educator page load.
    if request.session.get(LAST_ORGANISATION_SESSION_KEY) != organisation.slug:
        request.session[LAST_ORGANISATION_SESSION_KEY] = organisation.slug

    if not path_string.strip("/"):
        # The organisation's own URL names no section: land on the first one
        # the visitor's roles show, as the educator root does.
        landing = first_visible_section(interface_config, scoped_request)
        if landing is None:
            raise Http404
        return redirect(
            "educator_interface:interface",
            organisation_slug=organisation.slug,
            path_string=landing.url_name,
        )

    is_switch = request.headers.get("X-Organisation-Switch") == "true"
    landed_elsewhere = False
    if is_switch:
        scoped_request.panel_announcement = f"Now viewing {organisation.name}"
        # The switcher links to the section the visitor is on, which their
        # roles in this organisation may not show. They land on one it does.
        asked = sections_by_url_name(interface_config).get(path_string.split("/", 1)[0])
        if asked is not None and not (
            asked.is_visible(scoped_request) and asked.is_available(scoped_request)
        ):
            landing = first_visible_section(interface_config, scoped_request)
            if landing is None:
                raise Http404
            path_string = landing.url_name
            scoped_request.path_string = path_string
            landed_elsewhere = True

    try:
        response = panel_framework_view(
            config=interface_config,
            request=scoped_request,
            path_string=path_string,
            template_name="educator_interface/interface.html",
            url_name="educator_interface:interface",
        )
    except OrganisationScopeDenied:
        # Only a switch request gets the softened "wrong organisation"
        # reply — every other 404 from path resolution (unknown segment,
        # missing tab/panel/action, deleted object) must still propagate,
        # switch header or not.
        if not is_switch:
            raise
        section = path_string.split("/", 1)[0]
        section_config = sections_by_url_name(interface_config)[section]
        section_model: type[Model] | None = getattr(section_config, "model", None)
        # authorise_instance only ever raises OrganisationScopeDenied from a
        # config with a real model — get_instance_view (panel_framework/
        # views.py) requires one to resolve the detail view in the first
        # place — so this is an internal-consistency check, not a real
        # runtime path.
        if section_model is None:
            raise Http404 from None
        label = section_model._meta.verbose_name
        messages.info(
            request,
            f"Switched to {organisation.name} — that {label} isn't in this organisation",
        )
        scoped_request.path_string = section
        response = panel_framework_view(
            config=interface_config,
            request=scoped_request,
            path_string=section,
            template_name="educator_interface/interface.html",
            url_name="educator_interface:interface",
        )
        response["HX-Push-Url"] = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": section},
        )

    if landed_elsewhere:
        response["HX-Push-Url"] = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
        )
    return response
