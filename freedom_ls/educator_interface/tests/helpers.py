"""Shared helpers for tests that read an educator page as an organisation admin."""

from __future__ import annotations

import copy
import csv
import io
import uuid
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol, cast
from urllib.parse import quote

import lxml.html
import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
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
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.models import Conversation
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.role_based_permissions.utils import assign_object_role

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


class RoleHolderClient(Protocol):
    """The `role_holder_client` fixture: a client for a staff user holding
    `role` on `target`."""

    def __call__(
        self, target: Organisation | Cohort, role: str = "organisation_admin"
    ) -> Client: ...


def organisation_admin_viewer(organisation: Organisation) -> User:
    viewer = cast(User, UserFactory(staff=True))
    assign_object_role(viewer, organisation, "organisation_admin")
    return viewer


def assert_plain_sentence(region: lxml.html.HtmlElement, sentence: str) -> None:
    """`sentence` stands as a plain paragraph, not inside a callout box."""
    paragraphs = [
        element
        for element in region.iter("p")
        if " ".join(element.text_content().split()) == sentence
    ]
    assert len(paragraphs) == 1, sentence
    assert not paragraphs[0].xpath("ancestor::*[contains(@class, 'callout')]")


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

REGISTERABLE_ROWS = [
    ("no_owner", True),
    ("owned", True),
    ("shared", True),
    ("held", False),
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
    organisation: Organisation, course: Course, action: str, *, panel: str = "content"
) -> str:
    return _interface_url(
        organisation.slug,
        f"courses/{course.pk}/__tabs/content/__panels/{panel}/__actions/{action}",
    )


def _staff_document(
    client: Client, organisation: Organisation
) -> lxml.html.HtmlElement:
    return _get_document(client, _interface_url(organisation.slug, "staff"))


def _staff_member_row(
    document: lxml.html.HtmlElement, email: str
) -> lxml.html.HtmlElement:
    """The table row whose text includes `email`."""
    (row,) = [
        r
        for r in document.cssselect("#main-content tbody tr")
        if email in r.text_content()
    ]
    return row


def _hold(
    user: User,
    role: str,
    target: Organisation | Cohort,
    grantor: User | None = None,
) -> None:
    assign_role(grantor or UserFactory(superuser=True), user, role, target)


def _header_of(document: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (heading,) = document.cssselect("#instance-title")
    return heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]


def _add_member(cohort: Cohort) -> Learner:
    learner = cast(Learner, LearnerFactory(organisation=cohort.organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


def _learner_page(
    client: Client, learner: Learner, tab: str = ""
) -> lxml.html.HtmlElement:
    path = f"learners/{learner.pk}" + (f"/__tabs/{tab}" if tab else "")
    return _get_document(client, _interface_url(learner.organisation.slug, path))


def _region_text(document: lxml.html.HtmlElement) -> str:
    (region,) = document.cssselect("[data-tab-set]")
    return str(region.text_content())


def _history_rows(document: lxml.html.HtmlElement) -> list[list[str]]:
    return _entry_rows(document, "[data-tab-set]")


def _export_audit_csv(
    client: Client, url: str, table_key: str = "history"
) -> tuple[list[str], list[list[str]], str]:
    """An audit table's CSV export at ``url``: (header, rows, Content-Disposition)."""
    response = client.get(url, {f"{table_key}-export": "csv"})
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    return header, rows, response["Content-Disposition"]


def _history_export_url(learner: Learner) -> str:
    return _interface_url(
        learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
    )


# Shared setup for the educator's Messages tab on the learner page.
messages_section = pytest.mark.usefixtures("mock_site_context", "_messaging_on")


def _msg_educator(organisation: Organisation) -> User:
    educator = cast(User, UserFactory(staff=True))
    _grant(educator, "organisation_admin", organisation)
    return educator


def _grant(user: User, role: str, target: Organisation | Cohort | Site) -> None:
    """Give `user` a role on `target`, granted by a superuser."""
    grantor = cast(User, UserFactory(superuser=True))
    assign_role(grantor, user, role, target)


def _msg_learner(organisation: Organisation, **user_fields: str) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(
                **{"first_name": "Ada", "last_name": "Lovelace"} | user_fields
            ),
        ),
    )


def _msg_conversation(user: User, other: User) -> Conversation:
    return cast(Conversation, ConversationFactory(between=(user, other)))


def _msg_url(organisation: Organisation, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )


