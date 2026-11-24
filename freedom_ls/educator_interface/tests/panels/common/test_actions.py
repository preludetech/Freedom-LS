"""The behaviour every educator action shares: the reason field, the
picker 422s, the single-row dialogs, refusals and rollback."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest

from django.db import transaction
from django.test import Client

from freedom_ls.accounts.config import config
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.tests.helpers import (
    _add_to_cohort_url,
    _assert_message_dialog,
    _bulk_learner,
    _bulk_text,
    _cohort,
    _cohort_url,
    _edit_name_url,
    _interface_url,
    _learner_reregister_url,
    _learner_state_url,
    _learner_unregister_url,
    _membership,
    _move_url_from_cohort,
    _move_url_from_learner,
    _named_learner,
    _pending_learner,
    _post,
    _registered_cohort,
    _remove_role_url,
    _remove_url_from_cohort,
    _remove_url_from_learner,
    _resend_url,
    _RolledBackError,
    _staff_member_holding,
    _state_url,
    _unregister_post_url,
    _unregister_url,
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
    Learner,
    StaffMember,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


def _rename_cohort_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Before"))
    return _cohort_url(organisation, cohort, "/__actions/edit"), {"name": "After"}


def _rename_learner_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    return _edit_name_url(organisation, _named_learner(organisation)), {
        "first_name": "Grace",
        "last_name": "Hopper",
    }


def _deactivate_cohort_request(
    organisation: Organisation,
) -> tuple[str, dict[str, str]]:
    cohort = CohortFactory(organisation=organisation)
    return _cohort_url(organisation, cohort, "/__actions/deactivate"), {}


def _resend_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    return _resend_url(organisation, _pending_learner(organisation)), {}


def _create_cohort_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    return _interface_url(organisation.slug, "cohorts/__actions/create_cohort"), {
        "name": "Fresh"
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
@pytest.mark.parametrize(
    "build_request",
    [
        _create_cohort_request,
        _rename_cohort_request,
        _rename_learner_request,
        _deactivate_cohort_request,
        _resend_request,
    ],
)
def test_a_failure_after_the_write_leaves_no_entry(
    staff_client: Client,
    build_request: Callable[[Organisation], tuple[str, dict[str, str]]],
) -> None:
    organisation = OrganisationFactory()
    url, data = build_request(organisation)

    def post_then_fail() -> None:
        with transaction.atomic():
            response = _post(staff_client, url, data)
            assert response.status_code in (204, 200)
            assert AuditLogEntry.unscoped.exists()
            raise _RolledBackError

    with pytest.raises(_RolledBackError):
        post_then_fail()

    assert not AuditLogEntry.unscoped.exists()


_DialogRequest = tuple[str, dict[str, str]]


def _reason_deactivate_cohort(organisation: Organisation) -> _DialogRequest:
    cohort = CohortFactory(organisation=organisation)
    return _cohort_url(organisation, cohort, "/__actions/deactivate"), {}


def _reason_deactivate_learner(organisation: Organisation) -> _DialogRequest:
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    return _learner_state_url(organisation, learner, "deactivate"), {}


def _reason_remove_from_cohort(organisation: Organisation) -> _DialogRequest:
    learner, cohort = _membership(organisation)
    return _remove_url_from_learner(organisation, learner), {"cohort": str(cohort.pk)}


def _reason_unregister_cohort(organisation: Organisation) -> _DialogRequest:
    cohort, registration = _registered_cohort(organisation)
    return _unregister_post_url(organisation, cohort), {
        "registration": str(registration.pk)
    }


def _reason_unregister_learner(organisation: Organisation) -> _DialogRequest:
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=True)
    return _learner_unregister_url(organisation, learner), {
        "registration": str(registration.pk)
    }


def _reason_remove_role(organisation: Organisation) -> _DialogRequest:
    user = _staff_member_holding("cohort_admin", _cohort(organisation))
    return _remove_role_url(organisation), {
        "user": str(user.pk),
        "role": "cohort_admin",
    }


def _reason_suspend_member(organisation: Organisation) -> _DialogRequest:
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    return _state_url(organisation, "deactivate"), {"user": str(user.pk)}


REASON_DIALOGS = [
    _reason_deactivate_cohort,
    _reason_deactivate_learner,
    _reason_remove_from_cohort,
    _reason_unregister_cohort,
    _reason_unregister_learner,
    _reason_remove_role,
    _reason_suspend_member,
]


def _reason_post(
    client: Client, request: _DialogRequest, reason: str | None
) -> tuple[_MonkeyPatchedWSGIResponse, list[AuditLogEntry]]:
    """POST the dialog `request` and return the response with the entries it
    wrote, leaving out those that setting the scene wrote."""
    before = set(AuditLogEntry.unscoped.values_list("pk", flat=True))
    url, params = request
    data = params if reason is None else {**params, "reason": reason}
    response = _post(client, url, data)
    written = list(AuditLogEntry.unscoped.exclude(pk__in=before))
    return response, written


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_confirm_dialog_renders_the_optional_reason_field(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()
    url, params = build_url(organisation)

    response = staff_client.get(url, params, HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content.decode())
    (field,) = document.cssselect("input[name='reason']")
    assert field.get("maxlength") == "500"
    label = document.cssselect(f"label[for='{field.get('id')}']")[0]
    assert label.text_content().strip() == "Reason (optional):"
    assert document.cssselect("form input[name='reason']")


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_reason_posted_with_a_confirm_dialog_reaches_the_entry(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()

    response, written = _reason_post(
        staff_client, build_url(organisation), "  Left the programme  "
    )

    assert response.status_code in (200, 204)
    assert [entry.reason for entry in written] == ["Left the programme"]


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_confirm_dialog_allows_an_empty_reason(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()

    response, written = _reason_post(staff_client, build_url(organisation), None)

    assert response.status_code in (200, 204)
    assert [entry.reason for entry in written] == [""]


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_reason_over_500_characters_answers_422_and_changes_nothing(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()

    response, written = _reason_post(staff_client, build_url(organisation), "x" * 501)

    assert response.status_code == 422
    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='reason']")
    assert "at most 500 characters" in document.text_content()
    assert written == []


@pytest.mark.django_db
def test_a_stale_cohort_in_the_add_to_cohort_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    stale = str(uuid.uuid4())

    response = _post(
        staff_client, _add_to_cohort_url(organisation, learner), {"cohort": stale}
    )

    assert response.status_code == 422
    assert "Choose a cohort from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_a_stale_destination_in_the_move_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    CohortFactory(organisation=organisation)
    stale = str(uuid.uuid4())

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": stale},
    )

    assert response.status_code == 422
    assert "Choose a cohort from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


def _single_row_dialog_url(name: str, organisation: Organisation) -> str:
    """The URL of the confirmation dialog `name`, over records made for it."""
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    if name == "deactivate_cohort":
        return _cohort_url(organisation, cohort, "/__actions/deactivate")
    if name == "reactivate_cohort":
        return _cohort_url(organisation, cohort, "/__actions/reactivate")
    if name == "delete_cohort":
        empty = cast(Cohort, CohortFactory(organisation=organisation))
        return _cohort_url(
            organisation, empty, "/__tabs/settings/__panels/status/__actions/delete"
        )
    if name == "deactivate_learner":
        return _learner_state_url(organisation, learner, "deactivate")
    if name == "reactivate_learner":
        return _learner_state_url(organisation, learner, "reactivate")
    if name == "resend_setup_email":
        return _resend_url(organisation, _pending_learner(organisation))
    if name == "remove_from_cohort":
        return _remove_url_from_cohort(organisation, cohort, learner)
    if name == "move":
        destination = CohortFactory(organisation=organisation)
        return (
            _move_url_from_cohort(organisation, cohort, learner)
            + f"&destination={destination.pk}"
        )
    if name == "deactivate_registration":
        LearnerCourseRegistrationFactory(learner=learner, is_active=True)
        return _learner_unregister_url(organisation, learner) + (
            f"?registration={learner.learnercourseregistration_set.get().pk}"
        )
    if name == "reactivate_registration":
        registration = LearnerCourseRegistrationFactory(
            learner=learner, is_active=False
        )
        return (
            _learner_reregister_url(organisation, learner)
            + f"?registration={registration.pk}"
        )
    if name == "deactivate_cohort_registration":
        registration = CohortCourseRegistrationFactory(cohort=cohort)
        return _unregister_url(organisation, cohort, registration)
    member = _staff_member_holding("cohort_viewer", cohort)
    if name == "deactivate_member":
        return f"{_state_url(organisation, 'deactivate')}?user={member.pk}"
    if name == "reactivate_member":
        StaffMember.objects.filter(user=member).update(is_active=False)
        return f"{_state_url(organisation, 'reactivate')}?user={member.pk}"
    return f"{_remove_role_url(organisation)}?user={member.pk}&role=cohort_viewer"


_SINGLE_ROW_DIALOG_WEIGHTS: dict[str, tuple[str, str]] = {
    "deactivate_cohort": ("primary", "Deactivating…"),
    "reactivate_cohort": ("primary", "Reactivating…"),
    "delete_cohort": ("error", "Deleting…"),
    "deactivate_learner": ("primary", "Deactivating…"),
    "reactivate_learner": ("primary", "Reactivating…"),
    "resend_setup_email": ("primary", "Sending…"),
    "remove_from_cohort": ("error", "Removing…"),
    "move": ("primary", "Moving…"),
    "deactivate_registration": ("primary", "Deactivating…"),
    "reactivate_registration": ("primary", "Reactivating…"),
    "deactivate_cohort_registration": ("primary", "Deactivating…"),
    "deactivate_member": ("primary", "Deactivating…"),
    "reactivate_member": ("primary", "Reactivating…"),
    "deactivate_role": ("primary", "Deactivating…"),
}


def _single_row_dialog(
    client: Client, name: str, organisation: Organisation
) -> lxml.html.HtmlElement:
    url = _single_row_dialog_url(name, organisation)
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(_SINGLE_ROW_DIALOG_WEIGHTS))
def test_single_row_dialog_title_is_a_question(
    name: str, staff_client: Client, organisation: Organisation
):
    """A confirmation asks; the move dialog, which is a form, names the
    action and the learner and states the current cohort in its body."""
    document = _single_row_dialog(staff_client, name, organisation)

    (title,) = document.cssselect("#app-modal-title")
    text = title.text_content().strip()
    if name == "move":
        assert text.startswith("Move ")
        assert "?" not in text
        assert "Current cohort:" in document.text_content()
    else:
        assert text.endswith("?")


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(_SINGLE_ROW_DIALOG_WEIGHTS))
def test_single_row_dialog_focuses_cancel_or_the_move_destination(
    name: str, staff_client: Client, organisation: Organisation
):
    document = _single_row_dialog(staff_client, name, organisation)

    focused = [
        element.tag if element.tag == "select" else element.text_content().strip()
        for element in document.cssselect("[autofocus]")
    ]
    assert focused == (["select"] if name == "move" else ["Cancel"])


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(_SINGLE_ROW_DIALOG_WEIGHTS))
def test_single_row_dialog_confirm_button_weight_and_loading_text(
    name: str, staff_client: Client, organisation: Organisation
):
    document = _single_row_dialog(staff_client, name, organisation)

    (confirm,) = document.cssselect("button[type=submit]")
    variant, loading_text = _SINGLE_ROW_DIALOG_WEIGHTS[name]
    assert confirm.get("data-variant") == variant
    assert loading_text in confirm.text_content()


@pytest.mark.django_db
def test_a_row_action_on_a_learner_from_another_organisation_answers_the_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    elsewhere = _bulk_learner(organisation=OrganisationFactory())

    response = staff_client.get(
        _learner_state_url(organisation, elsewhere, "deactivate"),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
def test_a_row_action_on_an_unknown_learner_answers_the_dialog(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.get(
        _interface_url(
            organisation.slug, f"learners/{uuid.uuid4()}/__actions/deactivate"
        ),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
def test_a_bulk_action_that_does_not_exist_answers_the_dialog(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.post(
        _interface_url(organisation.slug, "learners/__actions/no_such_action"),
        {"keys": [str(uuid.uuid4())]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
def test_an_already_changed_learner_refusal_is_a_message_dialog(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    _assert_message_dialog(
        response,
        f"{learner.user.display_name} was already changed",
        "Nothing changed. Someone else may have already used Reactivate on this "
        "learner.",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_recently_sent_setup_email_refusal_is_a_message_dialog(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, learner))

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    minutes = config.SETUP_EMAIL_RESEND_SECONDS // 60
    _assert_message_dialog(
        response,
        "Setup email sent recently",
        f"{learner.user.display_name} was sent a setup email recently. "
        f"Try again in {minutes} minutes.",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_an_already_set_up_account_refusal_is_a_message_dialog(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    name = learner.user.display_name
    _assert_message_dialog(
        response,
        f"{name} has already set up their account",
        f"Nothing was sent. {name} has signed in or set a password since this "
        "page loaded.",
    )
