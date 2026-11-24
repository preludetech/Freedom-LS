"""The actions on a course's Overview tab."""

from __future__ import annotations

import json
from typing import cast
from unittest import mock

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.course.actions import (
    RegisterCohortOnCourseAction,
    RegisterLearnerOnCourseAction,
)
from freedom_ls.educator_interface.panels.course.config import CourseConfig
from freedom_ls.educator_interface.tests.helpers import (
    RoleHolderClient,
    _get_document,
    _interface_url,
    _post,
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
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    COURSE_NOT_OPEN_MESSAGE,
    CourseNotOpenError,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.context import PanelContext

OVERVIEW = "__tabs/overview/__panels/cohorts"


def _page_url(organisation: Organisation, course: Course) -> str:
    return _interface_url(organisation.slug, f"courses/{course.pk}")


def _action_url(
    organisation: Organisation, course: Course, registration_pk: object = None
) -> str:
    url = _interface_url(
        organisation.slug,
        f"courses/{course.pk}/{OVERVIEW}/__actions/deactivate_cohort_registration",
    )
    return url if registration_pk is None else f"{url}?registration={registration_pk}"


def _deactivate_buttons(document: lxml.html.HtmlElement) -> list[str]:
    """The distinct aria-labels of the Deactivate triggers in the Cohort
    registrations panel. The table renders each row for wide and narrow
    screens, so a row's trigger appears more than once."""
    (panel,) = document.cssselect("section[data-panel='cohorts']")
    return sorted(
        {
            button.get("aria-label")
            for button in panel.cssselect("button")
            if button.text_content().strip() == "Deactivate"
        }
    )


def _register(
    organisation: Organisation, course: Course, **cohort_fields: object
) -> tuple[Cohort, CohortCourseRegistration]:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    return cohort, cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(cohort=cohort, course=course),
    )


@pytest.mark.django_db
def test_an_organisation_admin_sees_deactivate_on_an_active_row_of_an_active_cohort(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course, name="Cohort A")
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _deactivate_buttons(document) == ["Deactivate Cohort A"]


@pytest.mark.django_db
def test_a_cards_deactivate_button_sits_in_the_item_footer_not_the_value_grid(
    role_holder_client: RoleHolderClient,
) -> None:
    """A card's Deactivate button used to render inside the label and value grid,
    indented under the labels. It belongs in the card's item footer, at the
    title's left edge."""
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course, name="Cohort A")
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    (panel,) = document.cssselect("section[data-panel='cohorts']")
    (card,) = panel.cssselect("li.panel-data-table-card")
    footer_buttons = card.cssselect("[data-item-footer] button")
    assert [b.get("aria-label") for b in footer_buttons] == ["Deactivate Cohort A"]
    assert card.cssselect("dl button") == []


@pytest.mark.django_db
def test_no_deactivate_on_an_inactive_registration(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=False)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _deactivate_buttons(document) == []


@pytest.mark.django_db
def test_no_deactivate_on_an_active_registration_of_an_inactive_cohort(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _deactivate_buttons(document) == []


@pytest.mark.django_db
def test_the_confirmation_names_the_cohort_course_and_who_loses_access(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    cohort, registration = _register(organisation, course, name="Cohort A")
    CohortMembershipFactory(cohort=cohort)
    client = role_holder_client(organisation)

    response = client.get(
        _action_url(organisation, course, registration.pk), HTTP_HX_REQUEST="true"
    )

    text = " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )
    assert response.status_code == 200
    assert "Deactivate Cohort A's registration for Algebra" in text
    assert "1 learner" in text


@pytest.mark.django_db
def test_a_post_deactivates_the_registration_and_fires_both_events(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort, registration = _register(organisation, course)
    client = role_holder_client(organisation)

    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(registration.pk), "reason": "Course retired"},
    )

    registration.refresh_from_db()
    assert response.status_code == 204
    assert registration.is_active is False
    trigger = json.loads(response["HX-Trigger"])
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(registration.pk)]}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}
    entry = AuditLogEntry.unscoped.get(reason="Course retired")
    assert entry.action == "cohort_registration.deactivated"
    assert entry.target_object_id == str(cohort.pk)