def _card_summary(
    card: lxml.html.HtmlElement,
) -> tuple[str, list[str], list[str], bool]:
    """An audit card's title, its field labels, its Who and Target values, and
    whether its toggle names a hidden detail holding the reason."""
    (title,) = card.cssselect("p.font-bold")
    fields = card.cssselect("dl")[0]
    labels = [dt.text_content().strip() for dt in fields.cssselect("dt")]
    values = [" ".join(dd.text_content().split()) for dd in fields.cssselect("dd")]
    (toggle,) = card.cssselect("button[aria-controls]")
    (detail,) = card.cssselect("[data-row-detail]")
    return (
        title.text_content().strip(),
        labels,
        values[1:],
        toggle.get("aria-controls") == detail.get("id")
        and detail.get("hidden") is not None
        and "Asked to leave" in detail.text_content(),
    )


def _get_table_fragment(client: Client, path: str) -> _MonkeyPatchedWSGIResponse:
    return client.get(path, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="history-table")


def _shared_and_own_course_world() -> tuple[Organisation, Course, Course]:
    """An organisation with a course of its own and a same-titled course that
    another organisation owns and shares with it."""
    organisation = OrganisationFactory(name="Harbour College")
    own = CourseFactory(
        title="Workplace Safety", slug="own-safety", audience=CourseAudience.PUBLIC
    )
    own.organisations.add(organisation)
    shared = CourseFactory(
        title="Workplace Safety", slug="shared-safety", audience=CourseAudience.PUBLIC
    )
    shared.organisations.add(OrganisationFactory(name="Northwind Logistics"))
    shared.shared_with.add(organisation)
    return (
        cast(Organisation, organisation),
        cast(Course, own),
        cast(Course, shared),
    )


def _shared_by_notes(document: lxml.html.HtmlElement) -> list[str]:
    return [
        element.text_content().strip()
        for element in document.cssselect("[data-testid='shared-by']")
    ]


def _shared_by_notes_by_row(
    document: lxml.html.HtmlElement,
) -> dict[str, list[str]]:
    """The shared-by notes of each table row, keyed by the row's text."""
    return {
        " ".join(row.text_content().split()): _shared_by_notes(row)
        for row in document.cssselect("tbody tr")
    }


def _notes_for(rows: dict[str, list[str]], name: str) -> list[str]:
    (notes,) = [notes for text, notes in rows.items() if name in text]
    return notes


def _cohort_url(organisation: Organisation, cohort: Cohort, suffix: str = "") -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}{suffix}")


def _get_fragment(client: Client, url: str) -> str:
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


def _post(
    client: Client, url: str, data: dict[str, str] | None = None
) -> _MonkeyPatchedWSGIResponse:
    return client.post(url, data or {}, HTTP_HX_REQUEST="true")


def _picker_dialog(client: Client, url: str) -> lxml.html.HtmlElement:
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


def _dialog_title(document: lxml.html.HtmlElement) -> str:
    (title,) = document.cssselect("#app-modal-title")
    return " ".join(title.text_content().split())


def _site_admin_client(
    site: Site, logged_in_client: Callable[[User], Client]
) -> Client:
    admin = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), admin, "site_admin", site)
    return cast(Client, logged_in_client(admin))


def _edit_name_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/edit_name"
    )


def _named_learner(organisation: Organisation) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name="Ada", last_name="Lovelace"),
        ),
    )


def _learner_state_url(
    organisation: Organisation, learner: Learner, action: str
) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/{action}"
    )


def _remove_url_from_learner(
    organisation: Organisation, learner: Learner, cohort: Cohort | None = None
) -> str:
    url = _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/cohorts"
        "/__actions/remove_from_cohort",
    )
    return f"{url}?cohort={cohort.pk}" if cohort is not None else url


def _membership(
    organisation: Organisation, **cohort_fields: object
) -> tuple[Learner, Cohort]:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner, cohort


def _offered_options(client: Client, url: str) -> set[str]:
    response = client.get(url, HTTP_HX_REQUEST="true")
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value")
        for option in document.cssselect("option[value]")
        if option.get("value")
    }


def _cohort_admin_on(organisation: Organisation, *cohorts: Cohort) -> User:
    grantor = LearnerFactory(user__superuser=True).user
    educator = cast(
        User, LearnerFactory(user__staff=True, organisation=organisation).user
    )
    for cohort in cohorts:
        assign_role(grantor, educator, "cohort_admin", cohort)
    return educator


