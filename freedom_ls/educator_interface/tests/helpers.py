"""Shared helpers for tests that read an educator page as an organisation admin."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, cast

import lxml.html
from pytest_django.fixtures import DjangoAssertNumQueries

from django.db import connection
from django.db.models import Model
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import record_entry, record_run_summary
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.content_engine.models import Course as CourseModel
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


def organisation_admin_viewer(organisation: Organisation) -> User:
    viewer = cast(User, UserFactory(staff=True))
    assign_object_role(viewer, organisation, "organisation_admin")
    return viewer


def get_interface_page(
    organisation: Organisation, path_string: str, viewer: User
) -> str:
    client = Client()
    client.force_login(viewer)
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": path_string,
            },
        )
    )
    assert response.status_code == 200
    return str(response.content.decode())


def profile_picture_sources(content: str) -> list[str]:
    return [
        image.get("src")
        for image in lxml.html.fromstring(content).cssselect(
            "img[data-profile-picture]"
        )
    ]


def page_after_adding_rows(
    organisation: Organisation,
    path_string: str,
    add_rows: Callable[[Organisation, int], None],
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> str:
    """The page once four more rows are added, asserting it costs no more queries than with one."""
    viewer = organisation_admin_viewer(organisation)
    add_rows(organisation, 1)
    with CaptureQueriesContext(connection) as one_row:
        get_interface_page(organisation, path_string, viewer)
    add_rows(organisation, 4)

    with django_assert_max_num_queries(len(one_row.captured_queries)):
        return get_interface_page(organisation, path_string, viewer)


def _public_course() -> Course:
    return cast(Course, CourseFactory(audience=CourseAudience.PUBLIC))


def course_per_reach_row(organisation: Organisation) -> dict[str, Course]:
    """One public, published course for each way a course can stand to
    `organisation`, keyed by row id:

    - ``no_owner``: no owning organisation.
    - ``owned``: owned by `organisation`.
    - ``shared``: owned by another organisation and shared with `organisation`.
    - ``held``: owned by another organisation, not shared, but a cohort and a
      learner of `organisation` each hold an inactive registration on it.
    - ``unreached``: owned by another organisation, not shared, with no
      registration held by `organisation`.
    """
    other = OrganisationFactory()
    owned = _public_course()
    owned.organisations.add(organisation)
    shared = _public_course()
    shared.organisations.add(other)
    shared.shared_with.add(organisation)
    held = _public_course()
    held.organisations.add(other)
    CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation), course=held, is_active=False
    )
    LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=organisation), course=held, is_active=False
    )
    unreached = _public_course()
    unreached.organisations.add(other)
    return {
        "no_owner": _public_course(),
        "owned": owned,
        "shared": shared,
        "held": held,
        "unreached": unreached,
    }


def _educator_request(
    site_aware_request: RequestFactory, organisation: Organisation
) -> HttpRequest:
    educator = LearnerFactory(user__staff=True).user
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator, "organisation_admin", organisation)
    request = site_aware_request.get("/")
    request.user = educator
    request.organisation = organisation
    return request


def _any_request() -> HttpRequest:
    """For a filter whose apply() reads nothing from the request."""
    return RequestFactory().get("/")


COURSE_REACH_ROWS = [
    ("no_owner", True),
    ("owned", True),
    ("shared", True),
    ("held", True),
    ("unreached", False),
]


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _bulk_learner(**fields: object) -> Learner:
    return cast(Learner, LearnerFactory(**fields))


def _learners_bulk_url(organisation: Organisation, action_name: str) -> str:
    return _interface_url(organisation.slug, f"learners/__actions/{action_name}")


def _bulk_post(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    **extra: str,
) -> _MonkeyPatchedWSGIResponse:
    return client.post(
        _learners_bulk_url(organisation, action_name),
        {"keys": [str(learner.pk) for learner in learners], **extra},
        HTTP_HX_REQUEST="true",
    )


def _bulk_text(response: _MonkeyPatchedWSGIResponse) -> str:
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


QUERY_BUDGET = 60


def _get_document(client: Client, url: str) -> lxml.html.HtmlElement:
    response = client.get(url)
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


def _history_entry(learner: Learner, **overrides: object) -> AuditLogEntry:
    return cast(
        AuditLogEntry,
        AuditLogEntryFactory(
            target=learner,
            organisation=learner.organisation,
            action="learner.deactivated",
            **overrides,
        ),
    )


def _visible_text(element: lxml.html.HtmlElement) -> str:
    """The text of `element` without the avatar chip's inline stylesheet."""
    clone = copy.deepcopy(element)
    for style in clone.cssselect("style"):
        style.drop_tree()
    return str(clone.text_content()).strip()


def _entry_rows(document: lxml.html.HtmlElement, selector: str) -> list[list[str]]:
    """Each entry row's data cells, without its toggle cell or its detail row."""
    return [
        [_visible_text(cell) for cell in row.cssselect("td")][1:]
        for row in document.cssselect(f"{selector} tbody tr:not([data-row-detail])")
    ]


def _row_details(document: lxml.html.HtmlElement, selector: str) -> list[str]:
    """The text of each row detail, in row order."""
    return [
        " ".join(row.text_content().split())
        for row in document.cssselect(f"{selector} tbody tr[data-row-detail]")
    ]


def _audit_log_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "audit-log")


def _audit_log_rows(document: lxml.html.HtmlElement) -> list[list[str]]:
    return _entry_rows(document, "body")


def _record_run(
    organisation: Organisation,
    learners: Sequence[object],
    run_id: uuid.UUID,
    target_label: str = "Spring cohort",
) -> None:
    for learner in learners:
        record_entry(
            action="learner.deactivated",
            actor=None,
            target=cast(Model, learner),
            target_label=target_label,
            organisation=organisation,
            run_id=run_id,
        )
    record_run_summary(
        action="bulk_action.completed",
        run_id=run_id,
        organisation=organisation,
        actor=None,
        counts={"changed": len(learners), "skipped": 0, "failed": 0},
    )


def _audit_log_document(
    staff_client: Client, organisation: Organisation
) -> lxml.html.HtmlElement:
    return _get_document(staff_client, _audit_log_url(organisation))


def _content_action_url(
    organisation: Organisation, course: CourseModel, action: str
) -> str:
    return _interface_url(
        organisation.slug, f"courses/{course.pk}/__panels/content/__actions/{action}"
    )