@pytest.mark.django_db
def test_a_post_for_a_cohort_deactivated_after_render_is_422_and_changes_nothing(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort, registration = _register(organisation, course)
    client = role_holder_client(organisation)
    Cohort.objects.filter(pk=cohort.pk).update(is_active=False)

    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(registration.pk), "reason": "Course retired"},
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert registration.is_active is True


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["inactive", "other course", "other organisation"])
def test_a_registration_outside_the_actions_scope_is_a_404(
    role_holder_client: RoleHolderClient, case: str
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)
    if case == "inactive":
        registration = CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=organisation),
            course=course,
            is_active=False,
        )
    elif case == "other course":
        registration = CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=organisation), course=CourseFactory()
        )
    else:
        registration = CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=OrganisationFactory()), course=course
        )

    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(registration.pk), "reason": "Course retired"},
    )

    assert response.status_code == 404
    assert CohortCourseRegistration.objects.get(pk=registration.pk).is_active is (
        case != "inactive"
    )


@pytest.mark.django_db
def test_a_cohort_only_role_acts_on_its_own_cohorts_rows_only(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    own, own_registration = _register(organisation, course, name="Cohort One")
    _other, other_registration = _register(organisation, course, name="Cohort Two")
    client = role_holder_client(own, "cohort_admin")

    document = _get_document(client, _page_url(organisation, course))
    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(other_registration.pk), "reason": "Course retired"},
    )

    assert _deactivate_buttons(document) == ["Deactivate Cohort One"]
    assert response.status_code == 404
    other_registration.refresh_from_db()
    assert other_registration.is_active is True
    assert own_registration.is_active is True