def _resend_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/resend_setup_email"
    )


def _pending_learner(organisation: Organisation) -> Learner:
    user = UserFactory(email="pending@example.com", last_login=None)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return cast(Learner, LearnerFactory(organisation=organisation, user=user))


def _learner_register_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/register_for_course"
    )


def _learner_unregister_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/registrations"
        "/__actions/deactivate_registration",
    )


def _learner_reregister_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/registrations"
        "/__actions/reactivate_registration",
    )


def _empty_picker_text(client: Client, url: str) -> str:
    """The text of a picker dialog that has nothing to offer, after checking
    it shows no select, no submit button and a Close button."""
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("select") == []
    assert document.cssselect("button[type='submit']") == []
    assert "Close" in [
        button.text_content().strip() for button in document.cssselect("button")
    ]
    return " ".join(document.text_content().split())


def _scoped_request(user: User, organisation: Organisation) -> HttpRequest:
    """A request as `scope_request` leaves it: the user and the organisation
    the table's rows belong to."""
    request = cast(OrganisationScopedRequest, RequestFactory().post("/"))
    request.user = user
    request.organisation = organisation
    return request


def _bulk_confirm(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
) -> _MonkeyPatchedWSGIResponse:
    return _bulk_post(
        client,
        organisation,
        action_name,
        learners,
        confirmed="on",
        expected_count=str(len(learners)),
    )


def _bulk_cohort_confirm(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    cohort: Cohort,
) -> _MonkeyPatchedWSGIResponse:
    return _bulk_confirm_with(
        client, organisation, action_name, learners, cohort=str(cohort.pk)
    )


def _bulk_confirm_with(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    **extra: str,
) -> _MonkeyPatchedWSGIResponse:
    return _bulk_post(
        client,
        organisation,
        action_name,
        learners,
        confirmed="on",
        expected_count=str(len(learners)),
        **extra,
    )


def _bulk_pending_learner(organisation: Organisation) -> Learner:
    user = UserFactory(last_login=None)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return _bulk_learner(organisation=organisation, user=user)


def _assert_message_dialog(
    response: _MonkeyPatchedWSGIResponse, title: str, message: str
) -> None:
    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 422
    assert document.get_element_by_id("app-modal-title").text_content() == title
    assert message in _text(response)
    (close,) = [
        el for el in document.iter("button") if el.text_content().strip() == "Close"
    ]
    assert close.get("autofocus") is not None


def _text(response: _MonkeyPatchedWSGIResponse) -> str:
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


def _cohort(organisation: Organisation, **kwargs: str) -> Cohort:
    return cast(Cohort, CohortFactory(organisation=organisation, **kwargs))


def _remove_role_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "staff/__actions/deactivate_role")


def _staff_member_holding(
    role: str, target: Organisation | Cohort | list[Cohort], **fields: str
) -> User:
    user = cast(User, UserFactory(**fields))
    for each in target if isinstance(target, list) else [target]:
        assign_role(UserFactory(superuser=True), user, role, each)
    return user


def _state_url(organisation: Organisation, action: str) -> str:
    return _interface_url(organisation.slug, f"staff/__actions/{action}")


def _quick_view_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation_slug,
            "path_string": f"{path_string}/__quick-view",
        },
    )


def _get_quick_view(
    client: Client, organisation: Organisation, path_string: str
) -> _MonkeyPatchedWSGIResponse:
    return client.get(
        _quick_view_url(organisation.slug, path_string), HTTP_HX_REQUEST="true"
    )


def _add_to_cohort_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
    )


def _organisation_admin_on(organisation: Organisation) -> User:
    grantor = cast(User, LearnerFactory(user__superuser=True).user)
    educator = cast(
        User, LearnerFactory(user__staff=True, organisation=organisation).user
    )
    assign_role(grantor, educator, "organisation_admin", organisation)
    return educator


def _move_url_from_learner(
    organisation: Organisation,
    learner: Learner,
    source: Cohort | None = None,
    destination: Cohort | None = None,
) -> str:
    url = _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/cohorts/__actions/move",
    )
    params = []
    if source is not None:
        params.append(f"cohort={source.pk}")
    if destination is not None:
        params.append(f"destination={destination.pk}")
    return f"{url}?{'&'.join(params)}" if params else url


def _add_learners_list_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "learners/__actions/add_learner")


