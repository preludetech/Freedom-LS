"""The panel actions on a learner, driven through the interface URLs."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.core import mail
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.config import config
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseAudience, CourseVisibility
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.cohort.config import CohortConfig
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    RemoveFromCohortAction,
)
from freedom_ls.educator_interface.tests.helpers import (
    REGISTERABLE_ROWS,
    _add_learners_list_url,
    _add_to_cohort_url,
    _cohort,
    _cohort_admin_on,
    _cohort_history_tab,
    _dialog_title,
    _edit_name_url,
    _empty_picker_text,
    _get_fragment,
    _history_rows,
    _interface_url,
    _learner_page,
    _learner_register_url,
    _learner_reregister_url,
    _learner_state_url,
    _learner_unregister_url,
    _membership,
    _move_url_from_cohort,
    _move_url_from_learner,
    _named_learner,
    _offered_options,
    _organisation_admin_on,
    _pending_learner,
    _picker_dialog,
    _post,
    _remove_url_from_cohort,
    _remove_url_from_learner,
    _resend_url,
    _RolledBackError,
    _site_admin_client,
    course_per_reach_row,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import move_between_cohorts
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    COURSE_NOT_OPEN_MESSAGE,
)
from freedom_ls.learner_management.role_assignment import (
    assign_role,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.tests.audit_assertions import assert_entry

if TYPE_CHECKING:
    pass


@pytest.mark.django_db
def test_the_learner_name_form_puts_each_field_error_under_its_own_field(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "x" * 201, "last_name": "y" * 201},
    )

    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    alerts = document.cssselect("form [role=alert]")
    assert response.status_code == 422
    assert len(alerts) == 2
    for field_name in ("first_name", "last_name"):
        (field,) = document.cssselect(f"form input[name={field_name}]")
        (error,) = [a for a in alerts if a.get("id") == field.get("aria-describedby")]
        assert field.get("aria-invalid") == "true"
        assert "Ensure this value has at most 200 characters" in error.text_content()
        assert "name" not in error.text_content().split("Ensure")[0].lower()


# edit a learner's name


@pytest.mark.django_db
def test_a_site_admins_learner_settings_tab_offers_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    triggers = _settings_triggers(client, organisation, learner)

    assert _edit_name_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_an_organisation_admins_learner_settings_tab_offers_no_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    user = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), user, "organisation_admin", organisation)
    client = logged_in_client(user)

    triggers = _settings_triggers(client, organisation, learner)

    assert _edit_name_url(organisation, learner) not in triggers


@pytest.mark.django_db
def test_edit_name_post_changes_the_users_first_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    learner.user.refresh_from_db()
    assert learner.user.first_name == "Grace"


@pytest.mark.django_db
def test_edit_name_post_sends_the_new_display_name_as_the_page_title(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, trigger["instanceTitleChanged"]["title"]) == (
        204,
        "Grace Hopper",
    )


@pytest.mark.django_db
def test_edit_name_post_fires_the_learner_changed_event_for_the_learner(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


# deactivate and reactivate a learner


def _settings_triggers(
    client: Client, organisation: Organisation, learner: Learner
) -> set[str | None]:
    """The action URLs the learner's Settings tab offers, read as the
    instance-level URLs the actions also answer at."""
    response = client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/settings")
    )
    document = lxml.html.fromstring(response.content.decode())
    controls = [
        *(
            b.get("hx-get")
            for b in document.cssselect("section[data-panel] button[hx-get]")
        ),
        *(
            f.get("hx-post")
            for f in document.cssselect("section[data-panel] form[hx-post]")
        ),
    ]
    return {re.sub(r"/__tabs/settings(/__panels/[\w-]+)?", "", url) for url in controls}


@pytest.mark.django_db
def test_an_active_learners_settings_tab_offers_deactivate_not_reactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    triggers = _settings_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (True, False)


@pytest.mark.django_db
def test_a_removed_learners_settings_tab_offers_reactivate_not_deactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    triggers = _settings_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (False, True)


@pytest.mark.django_db
def test_deactivate_fragment_names_self_registration_only_on_the_default_organisation(
    staff_client: Client, mock_site_context: Site
):
    default = get_default_organisation(mock_site_context)
    learner = LearnerFactory(organisation=default, is_active=True)

    text = _get_fragment(
        staff_client, _learner_state_url(default, learner, "deactivate")
    )

    assert "self-register" in text


@pytest.mark.django_db
def test_deactivate_fragment_omits_self_registration_on_another_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory(is_default=False)
    learner = LearnerFactory(organisation=organisation, is_active=True)

    text = _get_fragment(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    assert "self-register" not in text


@pytest.mark.django_db
def test_reactivate_fragment_says_access_returns_through_existing_cohorts_and_registrations(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    text = _get_fragment(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    assert "existing cohorts and registrations" in text


@pytest.mark.django_db
def test_deactivate_post_answers_204_with_a_location_to_the_learner_page(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    location = json.loads(response["HX-Location"])
    assert (response.status_code, location["path"]) == (
        204,
        _interface_url(organisation.slug, f"learners/{learner.pk}"),
    )


@pytest.mark.django_db
def test_learner_header_state_action_from_a_tab_navigates_back_to_that_tab(
    staff_client: Client,
):
    """Deactivating from the history tab used to land on the Overview tab."""
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)
    tab_path = _interface_url(
        organisation.slug, f"learners/{learner.pk}/__tabs/history"
    )

    response = staff_client.post(
        _learner_state_url(organisation, learner, "deactivate"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL=f"http://testserver{tab_path}",
    )

    assert json.loads(response["HX-Location"])["path"] == tab_path


@pytest.mark.django_db
def test_deactivate_post_sets_the_learner_inactive(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    _post(staff_client, _learner_state_url(organisation, learner, "deactivate"))

    learner.refresh_from_db()
    assert learner.is_active is False


@pytest.mark.django_db
def test_reactivate_post_sets_the_learner_active(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    _post(staff_client, _learner_state_url(organisation, learner, "reactivate"))

    learner.refresh_from_db()
    assert learner.is_active is True


@pytest.mark.django_db
def test_deactivating_a_removed_learner_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    learner.refresh_from_db()
    assert (response.status_code, learner.is_active) == (422, False)


@pytest.mark.django_db
def test_reactivating_an_active_learner_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    assert response.status_code == 422


# remove from a cohort


def _remove_triggers(client: Client, url: str) -> list[str]:
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "remove_from_cohort" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_the_learner_page_renders_with_the_remove_action_registered(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, _ = _membership(organisation)

    response = staff_client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_remove_fragment_from_the_learner_page_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client, _remove_url_from_learner(organisation, learner, cohort)
    )

    assert "They lose access to: Algebra." in text
    assert "Progress is kept." in text


@pytest.mark.django_db
def test_remove_fragment_says_the_learner_keeps_every_course_through_another_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    LearnerCourseRegistrationFactory(learner=learner, course=course)

    text = _get_fragment(
        staff_client, _remove_url_from_learner(organisation, learner, cohort)
    )

    assert "keep access to every course through another registration" in text


@pytest.mark.django_db
def test_remove_post_from_the_learner_page_deletes_the_membership(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 204
    assert not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_remove_post_sends_both_ids_with_the_learner_and_cohort_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    ids = {"ids": [str(learner.pk), str(cohort.pk)]}
    assert (trigger[LEARNER_CHANGED], trigger[COHORT_CHANGED]) == (ids, ids)
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_a_stale_remove_naming_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation, is_active=False)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert "to remove learners from it." in " ".join(response.content.decode().split())
    assert "is inactive" in response.content.decode()
    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_a_cohort_admins_learner_page_offers_remove_on_the_granted_cohort_only(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    other = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=other, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", granted)
    assign_role(grantor, educator, "cohort_viewer", other)

    triggers = _remove_triggers(
        logged_in_client(educator),
        _interface_url(organisation.slug, f"learners/{learner.pk}"),
    )

    assert {t.split("?cohort=")[1] for t in triggers} == {str(granted.pk)}


@pytest.mark.django_db
def test_a_forged_remove_on_an_unassigned_cohort_answers_403(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    other = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=other, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", granted)
    assign_role(grantor, educator, "cohort_viewer", other)

    response = _post(
        logged_in_client(educator),
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(other.pk)},
    )

    assert response.status_code == 403
    assert CohortMembership.objects.filter(learner=learner, cohort=other).exists()


# add to a cohort


@pytest.mark.django_db
def test_add_to_cohort_offers_only_active_cohorts_the_learner_is_not_in(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, member_of = _membership(organisation)
    open_cohort = cast(Cohort, CohortFactory(organisation=organisation))
    inactive = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    offered = _offered_options(staff_client, _add_to_cohort_url(organisation, learner))

    assert offered == {str(open_cohort.pk)}
    assert str(member_of.pk) not in offered
    assert str(inactive.pk) not in offered


@pytest.mark.django_db
def test_the_add_to_cohort_dialog_asks_before_a_cohort_is_chosen(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CohortFactory(organisation=organisation)

    document = _picker_dialog(staff_client, _add_to_cohort_url(organisation, learner))

    assert _dialog_title(document) == "Add Ada Lovelace to a cohort?"


@pytest.mark.django_db
def test_the_add_to_cohort_dialog_names_the_chosen_cohort_and_keeps_it_selected(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    cohort = CohortFactory(organisation=organisation, name="Cohort A")

    document = _picker_dialog(
        staff_client, _add_to_cohort_url(organisation, learner) + f"?cohort={cohort.pk}"
    )

    assert _dialog_title(document) == "Add Ada Lovelace to Cohort A?"
    (selected,) = document.cssselect("select[name='cohort'] option[selected]")
    assert selected.get("value") == str(cohort.pk)


@pytest.mark.django_db
def test_choosing_a_cohort_in_the_add_to_cohort_dialog_re_renders_it(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CohortFactory(organisation=organisation)
    url = _add_to_cohort_url(organisation, learner)

    document = _picker_dialog(staff_client, url)

    (select,) = document.cssselect("select[name='cohort']")
    assert select.get("hx-get") == url
    assert select.get("hx-trigger") == "change"
    assert select.get("hx-target") == "#app-modal-body"


@pytest.mark.django_db
def test_add_to_cohort_post_adds_the_membership(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 204
    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_add_to_cohort_post_sends_the_learner_and_cohort_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_add_to_cohort_post_naming_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_a_cohort_admins_add_to_cohort_offers_only_assigned_cohorts(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    spare = cast(Cohort, CohortFactory(organisation=organisation))
    unassigned = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, granted, spare)

    offered = _offered_options(
        logged_in_client(educator), _add_to_cohort_url(organisation, learner)
    )

    assert offered == {str(spare.pk)}
    assert str(unassigned.pk) not in offered


@pytest.mark.django_db
def test_a_forged_add_to_an_unassigned_cohort_answers_403_and_adds_nothing(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    unassigned = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, granted)

    response = _post(
        logged_in_client(educator),
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(unassigned.pk)},
    )

    assert response.status_code == 403
    assert not CohortMembership.objects.filter(
        learner=learner, cohort=unassigned
    ).exists()


# add a learner


def _list_triggers(client: Client, organisation: Organisation) -> list[str]:
    document = lxml.html.fromstring(
        client.get(_interface_url(organisation.slug, "learners")).content.decode()
    )
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "__actions/add_learner" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_the_learners_list_offers_add_learners_to_an_organisation_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)

    triggers = _list_triggers(logged_in_client(educator), organisation)

    assert len(triggers) == 1


@pytest.mark.django_db
def test_the_learners_list_offers_no_add_learners_to_a_cohort_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)

    triggers = _list_triggers(logged_in_client(educator), organisation)

    assert triggers == []


@pytest.mark.django_db
def test_add_learners_offers_only_active_cohorts_the_user_may_add_to(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    open_cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortFactory(organisation=organisation, is_active=False)
    CohortFactory(organisation=OrganisationFactory())

    offered = _offered_options(staff_client, _add_learners_list_url(organisation))

    assert offered == {str(open_cohort.pk)}


@pytest.mark.django_db
def test_add_learners_renders_a_preset_cohort_as_a_hidden_input(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = staff_client.get(
        _add_learners_list_url(organisation),
        {"cohort": str(cohort.pk)},
        HTTP_HX_REQUEST="true",
    )

    document = lxml.html.fromstring(response.content.decode())
    hidden = document.cssselect("input[type=hidden][name=cohort]")
    assert [field.get("value") for field in hidden] == [str(cohort.pk)]


@pytest.mark.django_db
def test_add_learner_post_without_an_email_answers_422(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(staff_client, _add_learners_list_url(organisation), {"email": ""})

    assert response.status_code == 422


@pytest.mark.django_db
def test_add_learner_post_with_an_invalid_address_answers_422_and_adds_nobody(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _post(
        staff_client, _add_learners_list_url(organisation), {"email": "bad-address"}
    )

    assert response.status_code == 422
    assert not Learner.objects.filter(organisation=organisation).exists()


@pytest.mark.django_db
def test_add_learner_post_answers_200_with_the_outcome_and_add_another(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com", "first_name": "Nia", "last_name": "Okoye"},
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    (result,) = document.cssselect("[data-testid='add-learner-result']")
    assert "new@example.com" in result.text_content()
    assert "Account created and setup email sent." in result.text_content()
    assert "Learner added" in document.cssselect("h2")[0].text_content()
    (again,) = [
        button
        for button in document.cssselect("button[hx-get]")
        if button.text_content().strip() == "Add another"
    ]
    assert again.get("hx-get") == _add_learners_list_url(organisation)
    assert Learner.objects.filter(
        organisation=organisation,
        user__email="new@example.com",
        user__first_name="Nia",
    ).exists()


@pytest.mark.django_db
def test_add_learner_post_for_an_existing_learner_is_titled_not_added(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation, user__email="here@example.com")

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "here@example.com"},
    )

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("h2")[0].text_content().strip() == "Not added"
    assert "Already a learner here." in response.content.decode()


@pytest.mark.django_db
def test_add_and_add_another_returns_an_empty_form_with_the_outcome_above_it(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Wave One"))

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com", "cohort": str(cohort.pk), "action": "add_another"},
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    (status,) = document.cssselect("[data-status-message]")
    assert " ".join(status.text_content().split()) == (
        "new@example.com: Account created and setup email sent. Added to the cohort."
    )
    (email,) = document.cssselect("input[name=email]")
    assert not email.get("value")
    assert document.cssselect("form[hx-post]")


@pytest.mark.django_db
def test_add_learner_post_sends_the_learner_changed_trigger(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com"},
    )

    assert LEARNER_CHANGED in json.loads(response["HX-Trigger"])


@pytest.mark.django_db
def test_add_learner_post_with_a_cohort_sends_the_cohort_changed_trigger_and_adds_them(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com", "cohort": str(cohort.pk)},
    )

    assert COHORT_CHANGED in json.loads(response["HX-Trigger"])
    assert cohort.cohortmembership_set.count() == 1


# resend the account setup email


@pytest.mark.django_db
def test_a_pending_learners_settings_tab_offers_resend_setup_email(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    triggers = _settings_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_a_learner_who_has_set_up_their_account_is_offered_no_resend(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    triggers = _settings_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) not in triggers


@pytest.mark.django_db
def test_resend_fragment_names_the_address(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    text = _get_fragment(staff_client, _resend_url(organisation, learner))

    assert "pending@example.com" in text


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_post_sends_one_message_and_answers_204(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (204, 1)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_post_fires_learner_changed_and_closes_the_modal(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    events = json.loads(response["HX-Trigger"])
    assert (events[LEARNER_CHANGED], "closeModal" in events) == (
        {"ids": [str(learner.pk)]},
        True,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_second_resend_answers_422_with_the_minutes_to_wait(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, learner))

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    minutes = config.SETUP_EMAIL_RESEND_SECONDS // 60
    assert (response.status_code, len(mail.outbox)) == (422, 1)
    assert f"{minutes} minutes" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_for_a_learner_who_has_set_up_answers_422_and_sends_nothing(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (422, 0)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_cohort_admins_forged_resend_answers_403_and_sends_nothing(
    mock_site_context: Site, logged_in_client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(logged_in_client(educator), _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (403, 0)


# move between cohorts


def _move_options(client: Client, url: str) -> set[str]:
    response = client.get(url, HTTP_HX_REQUEST="true")
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value") or ""
        for option in document.cssselect("select[name='destination'] option")
        if option.get("value")
    }


@pytest.mark.django_db
def test_move_fragment_offers_only_active_cohorts_the_learner_is_not_in(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    open_cohort = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)
    already_in = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=already_in, learner=learner)

    options = _move_options(
        staff_client, _move_url_from_learner(organisation, learner, source)
    )

    assert options == {str(open_cohort.pk)}


@pytest.mark.django_db
def test_move_fragment_names_courses_lost_gained_and_where_progress_continues(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    shared = CourseFactory(title="Algebra")
    lost = CourseFactory(title="Botany")
    gained = CourseFactory(title="Chemistry")
    source_registration = CohortCourseRegistrationFactory(cohort=source, course=shared)
    CohortCourseRegistrationFactory(cohort=source, course=lost)
    CohortCourseRegistrationFactory(cohort=destination, course=shared)
    CohortCourseRegistrationFactory(cohort=destination, course=gained)
    CourseProgressFactory(
        learner=learner,
        course=shared,
        learner_registration=None,
        cohort_registration=source_registration,
        progress_percentage=40,
    )

    text = _get_fragment(
        staff_client,
        _move_url_from_learner(organisation, learner, source, destination),
    )

    assert "They lose access to: Botany." in text
    assert "They gain access to: Chemistry." in text
    assert "Algebra: continues at 40%" in text


@pytest.mark.django_db
def test_move_post_moves_the_membership_and_answers_204_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert set(trigger[COHORT_CHANGED]["ids"]) == {
        str(learner.pk),
        str(source.pk),
        str(destination.pk),
    }
    assert str(learner.pk) in trigger[LEARNER_CHANGED]["ids"]
    assert list(CohortMembership.objects.filter(learner=learner)) == [
        CohortMembership.objects.get(learner=learner, cohort=destination)
    ]


@pytest.mark.django_db
def test_move_post_to_a_cohort_outside_the_users_grants_answers_403(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    unassigned = CohortFactory(organisation=organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", source)

    response = _post(
        logged_in_client(educator),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(unassigned.pk)},
    )

    assert response.status_code == 403
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_a_cohort_admin_can_move_between_two_assigned_cohorts(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", source)
    assign_role(grantor, educator, "cohort_admin", destination)

    response = _post(
        logged_in_client(educator),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_move_post_naming_an_inactive_source_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation, is_active=False)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 422
    assert "to move learners into or out of it." in " ".join(
        response.content.decode().split()
    )
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_move_post_naming_an_inactive_destination_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 422
    assert "to move learners into or out of it." in " ".join(
        response.content.decode().split()
    )
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_move_422_rerender_offers_the_same_destinations_as_the_fresh_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    open_cohort = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": ""},
    )

    document = lxml.html.fromstring(response.content.decode())
    options = {
        option.get("value")
        for option in document.cssselect("select[name='destination'] option")
        if option.get("value")
    }
    assert (response.status_code, options) == (422, {str(open_cohort.pk)})


@pytest.mark.django_db
def test_stale_move_dialog_for_a_departed_member_gives_the_reason_and_no_form(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    CohortMembership.objects.filter(learner=learner, cohort=source).delete()
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _move_url_from_learner(organisation, learner, source), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert (
        response.status_code,
        len(document.cssselect("form")),
        "is no longer a member of" in response.content.decode(),
    ) == (422, 0, True)


@pytest.mark.django_db
def test_the_move_refusal_for_a_departed_member_is_a_message_dialog_with_close(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    name = learner.user.display_name
    CohortMembership.objects.filter(learner=learner, cohort=source).delete()
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _move_url_from_learner(organisation, learner, source), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 422
    assert document.cssselect("#app-modal-title")[0].text_content().strip() == (
        f"{name} is no longer in {source}"
    )
    assert f"{name} is no longer a member of {source}" in " ".join(
        document.text_content().split()
    )
    assert [b.text_content().strip() for b in document.cssselect("footer button")] == [
        "Close"
    ]


@pytest.mark.django_db
def test_the_disabled_move_states_its_reason_and_names_it_with_aria_describedby(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _move_url_from_learner(organisation, learner, source), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    (move,) = document.cssselect("form button[type='submit']")
    (reason,) = document.cssselect(
        "form > div[data-modal-scroll] #move-disabled-reason"
    )
    assert not document.cssselect("footer #move-disabled-reason")
    assert move.get("disabled") is not None
    assert move.get("aria-describedby") == "move-disabled-reason"
    assert reason.text_content().strip() == "Choose a cohort to move them to."


@pytest.mark.django_db
def test_a_member_leaving_mid_move_answers_422_with_the_reason(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    def leave_then_refuse(*args: object, **kwargs: object) -> str:
        CohortMembership.objects.filter(learner=learner, cohort=source).delete()
        raise ValueError("The learner is not a member of the source cohort.")

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.learner.actions.move_between_cohorts",
        leave_then_refuse,
    )

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert (
        response.status_code,
        "is no longer a member of" in response.content.decode(),
    ) == (422, True)


@pytest.mark.django_db
def test_stale_move_post_for_a_departed_member_answers_422_with_the_reason(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    CohortMembership.objects.filter(learner=learner, cohort=source).delete()

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert (
        response.status_code,
        "is no longer a member of" in response.content.decode(),
        CohortMembership.objects.filter(learner=learner).exists(),
    ) == (422, True, False)


# register and deactivate a learner registration individually


@pytest.mark.django_db
def test_register_fragment_offers_the_registerable_courses(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    open_course = CourseFactory()
    coming_soon = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    held = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    offered = _offered_options(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert offered == {str(open_course.pk)}
    assert str(coming_soon.pk) not in offered
    assert str(held.pk) not in offered


def _ada(organisation: Organisation) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user__first_name="Ada",
            user__last_name="Lovelace",
        ),
    )


@pytest.mark.django_db
def test_the_register_dialog_asks_before_a_course_is_chosen(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CourseFactory()

    document = _picker_dialog(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert _dialog_title(document) == "Register Ada Lovelace for a course?"


@pytest.mark.django_db
def test_the_register_dialog_names_the_chosen_course_and_keeps_it_selected(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    course = CourseFactory(title="Course Other")

    document = _picker_dialog(
        staff_client,
        _learner_register_url(organisation, learner) + f"?course={course.pk}",
    )

    assert _dialog_title(document) == "Register Ada Lovelace for Course Other?"
    (selected,) = document.cssselect("select[name='course'] option[selected]")
    assert selected.get("value") == str(course.pk)


@pytest.mark.django_db
def test_choosing_a_course_in_the_register_dialog_re_renders_it(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CourseFactory()
    url = _learner_register_url(organisation, learner)

    document = _picker_dialog(staff_client, url)

    (select,) = document.cssselect("select[name='course']")
    assert select.get("hx-get") == url
    assert select.get("hx-trigger") == "change"
    assert select.get("hx-target") == "#app-modal-body"


@pytest.mark.django_db
def test_a_course_the_register_dialog_does_not_offer_leaves_the_question_open(
    staff_client: Client,
):
    """A stale choice on the refresh is not a submission, so the dialog
    neither names it nor shows an error."""
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CourseFactory()
    held = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    document = _picker_dialog(
        staff_client,
        _learner_register_url(organisation, learner) + f"?course={held.pk}",
    )

    assert _dialog_title(document) == "Register Ada Lovelace for a course?"
    assert document.cssselect("[role='alert']") == []
    assert document.cssselect("option[selected]:not([value=''])") == []


@pytest.mark.django_db
def test_register_post_creates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory()

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, is_active=True
    ).exists()
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_register_post_naming_a_coming_soon_course_answers_422_with_no_row(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert not LearnerCourseRegistration.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_unregister_fragment_names_the_cohort_keeping_access(staff_client: Client):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation, name="Year 10")
    course = CourseFactory(title="Algebra")
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "They keep access through Year 10." in text
    assert "Progress is kept." in text


@pytest.mark.django_db
def test_unregister_fragment_does_not_name_a_cohort_the_educator_cannot_see(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, seen = _membership(organisation, name="Year 10")
    hidden = cast(Cohort, CohortFactory(organisation=organisation, name="Staff Room"))
    CohortMembershipFactory(cohort=hidden, learner=learner)
    course = CourseFactory(title="Algebra")
    CohortCourseRegistrationFactory(cohort=hidden, course=course)
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)
    educator = _cohort_admin_on(organisation, seen)

    text = _get_fragment(
        logged_in_client(educator),
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "Staff Room" not in text
    assert "They keep access through another cohort." in text


@pytest.mark.django_db
def test_unregister_fragment_says_the_learner_loses_access_without_a_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "They lose access to Algebra." in text


@pytest.mark.django_db
def test_unregister_fragment_names_self_registration_only_on_the_default_organisation(
    staff_client: Client, mock_site_context: Site
):
    default = get_default_organisation(mock_site_context)
    learner = cast(Learner, LearnerFactory(organisation=default))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(default, learner) + f"?registration={registration.pk}",
    )

    assert "self-register" in text


@pytest.mark.django_db
def test_unregister_fragment_omits_self_registration_on_another_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory(is_default=False)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "self-register" not in text


@pytest.mark.django_db
def test_unregister_post_deactivates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    response = _post(
        staff_client,
        _learner_unregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, registration.is_active) == (204, False)
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_a_cohort_admin_can_register_a_learner_in_an_assigned_cohort(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    course = CourseFactory()
    educator = _cohort_admin_on(organisation, cohort)

    response = _post(
        logged_in_client(educator),
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 204
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course
    ).exists()


@pytest.mark.django_db
def test_a_cohort_admins_forged_register_on_a_learner_outside_their_cohorts_is_refused(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    _, cohort = _membership(organisation)
    outsider = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory()
    educator = _cohort_admin_on(organisation, cohort)

    response = _post(
        logged_in_client(educator),
        _learner_register_url(organisation, outsider),
        {"course": str(course.pk)},
    )

    assert response.status_code == 404
    assert not LearnerCourseRegistration.objects.filter(learner=outsider).exists()


# re-register a learner individually


def _reregister_triggers(client: Client, url: str) -> list[str]:
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "reactivate_registration" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_reregister_is_offered_on_an_inactive_individual_row_only(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    inactive = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, is_active=True)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    triggers = _reregister_triggers(
        staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert [t.split("?registration=")[1] for t in triggers] == [str(inactive.pk)]


@pytest.mark.django_db
def test_reregister_fragment_names_the_learner_and_the_course(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra"), is_active=False
    )

    text = _get_fragment(
        staff_client,
        _learner_reregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert f"Reactivate {learner.user.display_name}'s registration for Algebra?" in text


@pytest.mark.django_db
def test_reregister_post_reactivates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, registration.is_active) == (204, True)
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_reregister_post_on_a_course_that_gained_another_organisation_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    course = registration.course
    course.audience = CourseAudience.ORGANISATION_LEARNERS
    course.save()
    course.organisations.add(OrganisationFactory())

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (422, False)
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("row", "reactivated"),
    [("no_owner", True), ("owned", True), ("shared", True), ("held", False)],
)
def test_reregister_post_reactivates_only_a_course_available_to_the_organisation(
    staff_client: Client, row: str, reactivated: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=courses[row], is_active=False
    )

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (
        204 if reactivated else 422,
        reactivated,
    )
    assert (COURSE_NOT_OPEN_MESSAGE in response.content.decode()) is not reactivated


@pytest.mark.django_db
def test_reregister_post_naming_an_active_registration_answers_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=True)

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_viewers_forged_reregister_answers_403(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    response = _post(
        logged_in_client(viewer),
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (403, False)


# empty pickers


@pytest.mark.django_db
def test_an_empty_add_to_cohort_picker_says_the_learner_is_in_every_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, _ = _membership(organisation)
    learner.user.first_name, learner.user.last_name = "Ada", "Lovelace"
    learner.user.save()

    text = _empty_picker_text(staff_client, _add_to_cohort_url(organisation, learner))

    assert (
        "Ada Lovelace is already in every active cohort you can add learners to."
        in text
    )


@pytest.mark.django_db
def test_a_stale_add_to_cohort_post_naming_a_cohort_they_are_in_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner).count() == 1


@pytest.mark.django_db
def test_an_empty_register_picker_says_there_is_no_course_to_register_for(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user__first_name="",
            user__last_name="",
            user__email="pick@example.com",
        ),
    )
    LearnerCourseRegistrationFactory(learner=learner, is_active=True)

    text = _empty_picker_text(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert "There is no course pick@example.com can be registered for right now." in (
        text
    )


@pytest.mark.django_db
def test_a_stale_register_post_naming_a_held_course_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert LearnerCourseRegistration.objects.filter(learner=learner).count() == 1


@pytest.mark.django_db
def test_an_empty_move_picker_says_there_is_no_other_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    learner.user.first_name, learner.user.last_name = "Ada", "Lovelace"
    learner.user.save()
    CohortFactory(organisation=organisation, is_active=False)

    text = _empty_picker_text(
        staff_client, _move_url_from_learner(organisation, learner, source)
    )

    assert "There is no other active cohort you can move Ada Lovelace to." in text


@pytest.mark.django_db
def test_a_picker_with_something_to_offer_keeps_its_submit_button(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _add_to_cohort_url(organisation, learner), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("select[name='cohort']")
    assert document.cssselect("button[type='submit']")


@pytest.mark.django_db
def test_remove_fragment_from_the_cohort_page_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client, _remove_url_from_cohort(organisation, cohort, learner)
    )

    assert "They lose access to: Algebra." in text


@pytest.mark.django_db
def test_remove_post_from_the_cohort_page_deletes_the_membership(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_cohort(organisation, cohort),
        {"learner": str(learner.pk)},
    )

    assert response.status_code == 204
    assert not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_move_post_from_the_cohort_page_moves_the_membership(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_cohort(organisation, source, learner),
        {"learner": str(learner.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 204
    assert CohortMembership.objects.filter(learner=learner, cohort=destination).exists()


@pytest.mark.django_db
def test_a_stale_move_post_with_no_other_cohort_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)

    response = _post(
        staff_client,
        _move_url_from_cohort(organisation, source, learner),
        {"learner": str(learner.pk), "destination": str(source.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_deactivating_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"learners/{learner.pk}/__actions/deactivate",
            },
        ),
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("learner.deactivated", actor)


@pytest.mark.django_db
def test_adding_a_learner_to_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_membership.added", actor)


@pytest.mark.django_db
def test_removing_a_learner_from_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_membership.removed", actor)


@pytest.mark.django_db
def test_moving_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = cast(Cohort, CohortFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_membership.moved", actor)


@pytest.mark.django_db
def test_adding_learners_by_email_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _add_learners_list_url(organisation),
        {"email": "new@example.com"},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("learner.added", actor)


@pytest.mark.django_db
def test_registering_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _learner_register_url(organisation, learner),
        {"course": str(CourseFactory().pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("registration.added", actor)


@pytest.mark.django_db
def test_reregistering_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("registration.reactivated", actor)


@pytest.mark.django_db
def test_unregistering_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _learner_unregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("registration.deactivated", actor)


@pytest.mark.django_db
def test_renaming_a_learner_writes_an_entry_with_the_old_and_new_name(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    assert_entry(
        action="learner.renamed",
        actor=actor,
        target=learner,
        target_label="Grace Hopper",
        organisation=organisation,
        details={"old": "Ada Lovelace", "new": "Grace Hopper"},
    )


@pytest.mark.django_db
def test_saving_a_learner_under_their_own_name_writes_nothing(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)

    response = _post(
        staff_client,
        _edit_name_url(organisation, learner),
        {"first_name": "Ada", "last_name": "Lovelace"},
    )

    assert response.status_code == 204
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resending_a_setup_email_writes_an_entry(
    mock_site_context, logged_in_client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    actor = UserFactory(superuser=True)

    with django_capture_on_commit_callbacks(execute=True):
        _post(logged_in_client(actor), _resend_url(organisation, learner))

    assert_entry(
        action="learner.setup_email_resent",
        actor=actor,
        target=learner,
        target_label=learner.user.display_name,
        organisation=organisation,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_refused_resend_writes_nothing(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    set_up = LearnerFactory(organisation=organisation)
    recent = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, recent))
    entries_before = AuditLogEntry.unscoped.count()

    with django_capture_on_commit_callbacks(execute=True):
        too_soon = _post(staff_client, _resend_url(organisation, recent))
        already = _post(staff_client, _resend_url(organisation, set_up))

    assert (too_soon.status_code, already.status_code) == (422, 422)
    assert AuditLogEntry.unscoped.count() == entries_before


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_failed_entry_sends_no_email_and_leaves_the_resend_open(
    staff_client: Client, django_capture_on_commit_callbacks, monkeypatch
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    url = _resend_url(organisation, learner)

    def fail(*args: object, **kwargs: object) -> None:
        raise _RolledBackError

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.learner.actions.record_learner_entry",
        fail,
    )
    with (
        pytest.raises(_RolledBackError),
        django_capture_on_commit_callbacks(execute=True),
    ):
        _post(staff_client, url)
    monkeypatch.undo()
    assert mail.outbox == []

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, url)

    assert response.status_code == 204
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_posting_to_the_import_link_is_not_allowed(mock_site_context, logged_in_client):
    """The import action is a link to the import page; it has no submit."""
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)

    response = _post(
        logged_in_client(educator),
        _interface_url(organisation.slug, "learners/__actions/import_learners"),
    )

    assert response.status_code == 405


def _superuser_get_ctx(
    organisation: Organisation, instance: Cohort | None, data: dict[str, str]
) -> PanelContext:
    request = RequestFactory().get("/", data)
    request.user = UserFactory(superuser=True)
    request.organisation = organisation
    return PanelContext(
        request=request, instance=instance, base_url="/", name="", config=CohortConfig
    )


@pytest.mark.django_db
def test_the_add_learner_dialog_reads_its_preset_cohort_once(
    organisation: Organisation, django_assert_max_num_queries
):
    cohort = _cohort(organisation)
    action = AddLearnerAction()
    ctx = _superuser_get_ctx(organisation, None, {"cohort": str(cohort.pk)})
    action._preset_cohort(ctx)

    with django_assert_max_num_queries(0):
        preset = action._preset_cohort(ctx)

    assert preset == cohort


@pytest.mark.django_db
def test_a_membership_dialog_on_a_cohort_page_reads_its_learner_once(
    organisation: Organisation, django_assert_max_num_queries
):
    cohort = _cohort(organisation)
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    action = RemoveFromCohortAction()
    ctx = _superuser_get_ctx(organisation, cohort, {"learner": str(learner.pk)})
    action._pair(ctx)

    with django_assert_max_num_queries(0):
        pair = action._pair(ctx)

    assert pair == (learner, cohort)


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "registered"), REGISTERABLE_ROWS)
def test_registering_a_learner_for_a_course_works_only_when_it_is_registerable(
    staff_client: Client, row: str, registered: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    learner = cast(Learner, LearnerFactory(organisation=organisation))

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(courses[row].pk)},
    )

    assert (
        response.status_code,
        LearnerCourseRegistration.objects.filter(
            learner=learner, course=courses[row]
        ).exists(),
    ) == ((204 if registered else 422), registered)


@pytest.mark.django_db
def test_the_add_to_cohort_picker_on_a_learners_page_offers_no_inactive_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = CohortFactory(organisation=organisation, is_active=False)
    learner = LearnerFactory(organisation=organisation)

    response = staff_client.get(
        _interface_url(
            organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
        ),
        HTTP_HX_REQUEST="true",
    )

    assert str(inactive.pk) not in response.content.decode()


@pytest.mark.django_db
def test_the_add_to_cohort_picker_offers_no_inactive_cohort_after_a_submit_with_no_choice(
    staff_client: Client,
):
    """A submit with no cohort chosen used to re-render the select with the
    organisation's inactive cohorts, which the first render never offered."""
    organisation = OrganisationFactory()
    inactive = CohortFactory(organisation=organisation, is_active=False)
    learner = LearnerFactory(organisation=organisation)

    response = staff_client.post(
        _interface_url(
            organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
        ),
        {"cohort": ""},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert str(inactive.pk) not in response.content.decode()


@pytest.mark.django_db
def test_a_move_shows_on_both_cohorts_and_the_learner_history_tabs(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    source = CohortFactory(organisation=organisation, name="Alpha")
    destination = CohortFactory(organisation=organisation, name="Beta")
    CohortMembershipFactory(learner=learner, cohort=source)
    move_between_cohorts(learner, source, destination, actor=UserFactory())

    shown = [
        _history_rows(_cohort_history_tab(staff_client, source)),
        _history_rows(_cohort_history_tab(staff_client, destination)),
        _history_rows(_learner_page(staff_client, learner, "history")),
    ]

    assert [[row[2] for row in rows] for rows in shown] == [
        ["Learner moved between cohorts From Alpha to Beta"]
    ] * 3