@pytest.mark.django_db
def test_the_panel_refreshes_on_registration_and_cohort_changes(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    (panel,) = document.cssselect("section[data-panel='cohorts']")
    trigger = panel.get("hx-trigger")
    assert f"{REGISTRATION_CHANGED} from:body" in trigger
    assert f"{COHORT_CHANGED} from:body" in trigger


@pytest.mark.django_db
def test_the_overview_render_does_not_query_per_cohort_row(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)
    _get_document(client, _page_url(organisation, course))

    def queries_with(rows: int) -> int:
        for _ in range(rows):
            _register(organisation, course)
        with CaptureQueriesContext(connection) as captured:
            _get_document(client, _page_url(organisation, course))
        return len(captured)

    one_more = queries_with(1)
    three_more = queries_with(2)

    assert three_more <= one_more + 1


def _register_url(organisation: Organisation, course: Course) -> str:
    return _interface_url(
        organisation.slug,
        f"courses/{course.pk}/{OVERVIEW}/__actions/register_cohort",
    )


def _footer_buttons(document: lxml.html.HtmlElement) -> list[str]:
    """The text of the Register trigger in the Cohort registrations panel."""
    (panel,) = document.cssselect("section[data-panel='cohorts']")
    return [
        button.text_content().strip()
        for button in panel.cssselect("button")
        if button.text_content().strip() == "Register"
    ]


def _options(response_content: bytes) -> list[str]:
    document = lxml.html.fromstring(response_content.decode())
    return sorted(
        option.text_content().strip()
        for option in document.cssselect("select[name='cohort'] option")
        if option.get("value")
    )


def _title(response_content: bytes) -> str:
    document = lxml.html.fromstring(response_content.decode())
    (title,) = document.cssselect("#app-modal-title")
    return " ".join(title.text_content().split())


@pytest.mark.django_db
def test_the_footer_shows_register_to_an_organisation_admin(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _footer_buttons(document) == ["Register"]


@pytest.mark.django_db
def test_the_footer_shows_register_to_a_cohort_only_role(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_admin")

    document = _get_document(client, _page_url(organisation, course))

    assert _footer_buttons(document) == ["Register"]


@pytest.mark.django_db
def test_the_footer_hides_register_from_a_cohort_viewer(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_viewer")

    document = _get_document(client, _page_url(organisation, course))

    assert _footer_buttons(document) == []


@pytest.mark.django_db
def test_register_is_not_offered_for_a_course_not_available_to_the_organisation(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    request = cast(OrganisationScopedRequest, RequestFactory().get("/x"))
    request.organisation = organisation
    ctx = PanelContext(
        request=request,
        instance=course,
        base_url="/x",
        name="cohorts",
        config=CourseConfig,
    )
    offered_before = RegisterCohortOnCourseAction().is_offered(ctx)
    course.organisations.add(OrganisationFactory())

    assert offered_before is True
    assert RegisterCohortOnCourseAction().is_offered(ctx) is False


@pytest.mark.django_db
def test_the_picker_lists_unregistered_and_inactively_registered_cohorts_only(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    CohortFactory(organisation=organisation, name="Free")
    inactive_registration = CohortFactory(organisation=organisation, name="Lapsed")
    CohortCourseRegistrationFactory(
        cohort=inactive_registration, course=course, is_active=False
    )
    _register(organisation, course, name="Registered")
    CohortFactory(organisation=organisation, name="Closed", is_active=False)
    CohortFactory(organisation=OrganisationFactory(), name="Elsewhere")
    client = role_holder_client(organisation)

    response = client.get(_register_url(organisation, course), HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert _options(response.content) == ["Free", "Lapsed"]


@pytest.mark.django_db
def test_a_cohort_only_role_is_offered_only_its_own_cohorts(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    own = CohortFactory(organisation=organisation, name="Cohort One")
    CohortFactory(organisation=organisation, name="Cohort Two")
    client = role_holder_client(own, "cohort_admin")

    response = client.get(_register_url(organisation, course), HTTP_HX_REQUEST="true")

    assert _options(response.content) == ["Cohort One"]


@pytest.mark.django_db
def test_the_title_asks_about_a_cohort_until_one_is_chosen(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    cohort = CohortFactory(organisation=organisation, name="Cohort A")
    client = role_holder_client(organisation)
    label = course.label_for(organisation)

    unchosen = client.get(_register_url(organisation, course), HTTP_HX_REQUEST="true")
    chosen = client.get(
        f"{_register_url(organisation, course)}?cohort={cohort.pk}",
        HTTP_HX_REQUEST="true",
    )

    assert _title(unchosen.content) == f"Register a cohort for {label}?"
    assert _title(chosen.content) == f"Register Cohort A for {label}?"


@pytest.mark.django_db
def test_an_empty_picker_shows_the_empty_message(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course)
    client = role_holder_client(organisation)

    response = client.get(_register_url(organisation, course), HTTP_HX_REQUEST="true")

    text = " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )
    assert "Every cohort you can register already has this course." in text


@pytest.mark.django_db
def test_registering_a_listed_cohort_registers_it_and_fires_both_events(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(organisation)

    response = _post(
        client, _register_url(organisation, course), {"cohort": str(cohort.pk)}
    )

    registration = CohortCourseRegistration.objects.get(cohort=cohort, course=course)
    assert response.status_code == 204
    assert registration.is_active is True
    trigger = json.loads(response["HX-Trigger"])
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(registration.pk)]}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}


@pytest.mark.django_db
def test_registering_a_cohort_with_an_inactive_registration_reactivates_that_row(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=course, is_active=False
    )
    client = role_holder_client(organisation)

    response = _post(
        client, _register_url(organisation, course), {"cohort": str(cohort.pk)}
    )

    registration.refresh_from_db()
    assert response.status_code == 204
    assert registration.is_active is True
    assert CohortCourseRegistration.objects.filter(cohort=cohort).count() == 1


@pytest.mark.django_db
def test_registering_a_cohort_not_in_the_list_is_422(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    elsewhere = CohortFactory(organisation=OrganisationFactory())
    client = role_holder_client(organisation)

    response = _post(
        client, _register_url(organisation, course), {"cohort": str(elsewhere.pk)}
    )

    assert response.status_code == 422
    assert "Choose a cohort from the list." in response.content.decode()
    assert not CohortCourseRegistration.objects.filter(cohort=elsewhere).exists()


@pytest.mark.django_db
def test_a_course_the_service_finds_closed_is_a_422_form_error_and_writes_nothing(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(organisation)

    with mock.patch(
        "freedom_ls.educator_interface.panels.course.actions.register_cohort_for_course",
        side_effect=CourseNotOpenError("This course is not open to the organisation."),
    ):
        response = _post(
            client, _register_url(organisation, course), {"cohort": str(cohort.pk)}
        )

    assert response.status_code == 422
    assert "This course is not open to the organisation." in response.content.decode()
    assert not CohortCourseRegistration.objects.filter(cohort=cohort).exists()


LEARNERS = "__tabs/overview/__panels/learners"


def _learner_action_url(
    organisation: Organisation,
    course: Course,
    action: str,
    registration_pk: object = None,
) -> str:
    url = _interface_url(
        organisation.slug, f"courses/{course.pk}/{LEARNERS}/__actions/{action}"
    )
    return url if registration_pk is None else f"{url}?registration={registration_pk}"


def _direct_buttons(document: lxml.html.HtmlElement, verb: str) -> list[str]:
    """The distinct aria-labels of the `verb` triggers in the Direct
    registrations panel. The table renders each row for wide and narrow
    screens, so a row's trigger appears more than once."""
    (panel,) = document.cssselect("section[data-panel='learners']")
    return sorted(
        {
            button.get("aria-label")
            for button in panel.cssselect("button")
            if button.text_content().strip() == verb
        }
    )


def _direct(
    organisation: Organisation,
    course: Course,
    *,
    is_active: bool = True,
    first_name: str = "Ada",
) -> LearnerCourseRegistration:
    learner = LearnerFactory(
        organisation=organisation, user__first_name=first_name, user__last_name="Test"
    )
    return cast(
        LearnerCourseRegistration,
        LearnerCourseRegistrationFactory(
            learner=learner, course=course, is_active=is_active
        ),
    )


@pytest.mark.django_db
def test_an_active_direct_row_offers_deactivate_and_an_inactive_one_reactivate(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    active = _direct(organisation, course, first_name="Ada")
    inactive = _direct(organisation, course, is_active=False, first_name="Bea")
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _direct_buttons(document, "Deactivate") == [
        f"Deactivate {active.learner.user.display_name}"
    ]
    assert _direct_buttons(document, "Reactivate") == [
        f"Reactivate {inactive.learner.user.display_name}"
    ]


@pytest.mark.django_db
def test_a_learner_the_role_may_not_change_has_no_row_actions(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    own = _direct(organisation, course, first_name="Ada")
    other = _direct(organisation, course, first_name="Bea")
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=own.learner)
    client = role_holder_client(cohort, "cohort_admin")

    document = _get_document(client, _page_url(organisation, course))

    assert _direct_buttons(document, "Deactivate") == [
        f"Deactivate {own.learner.user.display_name}"
    ]
    response = _post(
        client,
        _learner_action_url(organisation, course, "deactivate_registration"),
        {"registration": str(other.pk), "reason": "Left"},
    )
    assert response.status_code == 404
    other.refresh_from_db()
    assert other.is_active is True


@pytest.mark.django_db
def test_the_deactivation_names_a_cohort_keeping_access_that_the_educator_sees(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    registration = _direct(organisation, course)
    seen = CohortFactory(organisation=organisation, name="Cohort A")
    hidden = CohortFactory(organisation=organisation, name="Staff Room")
    for cohort in (seen, hidden):
        CohortMembershipFactory(cohort=cohort, learner=registration.learner)
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
    client = role_holder_client(seen, "cohort_admin")

    response = client.get(
        _learner_action_url(
            organisation, course, "deactivate_registration", registration.pk
        ),
        HTTP_HX_REQUEST="true",
    )

    text = " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )
    assert response.status_code == 200
    assert "They keep access through Cohort A." in text
    assert "Staff Room" not in text


@pytest.mark.django_db
def test_a_post_deactivates_the_direct_registration_and_fires_both_events(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registration = _direct(organisation, course)
    client = role_holder_client(organisation)

    with mock.patch(
        "freedom_ls.educator_interface.panels.common.registration_actions.deactivate_registration"
    ) as deactivate:
        response = _post(
            client,
            _learner_action_url(organisation, course, "deactivate_registration"),
            {"registration": str(registration.pk), "reason": "Left"},
        )

    assert response.status_code == 204
    deactivate.assert_called_once()
    assert deactivate.call_args.args == (registration.learner, course)
    assert deactivate.call_args.kwargs["reason"] == "Left"
    trigger = json.loads(response["HX-Trigger"])
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(registration.learner_id)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(registration.learner_id)]}


@pytest.mark.django_db
def test_a_post_reactivates_the_direct_registration_and_fires_both_events(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registration = _direct(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    with mock.patch(
        "freedom_ls.educator_interface.panels.common.registration_actions.register_for_course"
    ) as register:
        response = _post(
            client,
            _learner_action_url(organisation, course, "reactivate_registration"),
            {"registration": str(registration.pk)},
        )

    assert response.status_code == 204
    register.assert_called_once()
    assert register.call_args.args == (registration.learner, course)
    trigger = json.loads(response["HX-Trigger"])
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(registration.learner_id)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(registration.learner_id)]}


@pytest.mark.django_db
def test_a_real_post_reactivates_the_row(role_holder_client: RoleHolderClient) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registration = _direct(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    _post(
        client,
        _learner_action_url(organisation, course, "reactivate_registration"),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert registration.is_active is True


@pytest.mark.django_db
def test_reactivating_for_a_course_closed_to_the_organisation_is_422(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registration = _direct(organisation, course, is_active=False)
    course.organisations.add(OrganisationFactory())
    client = role_holder_client(organisation)

    response = _post(
        client,
        _learner_action_url(organisation, course, "reactivate_registration"),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()
    assert registration.is_active is False


@pytest.mark.django_db
def test_reactivating_a_course_the_service_finds_closed_is_422_with_its_text(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registration = _direct(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    with mock.patch(
        "freedom_ls.educator_interface.panels.common.registration_actions.register_for_course",
        side_effect=CourseNotOpenError("Not open to this organisation."),
    ):
        response = _post(
            client,
            _learner_action_url(organisation, course, "reactivate_registration"),
            {"registration": str(registration.pk)},
        )

    assert response.status_code == 422
    assert "Not open to this organisation." in response.content.decode()
    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action", ["deactivate_registration", "reactivate_registration"]
)
@pytest.mark.parametrize("case", ["wrong state", "other course", "other organisation"])
def test_a_direct_registration_outside_the_actions_scope_is_a_404(
    role_holder_client: RoleHolderClient, action: str, case: str
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)
    # Deactivate reaches active rows and Reactivate inactive ones, so the
    # other cases use the state the action does reach.
    reachable_state = action == "deactivate_registration"
    if case == "wrong state":
        registration = _direct(organisation, course, is_active=not reachable_state)
    elif case == "other course":
        registration = _direct(organisation, CourseFactory(), is_active=reachable_state)
    else:
        registration = _direct(OrganisationFactory(), course, is_active=reachable_state)

    response = _post(
        client,
        _learner_action_url(organisation, course, action),
        {"registration": str(registration.pk), "reason": "Left"},
    )

    assert response.status_code == 404
    was_active = registration.is_active
    registration.refresh_from_db()
    assert registration.is_active is was_active


@pytest.mark.django_db
def test_the_direct_panel_refreshes_on_registration_and_learner_changes(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _direct(organisation, course)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    (panel,) = document.cssselect("section[data-panel='learners']")
    trigger = panel.get("hx-trigger")
    assert f"{REGISTRATION_CHANGED} from:body" in trigger
    assert f"{LEARNER_CHANGED} from:body" in trigger


@pytest.mark.django_db
def test_the_overview_render_does_not_query_per_direct_row(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)
    _get_document(client, _page_url(organisation, course))

    def queries_with(rows: int) -> int:
        for _ in range(rows):
            _direct(organisation, course)
        with CaptureQueriesContext(connection) as captured:
            _get_document(client, _page_url(organisation, course))
        return len(captured)

    one_more = queries_with(1)
    three_more = queries_with(2)

    assert three_more <= one_more + 1


def _register_learner_url(organisation: Organisation, course: Course) -> str:
    return _learner_action_url(organisation, course, "register_learner")


def _learner_options(response_content: bytes) -> list[str]:
    document = lxml.html.fromstring(response_content.decode())
    return sorted(
        option.text_content().strip()
        for option in document.cssselect("select[name='learner'] option")
        if option.get("value")
    )


def _learner_footer_buttons(document: lxml.html.HtmlElement) -> list[str]:
    """The text of the Register trigger in the Direct registrations panel."""
    (panel,) = document.cssselect("section[data-panel='learners']")
    return [
        button.text_content().strip()
        for button in panel.cssselect("button")
        if button.text_content().strip() == "Register"
    ]


def _named_learner(
    organisation: Organisation, first_name: str, **fields: object
) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user__first_name=first_name,
            user__last_name="Test",
            **fields,
        ),
    )


@pytest.mark.django_db
def test_the_direct_registrations_footer_shows_register_to_an_organisation_admin(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _learner_footer_buttons(document) == ["Register"]


@pytest.mark.django_db
def test_the_direct_registrations_footer_shows_register_to_a_cohort_only_role(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_admin")

    document = _get_document(client, _page_url(organisation, course))

    assert _learner_footer_buttons(document) == ["Register"]


@pytest.mark.django_db
def test_the_direct_registrations_footer_hides_register_from_a_cohort_viewer(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_viewer")

    document = _get_document(client, _page_url(organisation, course))

    assert _learner_footer_buttons(document) == []


@pytest.mark.django_db
def test_register_learner_is_not_offered_for_a_course_not_available_to_the_organisation(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    request = cast(OrganisationScopedRequest, RequestFactory().get("/x"))
    request.organisation = organisation
    ctx = PanelContext(
        request=request,
        instance=course,
        base_url="/x",
        name="learners",
        config=CourseConfig,
    )
    offered_before = RegisterLearnerOnCourseAction().is_offered(ctx)
    course.organisations.add(OrganisationFactory())

    assert offered_before is True
    assert RegisterLearnerOnCourseAction().is_offered(ctx) is False


@pytest.mark.django_db
def test_the_learner_picker_lists_unregistered_and_inactively_registered_learners_only(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _named_learner(organisation, "Free")
    lapsed = _named_learner(organisation, "Lapsed")
    LearnerCourseRegistrationFactory(learner=lapsed, course=course, is_active=False)
    _direct(organisation, course, first_name="Registered")
    _named_learner(organisation, "Closed", is_active=False)
    _named_learner(OrganisationFactory(), "Elsewhere")
    client = role_holder_client(organisation)

    response = client.get(
        _register_learner_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert _learner_options(response.content) == ["Free Test", "Lapsed Test"]


@pytest.mark.django_db
def test_a_cohort_only_role_is_offered_only_the_learners_it_covers(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    own = _named_learner(organisation, "Own")
    _named_learner(organisation, "Other")
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=own)
    client = role_holder_client(cohort, "cohort_admin")

    response = client.get(
        _register_learner_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert _learner_options(response.content) == ["Own Test"]


@pytest.mark.django_db
def test_the_learner_title_asks_about_a_learner_until_one_is_chosen(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    learner = _named_learner(organisation, "Ada")
    client = role_holder_client(organisation)
    label = course.label_for(organisation)

    unchosen = client.get(
        _register_learner_url(organisation, course), HTTP_HX_REQUEST="true"
    )
    chosen = client.get(
        f"{_register_learner_url(organisation, course)}?learner={learner.pk}",
        HTTP_HX_REQUEST="true",
    )

    assert _title(unchosen.content) == f"Register a learner for {label}?"
    assert _title(chosen.content) == f"Register Ada Test for {label}?"


@pytest.mark.django_db
def test_an_empty_learner_picker_shows_the_empty_message(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)

    response = client.get(
        _register_learner_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    text = " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )
    assert "Every learner you can register already has this course." in text


@pytest.mark.django_db
def test_registering_a_listed_learner_registers_them_and_fires_both_events(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    learner = _named_learner(organisation, "Ada")
    client = role_holder_client(organisation)

    response = _post(
        client,
        _register_learner_url(organisation, course),
        {"learner": str(learner.pk)},
    )

    registration = LearnerCourseRegistration.objects.get(learner=learner, course=course)
    assert response.status_code == 204
    assert registration.is_active is True
    trigger = json.loads(response["HX-Trigger"])
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_registering_a_learner_with_an_inactive_registration_reactivates_that_row(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registration = _direct(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    response = _post(
        client,
        _register_learner_url(organisation, course),
        {"learner": str(registration.learner_id)},
    )

    registration.refresh_from_db()
    assert response.status_code == 204
    assert registration.is_active is True
    assert (
        LearnerCourseRegistration.objects.filter(learner=registration.learner).count()
        == 1
    )


@pytest.mark.django_db
def test_registering_a_learner_not_in_the_list_is_422(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    elsewhere = _named_learner(OrganisationFactory(), "Elsewhere")
    client = role_holder_client(organisation)

    response = _post(
        client,
        _register_learner_url(organisation, course),
        {"learner": str(elsewhere.pk)},
    )

    assert response.status_code == 422
    assert "Choose a learner from the list." in response.content.decode()
    assert not LearnerCourseRegistration.objects.filter(learner=elsewhere).exists()


@pytest.mark.django_db
def test_a_learner_registration_the_service_finds_closed_is_a_422_form_error(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    learner = _named_learner(organisation, "Ada")
    client = role_holder_client(organisation)

    with mock.patch(
        "freedom_ls.educator_interface.panels.course.actions.register_for_course",
        side_effect=CourseNotOpenError("This course is not open to the organisation."),
    ):
        response = _post(
            client,
            _register_learner_url(organisation, course),
            {"learner": str(learner.pk)},
        )

    assert response.status_code == 422
    assert "This course is not open to the organisation." in response.content.decode()
    assert not LearnerCourseRegistration.objects.filter(learner=learner).exists()


def _course_seen_but_not_available(organisation: Organisation) -> Course:
    """Another organisation's public course. The organisation's educators see
    it only because one of its cohorts holds a registration, so they may not
    register anyone else for it."""
    course = cast(Course, CourseFactory(audience=CourseAudience.PUBLIC))
    course.organisations.add(OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation), course=course
    )
    return course


@pytest.mark.django_db
def test_registering_a_cohort_for_a_course_not_available_here_is_422(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = _course_seen_but_not_available(organisation)
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(organisation)

    response = _post(
        client, _register_url(organisation, course), {"cohort": str(cohort.pk)}
    )

    assert response.status_code == 422
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()
    assert not CohortCourseRegistration.objects.filter(cohort=cohort).exists()


@pytest.mark.django_db
def test_registering_a_learner_for_a_course_not_available_here_is_422(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = _course_seen_but_not_available(organisation)
    learner = _named_learner(organisation, "Ada")
    client = role_holder_client(organisation)

    response = _post(
        client,
        _register_learner_url(organisation, course),
        {"learner": str(learner.pk)},
    )

    assert response.status_code == 422
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()
    assert not LearnerCourseRegistration.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_an_inactive_direct_row_offers_no_reactivate_on_a_course_not_available_here(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = _course_seen_but_not_available(organisation)
    _direct(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _direct_buttons(document, "Reactivate") == []