def _cohort_with_courses(
    organisation: Organisation, course_count: int, **cohort_fields: object
) -> Cohort:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    for _ in range(course_count):
        CohortCourseRegistrationFactory(cohort=cohort)
    return cohort


def _course_option_values(response: _MonkeyPatchedWSGIResponse) -> set[str]:
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value")
        for option in document.cssselect("select[name='course'] option")
        if option.get("value")
    }


def _org_admin(organisation: Organisation) -> User:
    admin = cast(User, UserFactory(staff=True))
    assign_object_role(admin, organisation, "organisation_admin")
    return admin


def _tab_url(learner: Learner) -> str:
    return _msg_url(learner.organisation, f"learners/{learner.pk}/__tabs/messages")


def _view_conversation_url(learner: Learner) -> str:
    return f"{_tab_url(learner)}/__panels/others/__actions/view_conversation"


def _open_conversation(
    client: Client, learner: Learner, conversation: object, **extra: str
) -> _MonkeyPatchedWSGIResponse:
    return client.get(
        f"{_view_conversation_url(learner)}?conversation={conversation}",
        HTTP_HX_REQUEST="true",
        **extra,
    )


def _viewed_entries() -> list[AuditLogEntry]:
    return list(AuditLogEntry.unscoped.filter(action="conversation.viewed"))


def _oversight_scene() -> tuple[Organisation, User, Learner, Conversation]:
    organisation = cast(Organisation, OrganisationFactory())
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    MessageFactory(conversation=conversation, sender=educator, body="oversight me")
    return organisation, educator, learner, conversation


def _older_url(
    learner: Learner,
    conversation_pk: object,
    cursor: str,
    organisation: Organisation | None = None,
) -> str:
    slug = (organisation or learner.organisation).slug
    base = reverse(
        "educator_interface:oversight_thread_older",
        kwargs={
            "organisation_slug": slug,
            "learner_pk": str(learner.pk),
            "conversation_pk": str(conversation_pk),
        },
    )
    return f"{base}?before={quote(cursor)}" if cursor else base


def _cohort_page(client: Client, cohort: Cohort) -> lxml.html.HtmlElement:
    return _get_document(
        client, _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}")
    )


def _export_csv(
    client: Client, path_string: str, organisation: Organisation
) -> tuple[list[str], list[list[str]], str]:
    """The learners table's CSV export for ``path_string``: (header, rows, filename)."""
    response = client.get(
        _interface_url(organisation.slug, path_string), {"learners-export": "csv"}
    )
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    return header, rows, response["Content-Disposition"]


def _cohort_history_tab(client: Client, cohort: Cohort) -> lxml.html.HtmlElement:
    return _get_document(client, _cohort_history_url(cohort))


def _cohort_history_url(cohort: Cohort) -> str:
    return _interface_url(
        cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"
    )


def _unregister_post_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/courses/__actions/deactivate_cohort_registration"
    )


def _unregister_url(
    organisation: Organisation,
    cohort: Cohort,
    registration: CohortCourseRegistration | str,
) -> str:
    pk = registration if isinstance(registration, str) else registration.pk
    return f"{_unregister_post_url(organisation, cohort)}?registration={pk}"


def _registered_cohort(
    organisation: Organisation, course_title: str = "Algebra", **cohort_fields: object
) -> tuple[Cohort, CohortCourseRegistration]:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    registration = cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title=course_title)
        ),
    )
    return cohort, registration


def _pdf_url(organisation_slug: str, cohort_pk: object, report_pk: object) -> str:
    return reverse(
        "educator_interface:cohort_report_download",
        kwargs={
            "organisation_slug": organisation_slug,
            "cohort_pk": cohort_pk,
            "report_pk": report_pk,
        },
    )


def _ready_report(cohort: Cohort, **fields: object) -> GeneratedReport:
    report = cast(
        GeneratedReport,
        GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY, **fields
        ),
    )
    report.file.save("r.pdf", ContentFile(b"%PDF-1.4 bytes"), save=True)
    return report


def _remove_url_from_cohort(
    organisation: Organisation, cohort: Cohort, learner: Learner | None = None
) -> str:
    url = _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/remove_from_cohort"
    )
    return f"{url}?learner={learner.pk}" if learner is not None else url


def _move_url_from_cohort(
    organisation: Organisation, source: Cohort, learner: Learner
) -> str:
    url = _cohort_url(organisation, source, "/__tabs/learners/__actions/move")
    return f"{url}?learner={learner.pk}"


class _RolledBackError(Exception):
    pass
