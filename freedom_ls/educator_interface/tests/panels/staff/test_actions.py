"""Tests for the staff actions."""

from __future__ import annotations

import json
from typing import cast

import lxml.html
import pytest
from allauth.account.models import EmailAddress
from panel_framework.context import PanelContext

from django.core import mail
from django.test import Client, RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.educator_interface.events import (
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.panels.cohort.config import CohortConfig
from freedom_ls.educator_interface.panels.staff import actions as actions_module
from freedom_ls.educator_interface.panels.staff.actions import (
    REFUSAL_MESSAGES,
    AddStaffMemberToCohortAction,
    grantable_roles_for,
)
from freedom_ls.educator_interface.staff import current_role_entries
from freedom_ls.educator_interface.tests.helpers import (
    _assert_message_dialog,
    _cohort,
    _cohort_url,
    _interface_url,
    _post,
    _remove_role_url,
    _staff_member_holding,
    _state_url,
    _text,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerFactory,
    StaffMemberFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    StaffMember,
)
from freedom_ls.learner_management.role_assignment import (
    GrantableRole,
    assign_role,
    deactivate_role,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.tests.factories import SiteFactory


@pytest.mark.django_db
def test_grantable_roles_are_cached_on_the_request(
    panel_request, django_assert_max_num_queries
) -> None:
    request = panel_request()
    request.user = UserFactory(superuser=True)
    grantable_roles_for(request)

    with django_assert_max_num_queries(0):
        grantable_roles_for(request)


# add member


def _add_staff_member_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "staff/__actions/add_staff_member")


def _holder_client(
    logged_in_client, target: Organisation | Cohort, role: str = "organisation_admin"
) -> tuple[Client, User]:
    user = cast(User, UserFactory(staff=True))
    assign_role(UserFactory(superuser=True), user, role, target)
    return logged_in_client(user), user


def _lookup(client: Client, organisation: Organisation, email: str):
    return _post(
        client, _add_staff_member_url(organisation), {"step": "lookup", "email": email}
    )


def _submit_role(
    client: Client,
    organisation: Organisation,
    email: str,
    role: str,
    **extra: str,
):
    return _post(
        client,
        _add_staff_member_url(organisation),
        {"step": "submit", "email": email, "role": role, **extra},
    )


def _confirm(
    client: Client, organisation: Organisation, email: str, role: str, **extra: str
):
    return _submit_role(client, organisation, email, role, confirmed="1", **extra)


@pytest.fixture
def admin_client(logged_in_client, organisation: Organisation) -> Client:
    CohortFactory(organisation=organisation)
    return _holder_client(logged_in_client, organisation)[0]


@pytest.mark.django_db
def test_the_email_step_asks_for_an_address(admin_client, organisation):
    response = admin_client.get(
        _add_staff_member_url(organisation), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='email']")


@pytest.mark.django_db
def test_the_lookup_shows_an_existing_accounts_name_and_email(
    admin_client, organisation
):
    UserFactory(first_name="Ada", last_name="Lovelace", email="ada@example.com")

    text = _text(_lookup(admin_client, organisation, "ada@example.com"))

    assert "Existing account: Ada Lovelace, ada@example.com" in text


@pytest.mark.django_db
def test_the_lookup_shows_the_email_once_for_an_account_with_no_name(
    admin_client, organisation
):
    """An account without a name used to show its email twice."""
    UserFactory(first_name="", last_name="", email="nameless@example.com")

    text = _text(_lookup(admin_client, organisation, "nameless@example.com"))

    assert "Existing account: nameless@example.com" in text
    assert text.count("nameless@example.com") == 1


@pytest.mark.django_db
def test_the_lookup_creates_no_user(admin_client, organisation):
    UserFactory(email="ada@example.com")
    before = User._base_manager.count()

    _lookup(admin_client, organisation, "ada@example.com")
    _lookup(admin_client, organisation, "nobody@example.com")

    assert User._base_manager.count() == before


@pytest.mark.django_db
def test_the_lookup_of_another_sites_address_shows_the_message_and_no_name(
    admin_client, organisation
):
    User._base_manager.create(
        site=SiteFactory(), email="away@example.com", first_name="Awaynamed"
    )

    response = _lookup(admin_client, organisation, "away@example.com")

    text = _text(response)
    assert response.status_code == 422
    assert "belongs to an account on another site" in text
    assert "Awaynamed" not in text


@pytest.mark.django_db
def test_the_lookup_of_an_unknown_address_says_an_account_will_be_created(
    admin_client, organisation
):
    response = _lookup(admin_client, organisation, "nobody@example.com")

    assert response.status_code == 200
    assert "No account yet. One will be created and a setup email sent." in _text(
        response
    )


@pytest.mark.django_db
def test_the_lookup_of_an_unknown_address_offers_optional_name_fields(
    admin_client, organisation
):
    response = _lookup(admin_client, organisation, "nobody@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='first_name']")
    assert document.cssselect("input[name='last_name']")
    assert document.cssselect("input[name='role']")


@pytest.mark.django_db
def test_the_lookup_of_an_existing_address_offers_no_name_fields(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _lookup(admin_client, organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("input[name='first_name']")


@pytest.mark.django_db
def test_the_lookup_of_an_unknown_address_creates_nothing(admin_client, organisation):
    _lookup(admin_client, organisation, "nobody@example.com")

    assert not EmailAddress.objects.filter(email="nobody@example.com").exists()


@pytest.mark.django_db
def test_the_confirmation_for_an_unknown_address_states_the_role_and_carries_the_names(
    admin_client, organisation
):
    response = _submit_role(
        admin_client,
        organisation,
        "nobody@example.com",
        "organisation_admin",
        first_name="Ada",
    )

    document = lxml.html.fromstring(response.content.decode())
    text = _text(response)
    assert "Scope: Whole organisation." in text
    assert "An account will be created" not in text
    assert document.cssselect("input[type='hidden'][name='first_name'][value='Ada']")
    assert not User._base_manager.filter(email="nobody@example.com").exists()


@pytest.mark.django_db
def test_confirming_an_unknown_address_creates_the_account_with_the_names_and_role(
    admin_client, organisation
):
    _confirm(
        admin_client,
        organisation,
        "nobody@example.com",
        "organisation_admin",
        first_name="Ada",
        last_name="Lovelace",
    )

    user = User.objects.get(email="nobody@example.com")
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
    assert EmailAddress.objects.filter(user=user).count() == 1
    assert ObjectRoleAssignment.objects.filter(
        user=user, role="organisation_admin"
    ).exists()


@pytest.mark.django_db
def test_confirming_an_unknown_address_sends_one_setup_email(
    admin_client, organisation, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        _confirm(admin_client, organisation, "nobody@example.com", "organisation_admin")

    assert [message.to for message in mail.outbox] == [["nobody@example.com"]]


@pytest.mark.django_db
def test_a_refusal_after_the_account_step_rolls_the_account_back(
    admin_client, organisation, monkeypatch, django_capture_on_commit_callbacks
):
    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.assign_role", refuse
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = _confirm(
            admin_client, organisation, "nobody@example.com", "organisation_admin"
        )

    assert response.status_code == 403
    assert not User._base_manager.filter(email="nobody@example.com").exists()
    assert not EmailAddress.objects.filter(email="nobody@example.com").exists()
    assert mail.outbox == []


def _role_values(response) -> list[str]:
    document = lxml.html.fromstring(response.content.decode())
    return [radio.get("value") for radio in document.cssselect("input[name='role']")]


@pytest.mark.django_db
def test_an_organisation_admins_role_step_offers_no_roles_yet_first(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _lookup(admin_client, organisation, "ada@example.com")

    assert _role_values(response)[0] == ""
    assert "No roles yet" in _text(response)


@pytest.mark.django_db
def test_a_cohort_admins_role_step_does_not_offer_no_roles_yet(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    assert "" not in _role_values(response)


@pytest.mark.django_db
def test_the_no_role_confirmation_says_they_appear_in_staff_with_no_roles(
    admin_client, organisation
):
    UserFactory(email="ada@example.com", first_name="Ada", last_name="Lovelace")

    response = _submit_role(admin_client, organisation, "ada@example.com", "")

    assert response.status_code == 200
    assert "Add Ada Lovelace to the staff" in _text(response)
    assert "They'll appear in Staff with no roles." in _text(response)
    assert not StaffMember.objects.filter(user__email="ada@example.com").exists()


@pytest.mark.django_db
def test_confirming_no_role_creates_the_row_audits_and_fires_staff_changed(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    response = _confirm(admin_client, organisation, "ada@example.com", "")

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}
    staff_member = StaffMember.objects.get(user=user, organisation=organisation)
    entry = AuditLogEntry.unscoped.get(action="staff_member.added")
    assert (entry.target_label, entry.organisation) == (
        user.display_name,
        organisation,
    )
    assert entry.target == staff_member
    assert not ObjectRoleAssignment.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_adding_a_role_holder_who_has_no_row_with_no_role_is_422_before_confirming(
    admin_client, organisation
):
    user = _staff_member_holding(
        "cohort_admin", _cohort(organisation), first_name="Ada", last_name="Lovelace"
    )
    StaffMember.objects.filter(user=user).delete()

    response = _submit_role(admin_client, organisation, user.email, "")

    assert response.status_code == 422
    assert "Use Reactivate staff member instead." in _text(response)
    assert not StaffMember.objects.filter(user=user).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_active", "reason"),
    [
        (True, RefusalReason.ALREADY_STAFF),
        (False, RefusalReason.INACTIVE_STAFF_MEMBER),
    ],
)
def test_adding_an_existing_staff_member_with_no_role_is_422_before_confirming(
    admin_client, organisation, is_active, reason
):
    existing = StaffMemberFactory(organisation=organisation, is_active=is_active)
    email = existing.user.email

    response = _submit_role(admin_client, organisation, email, "")

    message = actions_module.REFUSAL_MESSAGES[reason].format(
        name=existing.user.display_name
    )
    assert response.status_code == 422
    assert message in _text(response)


@pytest.mark.django_db
def test_confirming_no_role_for_a_new_address_creates_the_account_and_sends_the_setup_email(
    admin_client, organisation, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = _confirm(admin_client, organisation, "nobody@example.com", "")

    user = User.objects.get(email="nobody@example.com")
    assert response.status_code == 204
    assert StaffMember.objects.filter(user=user, organisation=organisation).exists()
    assert [message.to for message in mail.outbox] == [["nobody@example.com"]]


@pytest.mark.django_db
def test_the_lookup_of_an_invalid_address_is_422(admin_client, organisation):
    response = _lookup(admin_client, organisation, "not-an-email")

    assert response.status_code == 422


@pytest.mark.django_db
def test_the_role_step_offers_every_staff_role_with_its_description(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")
    config = get_role_config(organisation.site.name)

    response = _lookup(admin_client, organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    offered = [
        r.get("value") for r in document.cssselect("input[name='role']:not([value=''])")
    ]
    text = _text(response)
    assert offered == [
        "organisation_admin",
        "organisation_staff_viewer",
        "organisation_staff_roles_viewer",
        "question_bank_viewer",
        "cohort_admin",
        "cohort_viewer",
    ]
    assert all(config[role].description in text for role in offered)
    assert not document.cssselect("input[name='role']:not([value=''])[checked]")


@pytest.mark.django_db
def test_a_site_admin_is_offered_six_roles(
    mock_site_context, logged_in_client, organisation
):
    CohortFactory(organisation=organisation)
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    UserFactory(email="ada@example.com")

    response = _lookup(logged_in_client(site_admin), organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert len(document.cssselect("input[name='role']:not([value=''])")) == 6


@pytest.mark.django_db
def test_with_no_active_cohort_only_the_organisation_roles_are_offered(
    mock_site_context, logged_in_client, organisation
):
    client, _ = _holder_client(logged_in_client, organisation)
    UserFactory(email="ada@example.com")

    response = _lookup(client, organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert [
        r.get("value") for r in document.cssselect("input[name='role']:not([value=''])")
    ] == [
        "organisation_admin",
        "organisation_staff_viewer",
        "organisation_staff_roles_viewer",
        "question_bank_viewer",
    ]
    assert "This organisation has no active cohorts yet." in _text(response)


@pytest.mark.django_db
def test_a_member_role_the_grantor_cannot_give_is_explained(
    admin_client, organisation, monkeypatch
):
    UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    text = _text(_lookup(admin_client, organisation, "ada@example.com"))

    assert "You can only give roles at or below your own." in text


@pytest.mark.django_db
def test_submitting_without_confirmation_shows_the_confirmation_and_writes_nothing(
    admin_client, organisation
):
    UserFactory(email="ada@example.com", first_name="Ada", last_name="Lovelace")
    roles_before = ObjectRoleAssignment.objects.count()
    members_before = StaffMember.objects.count()
    config = get_role_config(organisation.site.name)["organisation_admin"]

    response = _submit_role(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    text = _text(response)
    assert response.status_code == 200
    assert "Add Ada Lovelace as Organisation admin" in text
    assert config.description in text
    assert "Scope: Whole organisation." in text
    assert (
        ObjectRoleAssignment.objects.count(),
        StaffMember.objects.count(),
    ) == (
        roles_before,
        members_before,
    )


@pytest.mark.django_db
def test_the_confirmation_lists_the_current_and_after_roles(
    mock_site_context, logged_in_client, organisation
):
    cohort = CohortFactory(organisation=organisation, name="Alpha")
    client, _ = _holder_client(logged_in_client, organisation)
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_viewer", cohort)

    text = _text(
        _submit_role(client, organisation, "ada@example.com", "organisation_admin")
    )

    assert "Now Cohort viewer: Alpha After" in text
    assert "Organisation admin: Whole organisation" in text


@pytest.mark.django_db
def test_confirming_grants_organisation_admin_and_fires_member_changed(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert trigger[STAFF_CHANGED] == {"ids": [str(user.pk)]}
    assert ObjectRoleAssignment.objects.filter(
        user=user, role="organisation_admin", object_id=str(organisation.pk)
    ).exists()


@pytest.mark.django_db
def test_granting_organisation_admin_to_a_holder_is_422_with_the_message(
    admin_client, organisation
):
    holder = UserFactory(email="ada@example.com", first_name="Ada", last_name="L")
    assign_role(UserFactory(superuser=True), holder, "organisation_admin", organisation)

    response = _submit_role(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 422
    assert "Ada L is already Organisation admin here." in _text(response)


@pytest.mark.django_db
def test_a_confirmed_grant_of_organisation_admin_to_a_holder_is_422_and_restamps_nothing(
    admin_client, organisation
):
    """Two admins can open the dialog for the same person; the second to
    confirm must not overwrite who granted the role and when."""
    holder = UserFactory(email="ada@example.com", first_name="Ada", last_name="L")
    original_grantor = UserFactory(superuser=True)
    assign_role(original_grantor, holder, "organisation_admin", organisation)
    assignment = ObjectRoleAssignment.objects.get(
        user=holder, role="organisation_admin"
    )
    stamped_at = assignment.assigned_at

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 422
    assert "Ada L is already Organisation admin here." in _text(response)
    assignment.refresh_from_db()
    assert assignment.assigned_by == original_grantor
    assert assignment.assigned_at == stamped_at


@pytest.mark.django_db
def test_a_role_outside_the_grantors_reach_is_the_403_fragment_and_writes_nothing(
    admin_client, organisation, monkeypatch
):
    cohort = CohortFactory(organisation=organisation)
    target = UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (cohort,))],
    )

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 403
    assert not ObjectRoleAssignment.objects.filter(user=target).exists()


@pytest.mark.django_db
def test_a_cohort_role_is_checked_against_that_roles_own_cohorts(
    admin_client, organisation, monkeypatch
):
    allowed = CohortFactory(organisation=organisation)
    other = CohortFactory(organisation=organisation)
    target = UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [
            GrantableRole("cohort_admin", (other,)),
            GrantableRole("cohort_viewer", (allowed,)),
        ],
    )

    response = _confirm(
        admin_client,
        organisation,
        "ada@example.com",
        "cohort_viewer",
        cohorts=str(other.pk),
    )

    assert response.status_code == 403
    assert not ObjectRoleAssignment.objects.filter(user=target).exists()


@pytest.mark.django_db
def test_a_user_with_nothing_to_grant_is_denied_at_the_lookup(
    mock_site_context, logged_in_client, organisation, monkeypatch
):
    client, _ = _holder_client(logged_in_client, organisation)
    UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *a: [],
    )

    response = _lookup(client, organisation, "ada@example.com")

    assert response.status_code == 403
    assert "Ada" not in _text(response)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (
            RefusalReason.SELF,
            "You can't change your own roles. Ask another organisation admin.",
        ),
        (
            RefusalReason.INACTIVE_USER,
            "This person's account is turned off, so they can't be given a role.",
        ),
    ],
)
def test_each_refusal_answers_422_with_its_message(
    admin_client, organisation, monkeypatch, reason, message
):
    UserFactory(email="ada@example.com")

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(reason)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.assign_role", refuse
    )

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert (response.status_code, message in _text(response)) == (422, True)


@pytest.mark.django_db
def test_a_not_permitted_refusal_is_the_403_fragment(
    admin_client, organisation, monkeypatch
):
    UserFactory(email="ada@example.com")

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.assign_role", refuse
    )

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_turned_off_account_cannot_be_given_a_role(admin_client, organisation):
    UserFactory(email="ada@example.com", is_active=False)

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 422
    assert "account is turned off" in _text(response)


@pytest.mark.django_db
def test_a_confirmed_post_for_another_sites_address_is_422_and_writes_nothing(
    admin_client, organisation
):
    away = User._base_manager.create(
        site=SiteFactory(), email="away@example.com", first_name="Awaynamed"
    )

    response = _confirm(
        admin_client, organisation, "away@example.com", "organisation_admin"
    )

    text = _text(response)
    assert response.status_code == 422
    assert "belongs to an account on another site" in text
    assert "Awaynamed" not in text
    assert not ObjectRoleAssignment.objects.filter(user_id=away.pk).exists()


@pytest.mark.django_db
def test_the_confirmation_for_a_site_level_admin_states_only_the_role(
    admin_client, organisation
):
    site_admin = UserFactory(email="boss@example.com")
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )

    text = _text(
        _submit_role(
            admin_client, organisation, "boss@example.com", "organisation_admin"
        )
    )

    assert "Scope: Whole organisation." in text
    assert "already has access to every organisation" not in text


@pytest.mark.django_db
def test_the_confirmation_for_a_suspended_member_says_the_role_waits_for_reactivation(
    admin_client, organisation
):
    cohort = CohortFactory(organisation=organisation)
    inactive_staff_member = UserFactory(email="ada@example.com")
    assign_role(
        UserFactory(superuser=True), inactive_staff_member, "cohort_viewer", cohort
    )
    StaffMember.objects.filter(user=inactive_staff_member).update(is_active=False)

    text = _text(
        _submit_role(
            admin_client, organisation, "ada@example.com", "organisation_admin"
        )
    )
    _confirm(admin_client, organisation, "ada@example.com", "organisation_admin")

    assert "takes effect only once they are reactivated" in text
    assert not StaffMember.objects.get(user=inactive_staff_member).is_active


@pytest.mark.django_db
def test_a_grant_to_someone_with_no_member_row_creates_an_active_one(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    text = _text(
        _submit_role(
            admin_client, organisation, "ada@example.com", "organisation_admin"
        )
    )
    _confirm(admin_client, organisation, "ada@example.com", "organisation_admin")

    assert "Adding this role creates one" not in text
    assert StaffMember.objects.get(user=user, organisation=organisation).is_active


@pytest.mark.django_db
def test_a_cohort_admin_reaching_the_add_member_url_gets_404(
    mock_site_context, logged_in_client, organisation
):
    cohort = CohortFactory(organisation=organisation)
    client, _ = _holder_client(logged_in_client, cohort, "cohort_admin")

    response = client.get(_add_staff_member_url(organisation), HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_empty_members_page_offers_add_member_in_the_header_and_the_empty_state(
    mock_site_context, logged_in_client, organisation
):
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )

    html = (
        logged_in_client(site_admin)
        .get(_interface_url(organisation.slug, "staff"))
        .content.decode()
    )

    header, _, empty_state = html.partition("No staff yet.")
    assert "/staff/__actions/add_staff_member" in header
    assert "/staff/__actions/add_staff_member" in empty_state


@pytest.mark.django_db
def test_the_members_page_header_holds_the_add_member_trigger(
    admin_client, organisation
):
    html = admin_client.get(_interface_url(organisation.slug, "staff")).content.decode()

    assert "/staff/__actions/add_staff_member" in html


@pytest.mark.django_db
def test_a_site_admin_with_nothing_to_grant_sees_no_add_member_trigger(
    mock_site_context, logged_in_client, organisation, monkeypatch
):
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *a: [],
    )

    html = (
        logged_in_client(site_admin)
        .get(_interface_url(organisation.slug, "staff"))
        .content.decode()
    )

    assert "/staff/__actions/add_staff_member" not in html


def _cohort_post(
    client: Client,
    organisation: Organisation,
    role: str,
    cohorts: list[Cohort],
    confirmed: bool = False,
):
    data: dict[str, str | list[str]] = {
        "step": "submit",
        "email": "ada@example.com",
        "role": role,
        "cohorts": [str(cohort.pk) for cohort in cohorts],
    }
    if confirmed:
        data["confirmed"] = "1"
    return _post(client, _add_staff_member_url(organisation), data)


@pytest.mark.django_db
def test_the_role_step_lists_each_grantable_cohort_with_the_roles_it_is_offered_for(
    admin_client, organisation, monkeypatch
):
    admin_only = _cohort(organisation, name="Alpha")
    both = _cohort(organisation, name="Beta")
    UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [
            GrantableRole("cohort_admin", (admin_only, both)),
            GrantableRole("cohort_viewer", (both,)),
        ],
    )

    response = _lookup(admin_client, organisation, "ada@example.com")

    rows = lxml.html.fromstring(response.content.decode()).cssselect(
        "[data-cohort-row]"
    )
    assert [(r.get("data-name"), r.get("data-roles")) for r in rows] == [
        ("alpha", "cohort_admin"),
        ("beta", "cohort_admin cohort_viewer"),
    ]


@pytest.mark.django_db
def test_the_role_step_explains_that_every_cohort_is_not_organisation_admin(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _lookup(admin_client, organisation, "ada@example.com")

    assert "Choosing every cohort is not the same as organisation admin" in _text(
        response
    )


@pytest.mark.django_db
def test_a_cohort_role_without_a_cohort_is_422_on_the_role_step(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _cohort_post(admin_client, organisation, "cohort_admin", [])

    assert response.status_code == 422
    assert "Choose at least one cohort." in _text(response)


@pytest.mark.django_db
def test_the_confirmation_names_the_cohorts_escaped(admin_client, organisation):
    cohort = _cohort(organisation, name="<b>Bold</b> cohort")
    UserFactory(email="ada@example.com")

    response = _cohort_post(admin_client, organisation, "cohort_admin", [cohort])

    html = response.content.decode()
    assert "&lt;b&gt;Bold&lt;/b&gt; cohort" in html
    assert "<b>Bold</b>" not in html


@pytest.mark.django_db
def test_the_confirmation_states_the_role_description_and_scope_and_nothing_more(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    UserFactory(email="ada@example.com")

    response = _cohort_post(admin_client, organisation, "cohort_admin", [cohort])

    text = _text(response)
    assert "Scope: Spring." in text
    assert "will be able to do more than they can now" not in text
    assert "has no active membership here" not in text


@pytest.mark.django_db
def test_confirming_grants_the_role_on_each_cohort(admin_client, organisation):
    first = _cohort(organisation)
    second = _cohort(organisation)
    user = UserFactory(email="ada@example.com")

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [first, second], confirmed=True
    )

    granted = set(
        ObjectRoleAssignment.objects.filter(user=user, role="cohort_admin").values_list(
            "object_id", flat=True
        )
    )
    assert (response.status_code, granted) == (204, {str(first.pk), str(second.pk)})


@pytest.mark.django_db
def test_a_role_already_held_on_every_chosen_cohort_is_422(admin_client, organisation):
    cohort = _cohort(organisation)
    holder = UserFactory(email="ada@example.com", first_name="Ada", last_name="L")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", cohort)

    response = _cohort_post(admin_client, organisation, "cohort_admin", [cohort])

    assert response.status_code == 422
    assert "Ada L already holds this role on these cohorts." in _text(response)


@pytest.mark.django_db
def test_a_partial_overlap_names_the_held_cohorts_in_the_confirmation(
    admin_client, organisation
):
    held = _cohort(organisation, name="Held cohort")
    new = _cohort(organisation, name="New cohort")
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", held)

    response = _cohort_post(admin_client, organisation, "cohort_admin", [held, new])

    text = _text(response)
    assert "Scope: New cohort." in text
    assert "already holds this role on Held cohort" in text


@pytest.mark.django_db
def test_a_partial_overlap_grants_only_the_new_cohorts(admin_client, organisation):
    held = _cohort(organisation)
    new = _cohort(organisation)
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", held)

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [held, new], confirmed=True
    )

    granted = set(
        ObjectRoleAssignment.objects.filter(
            user=holder, role="cohort_admin"
        ).values_list("object_id", flat=True)
    )
    assert (response.status_code, granted) == (204, {str(held.pk), str(new.pk)})


@pytest.mark.django_db
def test_a_cohort_outside_the_chosen_roles_grantable_cohorts_is_the_403_fragment(
    admin_client, organisation, monkeypatch
):
    allowed = _cohort(organisation)
    outside = _cohort(organisation)
    user = UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_admin", (allowed,))],
    )

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [outside], confirmed=True
    )

    assert response.status_code == 403
    assert not ObjectRoleAssignment.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_a_cohort_of_another_organisation_is_a_form_error_and_writes_nothing(
    admin_client, organisation
):
    foreign = _cohort(cast(Organisation, OrganisationFactory()))
    user = UserFactory(email="ada@example.com")

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [foreign], confirmed=True
    )

    assert response.status_code == 422
    assert not ObjectRoleAssignment.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_the_add_dialog_gives_a_viewer_role_on_the_organisation(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_staff_roles_viewer"
    )

    assert response.status_code == 204
    assert _active_roles(user) == {
        ("organisation_staff_roles_viewer", str(organisation.pk))
    }


@pytest.mark.django_db
def test_the_add_dialog_gives_the_question_bank_viewer_role_on_the_organisation(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    response = _confirm(
        admin_client, organisation, "ada@example.com", "question_bank_viewer"
    )

    assert response.status_code == 204
    assert _active_roles(user) == {("question_bank_viewer", str(organisation.pk))}


@pytest.mark.django_db
def test_deactivating_the_question_bank_viewer_role_deactivates_the_assignment(
    admin_client, organisation
):
    user = _staff_member_holding("question_bank_viewer", organisation)

    response = _remove(admin_client, organisation, user, "question_bank_viewer")

    assert response.status_code == 204
    assert _active_roles(user) == set()


@pytest.mark.django_db
def test_a_cohort_admins_forged_question_bank_viewer_grant_answers_422(
    cohort_admin_setup, organisation
):
    cohort, admin = cohort_admin_setup
    learner = LearnerFactory(organisation=organisation).user
    ctx = _cohort_admin_ctx(
        organisation,
        cohort,
        admin,
        {
            "step": "submit",
            "email": learner.email,
            "role": "question_bank_viewer",
            "cohorts": str(cohort.pk),
            "confirmed": "1",
        },
    )

    response = AddStaffMemberToCohortAction().handle_submit(ctx)

    assert response.status_code == 422
    assert not ObjectRoleAssignment.objects.filter(
        user=learner, role="question_bank_viewer"
    ).exists()


@pytest.mark.django_db
def test_giving_a_viewer_role_twice_is_422_and_names_the_role(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")
    assign_role(
        UserFactory(superuser=True),
        user,
        "organisation_staff_roles_viewer",
        organisation,
    )

    response = _submit_role(
        admin_client, organisation, "ada@example.com", "organisation_staff_roles_viewer"
    )

    assert response.status_code == 422
    assert "is already Organisation staff and roles viewer here." in _text(response)


@pytest.mark.django_db
def test_deactivating_a_viewer_role_deactivates_the_organisation_assignment(
    admin_client, organisation
):
    user = _staff_member_holding("organisation_staff_viewer", organisation)

    response = _remove(admin_client, organisation, user, "organisation_staff_viewer")

    assert response.status_code == 204
    assert _active_roles(user) == set()


@pytest.mark.django_db
def test_deactivating_your_own_organisation_admin_role_sends_you_to_a_section_you_can_still_see(
    logged_in_client, organisation
):
    """Removing the role that granted the Staff section leaves the actor
    nowhere to stay on Staff, so the response sends them to the first
    section they can still see."""
    cohort = _cohort(organisation)
    client, actor = _holder_client(logged_in_client, organisation)
    assign_role(UserFactory(superuser=True), actor, "cohort_viewer", cohort)
    _holder_client(logged_in_client, organisation)

    response = _remove(client, organisation, actor, "organisation_admin")

    assert response.status_code == 204
    assert response["HX-Redirect"] == _interface_url(organisation.slug, "dashboard")
    assert _active_roles(actor) == {("cohort_viewer", str(cohort.pk))}


@pytest.mark.django_db
def test_deactivating_someone_elses_role_keeps_the_actor_on_the_staff_page(
    admin_client, organisation
):
    user = _staff_member_holding("organisation_staff_viewer", organisation)

    response = _remove(admin_client, organisation, user, "organisation_staff_viewer")

    assert "HX-Redirect" not in response


def _remove_dialog(client: Client, organisation: Organisation, user: User, role: str):
    return client.get(
        _remove_role_url(organisation),
        {"user": str(user.pk), "role": role},
        HTTP_HX_REQUEST="true",
    )


def _remove(client: Client, organisation: Organisation, user: User, role: str):
    return _post(
        client, _remove_role_url(organisation), {"user": str(user.pk), "role": role}
    )


def _active_roles(user: User) -> set[tuple[str, str]]:
    return {
        (a.role, a.object_id)
        for a in ObjectRoleAssignment.objects.filter(user=user, is_active=True)
    }


@pytest.mark.django_db
def test_the_remove_confirmation_names_the_person_the_role_and_the_scope(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding(
        "cohort_admin", cohort, first_name="Ada", last_name="Lovelace"
    )

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_admin"))

    assert "Deactivate Cohort admin for Ada Lovelace" in text
    assert (
        "They lose Cohort admin on Evening group: Manages the learners and course registrations in their cohorts."
        in text
    )


@pytest.mark.django_db
def test_the_remove_confirmation_reads_an_organisation_role_as_the_whole_organisation(
    admin_client, organisation
):
    """The scope label "Whole organisation" used to be pasted mid-sentence,
    giving "They lose Organisation admin on Whole organisation"."""
    user = _staff_member_holding("organisation_admin", organisation)

    text = _text(_remove_dialog(admin_client, organisation, user, "organisation_admin"))

    assert "They lose Organisation admin on the whole organisation: " in text


@pytest.mark.django_db
def test_the_remove_confirmation_names_every_cohort_without_truncating(
    admin_client, organisation
):
    """The sentence used to splice a verb phrase after "They lose" and reuse
    the list's shortened scope, hiding cohorts that were being lost."""
    cohorts = [
        _cohort(organisation, name="Cohort A"),
        _cohort(organisation, name="Cohort B"),
        _cohort(organisation, name="Cohort C"),
    ]
    user = _staff_member_holding("cohort_admin", cohorts)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_admin"))

    assert "They lose Cohort admin on Cohort A, Cohort B and Cohort C: " in text


@pytest.mark.django_db
def test_the_remove_confirmation_lists_what_the_person_keeps(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding("cohort_admin", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)
    LearnerFactory(user=user, organisation=organisation)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_admin"))

    assert (
        "They keep their account, Cohort viewer on Evening group "
        "and their learner access in this organisation."
    ) in text


@pytest.mark.django_db
def test_the_remove_confirmation_loads_the_persons_roles_once(
    admin_client, organisation, monkeypatch
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_admin", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)
    calls: list[User] = []
    real_entries = current_role_entries

    def counting(target_user, target_organisation):
        calls.append(target_user)
        return real_entries(target_user, target_organisation)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.current_role_entries",
        counting,
    )

    response = _remove_dialog(admin_client, organisation, user, "cohort_admin")

    assert response.status_code == 200
    assert "They keep their account and Cohort viewer on" in _text(response)
    assert len(calls) == 1


@pytest.mark.django_db
def test_the_remove_confirmation_writes_nothing(admin_client, organisation):
    user = _staff_member_holding("cohort_admin", _cohort(organisation))
    before = _active_roles(user)

    _remove_dialog(admin_client, organisation, user, "cohort_admin")

    assert _active_roles(user) == before


@pytest.mark.django_db
def test_a_confirmed_removal_ends_the_role_on_every_cohort_of_the_entry(
    admin_client, organisation
):
    cohorts = [_cohort(organisation), _cohort(organisation)]
    user = _staff_member_holding("cohort_viewer", cohorts)

    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert response.status_code == 204
    assert _active_roles(user) == set()
    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}


def _reach_only(monkeypatch, *cohorts: Cohort) -> None:
    """Make the grantor able to give and take roles on `cohorts` alone."""
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.cohorts_visible_to",
        lambda *args, **kwargs: Cohort.objects.filter(pk__in=[c.pk for c in cohorts]),
    )


@pytest.mark.django_db
def test_a_confirmed_removal_leaves_a_cohort_outside_the_grantors_reach(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation)
    unreachable = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", [reachable, unreachable])
    _reach_only(monkeypatch, reachable)

    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert response.status_code == 204
    assert _active_roles(user) == {("cohort_viewer", str(unreachable.pk))}


@pytest.mark.django_db
def test_the_remove_confirmation_names_the_cohort_that_stays_out_of_reach(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation, name="Reachable")
    unreachable = _cohort(organisation, name="Beyond reach")
    user = _staff_member_holding("cohort_viewer", [reachable, unreachable])
    _reach_only(monkeypatch, reachable)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_viewer"))

    assert "They lose Cohort viewer on Reachable:" in text
    assert (
        "Cohort viewer on Beyond reach is outside the cohorts you can give, so it stays."
        in text
    )


@pytest.mark.django_db
def test_a_removal_with_no_cohort_in_reach_is_refused_and_writes_nothing(
    admin_client, organisation, monkeypatch
):
    unreachable = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", unreachable)
    _reach_only(monkeypatch, _cohort(organisation))
    before = _active_roles(user)

    dialog = _remove_dialog(admin_client, organisation, user, "cohort_viewer")
    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert dialog.status_code == 404
    assert response.status_code == 403
    assert _active_roles(user) == before


@pytest.mark.django_db
def test_a_confirmed_removal_leaves_the_other_roles_and_the_member_row(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_admin", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)

    _remove(admin_client, organisation, user, "cohort_admin")

    assert _active_roles(user) == {("cohort_viewer", str(cohort.pk))}
    assert StaffMember.objects.get(user=user, organisation=organisation).is_active


@pytest.mark.django_db
def test_the_remove_confirmation_for_a_site_level_target_says_their_access_is_unaffected(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    assign_role(UserFactory(superuser=True), user, "site_admin", organisation.site)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_viewer"))

    assert "Their site-level access is unaffected" in text
    assert "They stay on this organisation's staff list with no roles here." in text
    assert "takes them off this organisation's staff list" not in text


@pytest.mark.django_db
def test_the_remove_confirmation_for_a_site_level_target_with_other_roles_does_not_say_no_roles(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    assign_role(
        UserFactory(superuser=True), user, "cohort_admin", _cohort(organisation)
    )
    assign_role(UserFactory(superuser=True), user, "site_admin", organisation.site)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_viewer"))

    assert "Their site-level access is unaffected" in text
    assert "with no roles here" not in text


@pytest.mark.django_db
def test_the_remove_confirmation_for_your_own_role_speaks_to_you(
    logged_in_client, organisation
):
    """Someone removing their own Organisation admin cannot give the role
    back afterwards, so the dialog speaks to them and promises nothing
    they lose."""
    cohort = _cohort(organisation)
    client, actor = _holder_client(logged_in_client, organisation)
    assign_role(UserFactory(superuser=True), actor, "cohort_viewer", cohort)
    _holder_client(logged_in_client, organisation)

    text = _text(_remove_dialog(client, organisation, actor, "organisation_admin"))

    assert "Deactivate your Organisation admin role?" in text
    assert "You lose Organisation admin on the whole organisation" in text
    assert "You keep your account and Cohort viewer on" in text
    assert "Someone who can give this role can give it back to you." in text
    assert "They " not in text
    assert "You can give the role again later" not in text


@pytest.mark.django_db
def test_the_remove_confirmation_for_someone_else_keeps_the_third_person(
    admin_client, organisation
):
    user = _staff_member_holding("organisation_staff_viewer", organisation)

    text = _text(
        _remove_dialog(admin_client, organisation, user, "organisation_staff_viewer")
    )

    assert "They lose Organisation staff viewer" in text
    assert "They keep their account" in text
    assert "You can give the role again later." in text


@pytest.mark.django_db
def test_an_organisation_admin_removing_the_last_organisation_admin_is_422(
    admin_client, organisation, monkeypatch
):
    sole = _staff_member_holding("organisation_admin", organisation)
    monkeypatch.setattr(
        "freedom_ls.learner_management.role_assignment.is_last_organisation_admin",
        lambda *args: True,
    )

    response = _remove(admin_client, organisation, sole, "organisation_admin")

    assert response.status_code == 422
    assert "only organisation admin" in _text(response)
    assert _active_roles(sole) == {("organisation_admin", str(organisation.pk))}


@pytest.mark.django_db
def test_a_site_admin_removing_the_last_organisation_admin_is_warned_then_succeeds(
    mock_site_context, logged_in_client, organisation
):
    sole = _staff_member_holding(
        "organisation_admin", organisation, first_name="Ada", last_name="Lovelace"
    )
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    client = logged_in_client(site_admin)

    dialog = _text(_remove_dialog(client, organisation, sole, "organisation_admin"))
    response = _remove(client, organisation, sole, "organisation_admin")

    assert "Ada Lovelace is the only organisation admin." in dialog
    assert response.status_code == 204
    assert _active_roles(sole) == set()


@pytest.mark.django_db
def test_the_only_admin_warning_speaks_to_a_site_admin_removing_their_own_role(
    mock_site_context, logged_in_client, organisation
):
    """The warning named the viewer in the third person ("Ada is the only...")
    when they were deactivating their own role; it now says "You're"."""
    me = _staff_member_holding(
        "organisation_admin", organisation, first_name="Ada", last_name="Lovelace"
    )
    assign_role(UserFactory(superuser=True), me, "site_admin", organisation.site)
    client = logged_in_client(me)

    dialog = _text(_remove_dialog(client, organisation, me, "organisation_admin"))

    assert "You're the only organisation admin." in dialog
    assert "Ada Lovelace is the only organisation admin." not in dialog


@pytest.mark.django_db
def test_the_warning_is_absent_when_another_organisation_admin_remains(
    admin_client, organisation
):
    other = _staff_member_holding("organisation_admin", organisation)

    text = _text(
        _remove_dialog(admin_client, organisation, other, "organisation_admin")
    )

    assert "only organisation admin" not in text


@pytest.mark.django_db
def test_a_cohort_admin_may_remove_their_own_cohort_role(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, me = _holder_client(logged_in_client, cohort, "cohort_admin")
    assign_role(
        UserFactory(superuser=True), me, "organisation_staff_viewer", organisation
    )

    response = _remove(client, organisation, me, "cohort_admin")

    assert response.status_code == 204
    assert ("cohort_admin", str(cohort.pk)) not in _active_roles(me)


@pytest.mark.django_db
def test_removing_the_last_organisation_admin_role_from_yourself_is_422_with_the_lock_message(
    mock_site_context, logged_in_client, organisation
):
    client, me = _holder_client(logged_in_client, organisation)

    response = _remove(client, organisation, me, "organisation_admin")

    assert response.status_code == 422
    assert REFUSAL_MESSAGES[RefusalReason.LAST_ORGANISATION_ADMIN].format(
        name=me.display_name
    ) in _text(response)
    assert _active_roles(me) == {("organisation_admin", str(organisation.pk))}


@pytest.mark.django_db
def test_an_organisation_admin_removes_their_own_role_while_another_remains(
    mock_site_context, logged_in_client, organisation
):
    _staff_member_holding("organisation_admin", organisation)
    client, me = _holder_client(logged_in_client, organisation)

    response = _remove(client, organisation, me, "organisation_admin")

    assert response.status_code == 204
    assert _active_roles(me) == set()


@pytest.mark.django_db
def test_removing_a_role_the_user_does_not_hold_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))

    response = _remove(admin_client, organisation, user, "cohort_admin")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_removing_a_role_from_a_user_who_is_no_member_answers_the_unavailable_fragment(
    admin_client, organisation
):
    response = _remove(admin_client, organisation, UserFactory(), "cohort_viewer")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_refusal_partway_through_a_removal_is_403_and_keeps_every_cohort(
    admin_client, organisation, monkeypatch
):
    cohorts = [_cohort(organisation), _cohort(organisation)]
    user = _staff_member_holding("cohort_viewer", cohorts)
    before = _active_roles(user)
    real_remove_role = deactivate_role
    calls: list[Cohort] = []

    def refuse_second(grantor, target_user, role, target, **kwargs):
        if calls:
            raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)
        calls.append(target)
        real_remove_role(grantor, target_user, role, target, **kwargs)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.deactivate_role",
        refuse_second,
    )

    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert response.status_code == 403
    assert _active_roles(user) == before


@pytest.mark.django_db
def test_the_remove_confirmation_escapes_the_persons_name(admin_client, organisation):
    user = _staff_member_holding(
        "cohort_viewer", _cohort(organisation), first_name="<b>Bold</b>"
    )

    html = _remove_dialog(
        admin_client, organisation, user, "cohort_viewer"
    ).content.decode()

    assert "<b>Bold</b>" not in html
    assert "&lt;b&gt;Bold&lt;/b&gt;" in html


def _change_cohorts_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "staff/__actions/change_cohorts")


def _change_dialog(
    client: Client, organisation: Organisation, user: User, role: str = "cohort_viewer"
):
    return client.get(
        _change_cohorts_url(organisation),
        {"user": str(user.pk), "role": role},
        HTTP_HX_REQUEST="true",
    )


def _change(
    client: Client,
    organisation: Organisation,
    user: User,
    cohorts: list[Cohort],
    role: str = "cohort_viewer",
    confirmed: bool = True,
):
    data: dict[str, str | list[str]] = {
        "user": str(user.pk),
        "role": role,
        "cohorts": [str(cohort.pk) for cohort in cohorts],
    }
    if confirmed:
        data["confirmed"] = "1"
    return client.post(_change_cohorts_url(organisation), data, HTTP_HX_REQUEST="true")


def _checkbox_state(response) -> dict[str, bool]:
    document = lxml.html.fromstring(response.content.decode())
    return {
        box.get("value"): box.get("checked") is not None
        for box in document.cssselect("input[name='cohorts']")
    }


@pytest.mark.django_db
def test_the_change_dialog_ticks_the_cohorts_the_person_holds(
    admin_client, organisation
):
    held = _cohort(organisation, name="Held group")
    free = _cohort(organisation, name="Free group")
    user = _staff_member_holding("cohort_viewer", held)

    response = _change_dialog(admin_client, organisation, user)

    state = _checkbox_state(response)
    assert (state[str(held.pk)], state[str(free.pk)]) == (True, False)


@pytest.mark.django_db
def test_a_held_cohort_outside_the_grantors_reach_is_listed_read_only(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation, name="Reachable")
    unreachable = _cohort(organisation, name="Beyond reach")
    user = _staff_member_holding("cohort_viewer", [reachable, unreachable])
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (reachable,))],
    )

    response = _change_dialog(admin_client, organisation, user)

    assert _checkbox_state(response) == {str(reachable.pk): True}
    assert "Beyond reach (outside the cohorts you can give)" in _text(response)


@pytest.mark.django_db
def test_changing_cohorts_of_a_role_with_no_cohort_in_reach_is_refused_and_writes_nothing(
    admin_client, organisation, monkeypatch
):
    unreachable = _cohort(organisation)
    mine = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", unreachable)
    _reach_only(monkeypatch, mine)
    before = _active_roles(user)

    dialog = _change_dialog(admin_client, organisation, user)
    response = _change(admin_client, organisation, user, [mine])

    assert (dialog.status_code, response.status_code) == (404, 404)
    assert _active_roles(user) == before


@pytest.mark.django_db
def test_an_inactive_held_cohort_is_listed_read_only(admin_client, organisation):
    active = _cohort(organisation)
    dormant = _cohort(organisation, name="Dormant group")
    user = _staff_member_holding("cohort_viewer", [active, dormant])
    Cohort.objects.filter(pk=dormant.pk).update(is_active=False)

    response = _change_dialog(admin_client, organisation, user)

    assert str(dormant.pk) not in _checkbox_state(response)
    assert "Dormant group (inactive)" in _text(response)


@pytest.mark.django_db
def test_an_inactive_held_cohort_is_untouched_by_a_change(admin_client, organisation):
    active = _cohort(organisation)
    dormant = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", [active, dormant])
    Cohort.objects.filter(pk=dormant.pk).update(is_active=False)

    _change(admin_client, organisation, user, [])

    assert _active_roles(user) == {("cohort_viewer", str(dormant.pk))}


@pytest.mark.django_db
def test_a_held_cohort_outside_the_grantors_reach_is_untouched_by_a_change(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation)
    unreachable = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", [reachable, unreachable])
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (reachable,))],
    )

    _change(admin_client, organisation, user, [])

    assert _active_roles(user) == {("cohort_viewer", str(unreachable.pk))}


@pytest.mark.django_db
def test_the_confirmation_for_an_added_cohort_names_it(admin_client, organisation):
    held = _cohort(organisation)
    added = _cohort(organisation, name="Newly given")
    user = _staff_member_holding("cohort_viewer", held)

    response = _change(admin_client, organisation, user, [held, added], confirmed=False)

    text = _text(response)
    assert "Adds: Newly given" in text
    assert "will be able to do more than they can now" not in text
    assert "Deactivates on:" not in text


@pytest.mark.django_db
def test_the_confirmation_for_a_removed_cohort_names_the_loss(
    admin_client, organisation
):
    kept = _cohort(organisation)
    dropped = _cohort(organisation, name="Let go")
    user = _staff_member_holding("cohort_viewer", [kept, dropped])

    response = _change(admin_client, organisation, user, [kept], confirmed=False)

    text = _text(response)
    assert "Deactivates on: Let go" in text
    assert "will be able to do more" not in text
    assert "Adds:" not in text


@pytest.mark.django_db
def test_the_confirmation_for_an_added_and_a_removed_cohort_names_both(
    admin_client, organisation
):
    held = _cohort(organisation, name="Dropped one")
    added = _cohort(organisation, name="Added one")
    user = _staff_member_holding("cohort_viewer", held)

    response = _change(admin_client, organisation, user, [added], confirmed=False)

    text = _text(response)
    assert "Adds: Added one" in text
    assert "Deactivates on: Dropped one" in text


@pytest.mark.django_db
def test_the_confirmation_for_every_cohort_removed_uses_the_remove_wording(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)

    response = _change(admin_client, organisation, user, [], confirmed=False)

    document = lxml.html.fromstring(response.content.decode())
    assert f"Deactivate Cohort viewer for {user.display_name}" in _text(response)
    (button,) = document.cssselect("button[type=submit]")
    assert button.text_content().split()[0] == "Deactivate"


@pytest.mark.django_db
def test_a_confirmed_addition_grants_the_cohort(admin_client, organisation):
    held = _cohort(organisation)
    added = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", held)

    _change(admin_client, organisation, user, [held, added])

    assert _active_roles(user) == {
        ("cohort_viewer", str(held.pk)),
        ("cohort_viewer", str(added.pk)),
    }


@pytest.mark.django_db
def test_a_confirmed_removal_deactivates_the_cohort(admin_client, organisation):
    kept = _cohort(organisation)
    dropped = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", [kept, dropped])

    _change(admin_client, organisation, user, [kept])

    assert _active_roles(user) == {("cohort_viewer", str(kept.pk))}


@pytest.mark.django_db
def test_a_confirmed_change_with_an_addition_and_a_removal_does_both(
    admin_client, organisation
):
    dropped = _cohort(organisation)
    added = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", dropped)

    _change(admin_client, organisation, user, [added])

    assert _active_roles(user) == {("cohort_viewer", str(added.pk))}


@pytest.mark.django_db
def test_removing_every_cohort_leaves_no_active_assignment_for_the_role(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_admin", cohort)

    _change(admin_client, organisation, user, [])

    assert _active_roles(user) == {("cohort_admin", str(cohort.pk))}


@pytest.mark.django_db
def test_a_confirmed_change_answers_204_with_member_changed(admin_client, organisation):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))

    response = _change(admin_client, organisation, user, [_cohort(organisation)])

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}


@pytest.mark.django_db
def test_an_unconfirmed_change_leaves_every_assignment_unchanged(
    admin_client, organisation
):
    held = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", held)
    before = _active_roles(user)

    _change(admin_client, organisation, user, [_cohort(organisation)], confirmed=False)

    assert _active_roles(user) == before


@pytest.mark.django_db
def test_an_unchanged_selection_is_422(admin_client, organisation):
    held = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", held)

    response = _change(admin_client, organisation, user, [held], confirmed=False)

    assert response.status_code == 422
    assert "Nothing changed. Tick or untick a cohort first." in _text(response)


@pytest.mark.django_db
def test_a_cohort_outside_the_offered_set_answers_the_unavailable_fragment(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation)
    outside = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", reachable)
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (reachable,))],
    )

    response = _change(admin_client, organisation, user, [reachable, outside])

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()
    assert _active_roles(user) == {("cohort_viewer", str(reachable.pk))}


@pytest.mark.django_db
def test_a_cohort_admin_may_change_the_cohorts_of_their_own_role(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    other = _cohort(organisation)
    client, me = _holder_client(logged_in_client, cohort, "cohort_admin")
    assign_role(UserFactory(superuser=True), me, "cohort_admin", other)
    assign_role(UserFactory(superuser=True), me, "cohort_viewer", cohort)
    assign_role(
        UserFactory(superuser=True), me, "organisation_staff_viewer", organisation
    )

    response = _change(client, organisation, me, [cohort, other])

    assert response.status_code == 204
    assert ("cohort_viewer", str(other.pk)) in _active_roles(me)


@pytest.mark.django_db
def test_the_confirmation_for_a_person_with_no_member_row_names_only_the_change(
    admin_client, organisation
):
    held = _cohort(organisation)
    added = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", held)
    StaffMember.objects.filter(user=user).delete()

    response = _change(admin_client, organisation, user, [held, added], confirmed=False)

    text = _text(response)
    assert "Adds:" in text
    assert "Adding this role creates one" not in text


@pytest.mark.django_db
def test_the_confirmation_for_a_suspended_member_says_the_cohorts_wait_for_reactivation(
    admin_client, organisation
):
    held = _cohort(organisation)
    added = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", held)
    StaffMember.objects.filter(user=user).update(is_active=False)

    text = _text(
        _change(admin_client, organisation, user, [held, added], confirmed=False)
    )

    assert "is inactive here, so the added cohorts take effect only once" in text
    assert "has no active membership here" not in text


@pytest.mark.django_db
def test_a_change_for_an_organisation_admin_role_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _staff_member_holding("organisation_admin", organisation)

    response = _change(
        admin_client, organisation, user, [_cohort(organisation)], "organisation_admin"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_refusal_partway_through_a_change_keeps_every_assignment(
    admin_client, organisation, monkeypatch
):
    dropped = _cohort(organisation)
    added = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", dropped)
    before = _active_roles(user)

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.deactivate_role", refuse
    )

    response = _change(admin_client, organisation, user, [added])

    assert response.status_code == 403
    assert _active_roles(user) == before


def _state_dialog(client: Client, organisation: Organisation, user: User, action: str):
    return client.get(
        _state_url(organisation, action),
        {"user": str(user.pk)},
        HTTP_HX_REQUEST="true",
    )


def _state_post(client: Client, organisation: Organisation, user: User, action: str):
    return _post(client, _state_url(organisation, action), {"user": str(user.pk)})


def _staff_member_row(user: User, organisation: Organisation) -> StaffMember:
    return cast(
        StaffMember,
        StaffMember.objects.get(user=user, organisation=organisation),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["deactivate", "reactivate"])
def test_the_state_dialogs_leave_the_member_row_unchanged(
    admin_client, organisation, action
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    before = _staff_member_row(user, organisation).is_active

    _state_dialog(admin_client, organisation, user, action)

    assert _staff_member_row(user, organisation).is_active == before


@pytest.mark.django_db
def test_the_suspend_dialog_says_they_keep_their_roles(admin_client, organisation):
    user = _staff_member_holding(
        "cohort_viewer", _cohort(organisation), first_name="Ada", last_name="Lovelace"
    )

    text = _text(_state_dialog(admin_client, organisation, user, "deactivate"))

    assert "Deactivate Ada Lovelace" in text
    assert (
        f"They keep their roles but can do nothing in {organisation.name} "
        "until reactivated."
    ) in text


@pytest.mark.django_db
def test_suspending_stops_a_cohort_capability_and_answers_204(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    capability = "freedom_ls_learner_management.view_cohort"
    assert can(user, capability, cohort)

    response = _state_post(admin_client, organisation, user, "deactivate")

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}
    assert not _staff_member_row(user, organisation).is_active
    assert not can(user, capability, cohort)


@pytest.mark.django_db
def test_reactivating_restores_the_capability_and_answers_204(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    StaffMember.objects.filter(user=user).update(is_active=False)

    response = _state_post(admin_client, organisation, user, "reactivate")

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}
    assert can(user, "freedom_ls_learner_management.view_cohort", cohort)


@pytest.mark.django_db
def test_the_reactivate_dialog_for_someone_with_no_roles_says_so(
    admin_client, organisation
):
    member = StaffMemberFactory(organisation=organisation, is_active=False)

    text = _text(_state_dialog(admin_client, organisation, member.user, "reactivate"))

    assert "They have no roles here" in text
    assert "take effect again" not in text


@pytest.mark.django_db
def test_the_reactivate_dialog_lists_the_roles_that_take_effect_again(
    admin_client, organisation
):
    user = _staff_member_holding(
        "cohort_viewer",
        _cohort(organisation, name="Evening group"),
        first_name="Ada",
        last_name="Lovelace",
    )
    StaffMember.objects.filter(user=user).update(is_active=False)

    text = _text(_state_dialog(admin_client, organisation, user, "reactivate"))

    assert "Reactivate Ada Lovelace" in text
    assert "These roles take effect again: Cohort viewer on Evening group." in text


@pytest.mark.django_db
def test_reactivating_a_member_with_no_row_creates_an_active_one(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    StaffMember.objects.filter(user=user).delete()

    response = _state_post(admin_client, organisation, user, "reactivate")

    assert response.status_code == 204
    assert _staff_member_row(user, organisation).is_active


@pytest.mark.django_db
def test_reactivating_a_member_with_no_row_writes_member_reactivated(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    StaffMember.objects.filter(user=user).delete()

    _state_post(admin_client, organisation, user, "reactivate")

    entry = AuditLogEntry.unscoped.get(action="staff_member.reactivated")
    assert entry.target == _staff_member_row(user, organisation)
    assert entry.subjects[1:] == [subject_key(user)]


@pytest.mark.django_db
def test_an_organisation_admin_suspending_the_last_organisation_admin_is_422(
    admin_client, organisation, monkeypatch
):
    sole = _staff_member_holding("organisation_admin", organisation, first_name="Ada")
    monkeypatch.setattr(
        "freedom_ls.learner_management.role_assignment.is_last_organisation_admin",
        lambda *args: True,
    )

    response = _state_post(admin_client, organisation, sole, "deactivate")

    assert response.status_code == 422
    assert "Ada is this organisation's only organisation admin." in _text(response)
    assert _staff_member_row(sole, organisation).is_active


@pytest.mark.django_db
def test_a_site_admin_is_warned_in_the_suspend_dialog_and_succeeds(
    mock_site_context, logged_in_client, organisation
):
    sole = _staff_member_holding(
        "organisation_admin", organisation, first_name="Ada", last_name="Lovelace"
    )
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    client = logged_in_client(site_admin)

    dialog = _text(_state_dialog(client, organisation, sole, "deactivate"))
    response = _state_post(client, organisation, sole, "deactivate")

    assert "Ada Lovelace is the only organisation admin." in dialog
    assert response.status_code == 204
    assert not _staff_member_row(sole, organisation).is_active


@pytest.mark.django_db
def test_the_suspend_dialog_has_no_warning_while_another_organisation_admin_remains(
    admin_client, organisation
):
    other = _staff_member_holding("organisation_admin", organisation)

    text = _text(_state_dialog(admin_client, organisation, other, "deactivate"))

    assert "only organisation admin" not in text


@pytest.mark.django_db
def test_a_stale_suspend_of_an_inactive_row_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    StaffMember.objects.filter(user=user).update(is_active=False)

    response = _state_post(admin_client, organisation, user, "deactivate")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_stale_suspend_of_a_member_with_no_row_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
    StaffMember.objects.filter(user=user).delete()

    response = _state_post(admin_client, organisation, user, "deactivate")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_stale_reactivate_of_an_active_row_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))

    response = _state_post(admin_client, organisation, user, "reactivate")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_suspending_yourself_is_422_with_the_self_message(
    mock_site_context, logged_in_client, organisation
):
    _staff_member_holding("organisation_admin", organisation)
    client, me = _holder_client(logged_in_client, organisation)

    response = _state_post(client, organisation, me, "deactivate")

    assert response.status_code == 422
    assert "You can't change your own roles." in _text(response)
    assert _staff_member_row(me, organisation).is_active


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["deactivate", "reactivate"])
def test_a_state_change_for_a_non_member_answers_the_unavailable_fragment(
    admin_client, organisation, action
):
    response = _state_post(admin_client, organisation, UserFactory(), action)

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_the_state_dialogs_escape_the_persons_name(admin_client, organisation):
    user = _staff_member_holding(
        "cohort_viewer", _cohort(organisation), first_name="<b>Bold</b>"
    )

    html = _state_dialog(
        admin_client, organisation, user, "deactivate"
    ).content.decode()

    assert "<b>Bold</b>" not in html
    assert "&lt;b&gt;Bold&lt;/b&gt;" in html


def _search(
    client: Client, organisation: Organisation, term: str, cohort: Cohort | None = None
):
    url = (
        _cohort_add_staff_member_url(organisation, cohort)
        if cohort
        else _add_staff_member_url(organisation)
    )
    return client.get(url, {"q": term}, HTTP_HX_REQUEST="true")


def _options(response) -> list[lxml.html.HtmlElement]:
    document = lxml.html.fromstring(response.content.decode())
    return list(document.cssselect("[role='option']"))


@pytest.mark.django_db
def test_a_search_term_under_the_minimum_asks_for_more(admin_client, organisation):
    response = _search(admin_client, organisation, "e")

    assert "Type at least 2 characters to search, or enter a full email." in _text(
        response
    )
    assert _options(response) == []


@pytest.mark.django_db
def test_an_organisation_admin_finds_a_learner_who_is_not_staff(
    admin_client, organisation
):
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Erin", user__last_name="Learner"
    )

    options = _options(_search(admin_client, organisation, "erin"))

    assert [option.get("id") for option in options] == [
        f"staff-option-{learner.user.pk}"
    ]
    assert options[0].get("data-email") == learner.user.email


@pytest.mark.django_db
def test_a_search_option_for_an_account_with_no_name_shows_the_email_once(
    admin_client, organisation
):
    """An account with no name showed its email on the name line and again under it."""
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="",
        user__last_name="",
        user__email="nameless.member@qa.test",
    )

    (option,) = _options(_search(admin_client, organisation, "nameless"))

    assert option.get("id") == f"staff-option-{learner.user.pk}"
    assert option.text_content().count("nameless.member@qa.test") == 1


@pytest.mark.django_db
def test_a_cohort_admin_search_lists_only_people_they_may_pick(
    logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, _ = _holder_client(logged_in_client, cohort, "cohort_admin")
    LearnerFactory(
        organisation=organisation, user__first_name="Erin", user__last_name="Learner"
    )
    peer = UserFactory(first_name="Erin", last_name="Peer")
    assign_role(UserFactory(superuser=True), peer, "cohort_viewer", cohort)

    response = _search(client, organisation, "erin", cohort)

    assert [option.get("id") for option in _options(response)] == [
        f"staff-option-{peer.pk}"
    ]
    assert "Type their full email" not in _text(
        _search(client, organisation, "zzz", cohort)
    )


@pytest.mark.django_db
def test_an_organisation_admin_search_on_a_cohort_offers_the_full_email_route(
    admin_client, organisation
):
    cohort = _cohort(organisation)

    response = _search(admin_client, organisation, "zzz", cohort)

    assert "Type their full email to add someone else." in _text(response)


@pytest.mark.django_db
def test_an_organisation_admin_email_field_on_a_cohort_has_no_search_limit_note(
    admin_client, organisation
):
    cohort = _cohort(organisation)

    response = admin_client.get(
        _cohort_add_staff_member_url(organisation, cohort), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("[role='combobox']")
    assert not document.cssselect("#staff-search-help")


@pytest.mark.django_db
def test_a_cohort_admin_email_field_says_it_searches_staff_they_can_add(
    logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, _ = _holder_client(logged_in_client, cohort, "cohort_admin")

    response = client.get(
        _cohort_add_staff_member_url(organisation, cohort), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    help_text = document.get_element_by_id("staff-search-help")
    combobox = document.cssselect("[role='combobox']")[0]
    assert help_text.text_content().strip() == "Searching staff you can add"
    assert combobox.get("aria-describedby") == "staff-search-help"
    assert not document.cssselect(
        "#staff-search-results [role='listbox']:not([hidden])"
    )


@pytest.mark.django_db
def test_nine_matches_render_eight_options_and_the_cap_line(admin_client, organisation):
    for number in range(9):
        LearnerFactory(organisation=organisation, user__first_name=f"Sam{number}")

    response = _search(admin_client, organisation, "sam")

    assert len(_options(response)) == 8
    assert "Showing the first 8. Keep typing to narrow." in _text(response)


@pytest.mark.django_db
def test_search_results_carry_the_name_and_email_and_nothing_more(
    admin_client, organisation
):
    LearnerFactory(
        organisation=organisation,
        user__first_name="Erin",
        user__last_name="Learner",
        user__email="erin@example.com",
    )

    context = _search(admin_client, organisation, "erin").context

    (result,) = context["results"]
    assert set(result) == {"pk", "display_name", "email", "email_below_name"}


@pytest.mark.django_db
def test_a_search_term_is_escaped_in_the_no_match_note(admin_client, organisation):
    html = _search(admin_client, organisation, "<script>x</script>").content.decode()

    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html


@pytest.mark.django_db
def test_a_viewer_without_the_add_capability_cannot_search(
    logged_in_client, organisation
):
    client, _ = _holder_client(
        logged_in_client, organisation, "organisation_staff_viewer"
    )

    assert _search(client, organisation, "erin").status_code == 403


@pytest.mark.django_db
def test_search_results_are_an_unlinked_listbox_with_a_stable_id(
    admin_client, organisation
):
    LearnerFactory(organisation=organisation, user__first_name="Erin")

    document = lxml.html.fromstring(_search(admin_client, organisation, "erin").content)

    (listbox,) = document.cssselect("[role='listbox']")
    assert listbox.get("id")
    assert document.cssselect("[role='option'] a") == []


@pytest.mark.django_db
def test_the_email_input_is_a_list_autocomplete_combobox(admin_client, organisation):
    response = admin_client.get(
        _add_staff_member_url(organisation), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    (combobox,) = document.cssselect("input[role='combobox']")
    listbox_id = combobox.get("aria-controls")
    assert combobox.get("aria-autocomplete") == "list"
    assert combobox.get("hx-get") == _add_staff_member_url(organisation)
    assert document.cssselect(f"[id='{listbox_id}'][role='listbox']")


def _cohort_add_staff_member_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation,
        cohort,
        "/__tabs/settings/__panels/staff/__actions/add_staff_member",
    )


def _cohort_overview_lookup(client: Client, organisation: Organisation, cohort: Cohort):
    return _post(
        client,
        _cohort_add_staff_member_url(organisation, cohort),
        {"step": "lookup", "email": "ada@example.com"},
    )


def _cohort_overview_confirm(
    client: Client, organisation: Organisation, cohort: Cohort, cohorts: list[Cohort]
):
    return client.post(
        _cohort_add_staff_member_url(organisation, cohort),
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(other.pk) for other in cohorts],
            "confirmed": "1",
        },
        HTTP_HX_REQUEST="true",
    )


def _cohort_viewer_cohorts(user: User) -> set[str]:
    return set(
        ObjectRoleAssignment.objects.filter(
            user=user, role="cohort_viewer"
        ).values_list("object_id", flat=True)
    )


@pytest.mark.django_db
def test_the_cohort_dialog_offers_only_cohort_roles(admin_client, organisation):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    roles = [radio.get("value") for radio in document.cssselect("input[name='role']")]
    assert roles == ["cohort_admin", "cohort_viewer"]


@pytest.mark.django_db
def test_the_cohort_dialog_has_no_cohort_checklist(admin_client, organisation):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("input[type='checkbox'][name='cohorts']")


@pytest.mark.django_db
def test_the_cohort_dialog_carries_the_cohort_as_a_hidden_input(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    hidden = document.cssselect("input[type='hidden'][name='cohorts']")
    assert [field.get("value") for field in hidden] == [str(cohort.pk)]


@pytest.mark.django_db
def test_confirming_on_a_cohort_page_grants_the_role_on_that_cohort_alone(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    other = _cohort(organisation)
    user = UserFactory(email="ada@example.com")

    _cohort_overview_confirm(admin_client, organisation, cohort, [cohort])

    assert _cohort_viewer_cohorts(user) == {str(cohort.pk)}
    assert str(other.pk) not in _cohort_viewer_cohorts(user)


@pytest.mark.django_db
def test_the_cohort_confirmation_names_the_cohort_as_the_scope(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    UserFactory(email="ada@example.com")

    response = admin_client.post(
        _cohort_add_staff_member_url(organisation, cohort),
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(cohort.pk)],
        },
        HTTP_HX_REQUEST="true",
    )

    assert "Scope: Spring." in _text(response)


@pytest.mark.django_db
def test_a_post_naming_another_cohort_grants_nothing_on_it(admin_client, organisation):
    cohort = _cohort(organisation)
    other = _cohort(organisation)
    user = UserFactory(email="ada@example.com")

    _cohort_overview_confirm(admin_client, organisation, cohort, [other])

    assert _cohort_viewer_cohorts(user) == {str(cohort.pk)}


@pytest.mark.django_db
def test_the_settings_tab_offers_add_member_to_an_organisation_admin(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    LearnerFactory(organisation=organisation)

    html = admin_client.get(
        _cohort_url(organisation, cohort, "/__tabs/settings")
    ).content.decode()

    assert "/__tabs/settings/__panels/staff/__actions/add_staff_member" in html


@pytest.mark.django_db
def test_the_settings_tab_is_hidden_from_a_cohort_viewer(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, _ = _holder_client(logged_in_client, cohort, "cohort_viewer")

    response = client.get(
        _cohort_url(organisation, cohort, "/__tabs/settings"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_members_dialog_is_titled_add_a_member(admin_client, organisation):
    response = admin_client.get(
        _add_staff_member_url(organisation), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Add a staff member"


@pytest.mark.django_db
def test_the_cohort_dialog_email_step_is_titled_with_the_cohort(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")

    response = admin_client.get(
        _cohort_add_staff_member_url(organisation, cohort), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Add a staff member to Spring"


@pytest.mark.django_db
def test_the_cohort_dialog_role_step_is_titled_with_the_cohort(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Add a staff member to Spring"


@pytest.mark.django_db
def test_the_cohort_dialog_does_not_tell_an_organisation_admin_about_rank(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    text = _text(_cohort_overview_lookup(admin_client, organisation, cohort))

    assert "You can only give roles at or below your own." not in text


# who a cohort admin may add
#
# The cohort Settings tab does not open for a cohort admin yet, so these call
# the action directly with the admin's request.


@pytest.fixture
def cohort_admin_setup(
    organisation: Organisation,
) -> tuple[Cohort, User]:
    cohort = _cohort(organisation)
    admin = cast(User, UserFactory(staff=True))
    assign_role(UserFactory(superuser=True), admin, "cohort_admin", cohort)
    return cohort, admin


def _cohort_admin_ctx(
    organisation: Organisation,
    cohort: Cohort,
    admin: User,
    data: dict[str, str] | None = None,
) -> PanelContext:
    request = RequestFactory().post("/", data or {}, HTTP_HX_REQUEST="true")
    request.user = admin
    request.organisation = organisation
    return PanelContext(
        request=request,
        instance=cohort,
        base_url="/",
        name="",
        config=CohortConfig,
    )


def _lookup_in_cohort(
    organisation: Organisation, cohort: Cohort, admin: User, email: str
):
    ctx = _cohort_admin_ctx(
        organisation, cohort, admin, {"step": "lookup", "email": email}
    )
    return AddStaffMemberToCohortAction().handle_submit(ctx)


@pytest.mark.django_db
def test_a_cohort_admins_misses_answer_422_with_one_identical_body(
    cohort_admin_setup, organisation
):
    cohort, admin = cohort_admin_setup
    learner = LearnerFactory(organisation=organisation).user
    unseen = _staff_member_holding("cohort_viewer", _cohort(organisation))
    users_before = User._base_manager.count()

    responses = [
        _lookup_in_cohort(organisation, cohort, admin, email)
        for email in (learner.email, "nobody@example.com", unseen.email)
    ]

    assert {response.status_code for response in responses} == {422}
    assert len({response.content for response in responses}) == 1
    assert REFUSAL_MESSAGES[RefusalReason.NOT_VISIBLE] in _text(responses[0])
    assert User._base_manager.count() == users_before


@pytest.mark.django_db
def test_a_cohort_admin_can_pick_staff_on_their_own_cohort(
    cohort_admin_setup, organisation
):
    cohort, admin = cohort_admin_setup
    colleague = _staff_member_holding("cohort_viewer", cohort)

    response = _lookup_in_cohort(organisation, cohort, admin, colleague.email)

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_cohort_admins_forged_submit_naming_someone_unpickable_answers_422(
    cohort_admin_setup, organisation
):
    cohort, admin = cohort_admin_setup
    learner = LearnerFactory(organisation=organisation).user
    ctx = _cohort_admin_ctx(
        organisation,
        cohort,
        admin,
        {
            "step": "submit",
            "email": learner.email,
            "role": "cohort_viewer",
            "cohorts": str(cohort.pk),
            "confirmed": "1",
        },
    )

    response = AddStaffMemberToCohortAction().handle_submit(ctx)

    assert response.status_code == 422
    assert not ObjectRoleAssignment.objects.filter(
        user=learner, role="cohort_viewer"
    ).exists()


@pytest.mark.django_db
def test_add_staff_to_a_cohort_is_offered_only_when_there_is_someone_to_pick(
    cohort_admin_setup, organisation
):
    cohort, admin = cohort_admin_setup

    def offered() -> bool:
        ctx = _cohort_admin_ctx(organisation, cohort, admin)
        return AddStaffMemberToCohortAction().is_offered(ctx)

    assert not offered()

    _staff_member_holding("cohort_viewer", cohort)

    assert offered()


@pytest.mark.django_db
def test_add_staff_to_a_cohort_is_offered_to_someone_who_may_add_anyone(organisation):
    cohort = _cohort(organisation)
    admin = cast(User, UserFactory(staff=True))
    assign_role(UserFactory(superuser=True), admin, "organisation_admin", organisation)
    ctx = _cohort_admin_ctx(organisation, cohort, admin)

    assert AddStaffMemberToCohortAction().is_offered(ctx)


def _add_role_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "staff/__actions/add_role")


def _add_role_dialog(client: Client, organisation: Organisation, user: User):
    return client.get(
        _add_role_url(organisation), {"user": str(user.pk)}, HTTP_HX_REQUEST="true"
    )


def _add_role(
    client: Client,
    organisation: Organisation,
    user: User,
    role: str,
    cohorts: list[Cohort] | None = None,
    **extra: str,
):
    return client.post(
        _add_role_url(organisation),
        {
            "step": "submit",
            "user": str(user.pk),
            "role": role,
            "cohorts": [str(cohort.pk) for cohort in cohorts or []],
            "confirmed": "1",
            **extra,
        },
        HTTP_HX_REQUEST="true",
    )


@pytest.mark.django_db
def test_the_add_role_dialog_opens_at_the_role_step_with_the_person_and_their_roles(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding(
        "cohort_viewer", cohort, first_name="Ada", last_name="Lovelace"
    )

    response = _add_role_dialog(admin_client, organisation, user)

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='role']")
    assert not document.cssselect("input[name='email']")
    assert [i.get("value") for i in document.cssselect("input[name='user']")] == [
        str(user.pk)
    ]
    text = _text(response)
    assert "Add a role for Ada Lovelace" in text
    assert "Now Cohort viewer: Evening group" in text
    assert "Existing account" not in text


@pytest.mark.django_db
def test_the_add_staff_dialog_steps_read_next_and_the_confirm_step_confirm(
    admin_client, organisation
):
    """A step button says where the person goes, and the last says Confirm,
    never a noun that may be untrue for someone already on the staff."""
    cohort = _cohort(organisation)
    user = _staff_member_holding("organisation_staff_viewer", organisation)

    def submit_labels(response) -> list[str]:
        document = lxml.html.fromstring(response.content.decode())
        return [
            b.text_content().strip().splitlines()[0]
            for b in document.cssselect("button[type='submit']")
        ]

    role_step = _add_role_dialog(admin_client, organisation, user)
    confirmation = _add_role(
        admin_client, organisation, user, "cohort_viewer", [cohort], confirmed="0"
    )
    ordinary = _lookup(admin_client, organisation, "new.person@example.com")

    email_step = admin_client.get(_add_staff_member_url(organisation))

    assert submit_labels(email_step) == ["Next"]
    assert submit_labels(role_step) == ["Next"]
    assert submit_labels(ordinary) == ["Next"]
    assert submit_labels(confirmation) == ["Confirm"]


@pytest.mark.django_db
def test_add_role_disables_a_role_held_on_every_cohort_the_grantor_can_give(
    admin_client, organisation
):
    cohorts = list(Cohort.objects.filter(organisation=organisation))
    user = _staff_member_holding("cohort_viewer", cohorts)

    response = _add_role_dialog(admin_client, organisation, user)

    document = lxml.html.fromstring(response.content.decode())
    (held,) = document.cssselect("input[name='role'][value='cohort_viewer']")
    (other,) = document.cssselect("input[name='role'][value='cohort_admin']")
    assert held.get("disabled") is not None
    assert other.get("disabled") is None
    (reason,) = document.cssselect(f"#{held.get('aria-describedby')}")
    assert reason.text_content().strip() == "Already held on every cohort you can give"


@pytest.mark.django_db
def test_add_role_disables_an_organisation_role_the_person_holds(
    admin_client, organisation
):
    user = _staff_member_holding("organisation_staff_viewer", organisation)

    response = _add_role_dialog(admin_client, organisation, user)

    document = lxml.html.fromstring(response.content.decode())
    (held,) = document.cssselect(
        "input[name='role'][value='organisation_staff_viewer']"
    )
    assert held.get("disabled") is not None
    (reason,) = document.cssselect(f"#{held.get('aria-describedby')}")
    assert reason.text_content().strip() == "Already held"


@pytest.mark.django_db
def test_add_role_submit_grants_the_role_and_fires_staff_changed(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("organisation_staff_viewer", organisation)

    response = _add_role(admin_client, organisation, user, "cohort_viewer", [cohort])

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}
    assert ("cohort_viewer", str(cohort.pk)) in _active_roles(user)


@pytest.mark.django_db
def test_add_role_submit_of_a_held_role_answers_422(admin_client, organisation):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)

    response = _add_role(admin_client, organisation, user, "cohort_viewer", [cohort])

    assert response.status_code == 422


@pytest.mark.django_db
def test_add_role_grants_to_the_person_named_by_user_not_the_posted_email(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("organisation_staff_viewer", organisation)
    bystander = UserFactory(email="bystander@example.com")

    response = _add_role(
        admin_client,
        organisation,
        user,
        "cohort_viewer",
        [cohort],
        email=bystander.email,
    )

    assert response.status_code == 204
    assert ("cohort_viewer", str(cohort.pk)) in _active_roles(user)
    assert not ObjectRoleAssignment.objects.filter(user=bystander).exists()


@pytest.fixture
def viewing_cohort_admin(
    organisation: Organisation, cohort_admin_setup: tuple[Cohort, User]
) -> User:
    """A cohort admin of one cohort who also holds a staff viewer role."""
    _, admin = cohort_admin_setup
    assign_role(
        UserFactory(superuser=True), admin, "organisation_staff_viewer", organisation
    )
    return admin


@pytest.mark.django_db
def test_a_cohort_admin_without_a_viewer_role_is_refused_the_staff_page(
    logged_in_client, organisation, cohort_admin_setup
):
    _, admin = cohort_admin_setup

    response = logged_in_client(admin).get(
        _interface_url(organisation.slug, "staff"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action_name", "extra"),
    [
        ("add_role", {}),
        ("deactivate_role", {"role": "cohort_viewer"}),
        ("change_cohorts", {"role": "cohort_viewer"}),
    ],
)
def test_a_cohort_admin_with_a_viewer_role_opens_the_row_actions_for_their_cohort(
    logged_in_client,
    organisation,
    cohort_admin_setup,
    viewing_cohort_admin,
    action_name,
    extra,
):
    cohort, _ = cohort_admin_setup
    colleague = _staff_member_holding("cohort_viewer", cohort)

    response = logged_in_client(viewing_cohort_admin).get(
        _interface_url(organisation.slug, f"staff/__actions/{action_name}"),
        {"user": str(colleague.pk), **extra},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200


@pytest.fixture
def colleague_with_roles_elsewhere(
    organisation: Organisation, cohort_admin_setup: tuple[Cohort, User]
) -> User:
    """A cohort viewer on the cohort admin's cohort ("Own group") who also
    holds roles the cohort admin has no say over."""
    own, _ = cohort_admin_setup
    own.name = "Own group"
    own.save()
    colleague = _staff_member_holding(
        "cohort_viewer", [own, _cohort(organisation, name="Far group")]
    )
    assign_role(
        UserFactory(superuser=True),
        colleague,
        "organisation_staff_viewer",
        organisation,
    )
    return colleague


@pytest.mark.django_db
def test_the_add_role_dialog_shows_a_names_only_viewer_the_roles_on_their_cohorts_alone(
    logged_in_client, organisation, viewing_cohort_admin, colleague_with_roles_elsewhere
):
    response = _add_role_dialog(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague_with_roles_elsewhere,
    )

    text = _text(response)
    assert "Now Cohort viewer: Own group Role" in text
    assert "Far group" not in text
    assert "Organisation staff viewer" not in text


@pytest.mark.django_db
def test_the_add_role_confirm_step_shows_a_names_only_viewer_the_roles_on_their_cohorts_alone(
    logged_in_client,
    organisation,
    cohort_admin_setup,
    viewing_cohort_admin,
    colleague_with_roles_elsewhere,
):
    own, _ = cohort_admin_setup

    response = _add_role(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague_with_roles_elsewhere,
        "cohort_admin",
        [own],
        confirmed="",
    )

    text = _text(response)
    assert "After Cohort admin: Own groupCohort viewer: Own group" in text
    assert "Far group" not in text
    assert "Organisation staff viewer" not in text


@pytest.mark.django_db
def test_the_add_role_dialog_shows_a_roles_viewer_every_role(
    admin_client, organisation, cohort_admin_setup, colleague_with_roles_elsewhere
):
    response = _add_role_dialog(
        admin_client, organisation, colleague_with_roles_elsewhere
    )

    text = _text(response)
    assert "Organisation staff viewer: Whole organisation" in text
    assert "Cohort viewer: Far group, Own group" in text


@pytest.mark.django_db
def test_the_deactivate_role_dialog_shows_a_names_only_viewer_the_roles_on_their_cohorts_alone(
    logged_in_client, organisation, viewing_cohort_admin, colleague_with_roles_elsewhere
):
    response = _remove_dialog(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague_with_roles_elsewhere,
        "cohort_viewer",
    )

    text = _text(response)
    assert "They lose Cohort viewer on Own group" in text
    assert "Far group" not in text
    assert "Organisation staff viewer" not in text


@pytest.mark.django_db
def test_the_deactivate_role_dialog_shows_a_roles_viewer_every_role_kept(
    admin_client, organisation, cohort_admin_setup, colleague_with_roles_elsewhere
):
    response = _remove_dialog(
        admin_client, organisation, colleague_with_roles_elsewhere, "cohort_viewer"
    )

    assert "Organisation staff viewer on Whole organisation" in _text(response)


@pytest.mark.django_db
def test_the_deactivate_role_dialog_is_404_for_a_role_the_viewer_cannot_give(
    logged_in_client, organisation, viewing_cohort_admin, colleague_with_roles_elsewhere
):
    response = _remove_dialog(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague_with_roles_elsewhere,
        "organisation_staff_viewer",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_change_cohorts_dialog_hides_cohorts_out_of_reach_from_a_names_only_viewer(
    logged_in_client, organisation, viewing_cohort_admin, colleague_with_roles_elsewhere
):
    response = _change_dialog(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague_with_roles_elsewhere,
    )

    text = _text(response)
    assert "Own group" in text
    assert "Far group" not in text


@pytest.mark.django_db
def test_the_change_cohorts_confirm_step_reads_as_a_deactivation_to_a_names_only_viewer(
    logged_in_client, organisation, viewing_cohort_admin, colleague_with_roles_elsewhere
):
    response = _change(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague_with_roles_elsewhere,
        [],
        confirmed=False,
    )

    text = _text(response)
    assert "Deactivate Cohort viewer for" in text
    assert "Far group" not in text


@pytest.mark.django_db
def test_add_role_answers_403_for_a_cohort_the_cohort_admin_cannot_give(
    logged_in_client, organisation, cohort_admin_setup, viewing_cohort_admin
):
    own, _ = cohort_admin_setup
    foreign = _cohort(organisation)
    colleague = _staff_member_holding("cohort_viewer", own)

    response = _add_role(
        logged_in_client(viewing_cohort_admin),
        organisation,
        colleague,
        "cohort_admin",
        [foreign],
    )

    assert response.status_code == 403
    assert ("cohort_admin", str(foreign.pk)) not in _active_roles(colleague)


@pytest.mark.django_db
def test_a_cohort_admin_may_add_a_cohort_role_to_themselves_on_their_cohort(
    logged_in_client, organisation, cohort_admin_setup, viewing_cohort_admin
):
    cohort, _ = cohort_admin_setup

    response = _add_role(
        logged_in_client(viewing_cohort_admin),
        organisation,
        viewing_cohort_admin,
        "cohort_viewer",
        [cohort],
    )

    assert response.status_code == 204
    assert ("cohort_viewer", str(cohort.pk)) in _active_roles(viewing_cohort_admin)


@pytest.mark.django_db
def test_an_organisation_admin_adds_a_role_to_themselves(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, me = _holder_client(logged_in_client, organisation)

    response = _add_role(client, organisation, me, "cohort_viewer", [cohort])

    assert response.status_code == 204
    assert ("cohort_viewer", str(cohort.pk)) in _active_roles(me)


def _remove_staff_from_cohort_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation,
        cohort,
        "/__tabs/settings/__panels/staff/__actions/remove_staff_from_cohort",
    )


def _remove_staff_from_cohort(
    client: Client, organisation: Organisation, cohort: Cohort, user: User, role: str
):
    return _post(
        client,
        _remove_staff_from_cohort_url(organisation, cohort),
        {"user": str(user.pk), "role": role},
    )


@pytest.mark.django_db
def test_removing_from_a_cohort_deactivates_that_cohorts_role_only(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    other = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", [cohort, other])

    response = _remove_staff_from_cohort(
        admin_client, organisation, cohort, user, "cohort_viewer"
    )

    assert response.status_code == 204
    assert _active_roles(user) == {("cohort_viewer", str(other.pk))}
    assert AuditLogEntry.unscoped.filter(action="role.deactivated").count() == 1


@pytest.mark.django_db
def test_a_cohort_admin_who_cannot_see_staff_stays_on_the_cohort_after_removing_someone(
    logged_in_client, organisation
):
    """A cohort admin never saw the Staff section, so a change made on a
    cohort's Settings tab keeps them there."""
    cohort = _cohort(organisation)
    client, _admin = _holder_client(logged_in_client, cohort, "cohort_admin")
    user = _staff_member_holding("cohort_viewer", cohort)

    response = _remove_staff_from_cohort(
        client, organisation, cohort, user, "cohort_viewer"
    )

    assert response.status_code == 204
    assert "HX-Redirect" not in response


@pytest.mark.django_db
def test_removing_from_a_cohort_announces_the_staff_change(admin_client, organisation):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)

    response = _remove_staff_from_cohort(
        admin_client, organisation, cohort, user, "cohort_viewer"
    )

    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}


@pytest.mark.django_db
def test_the_remove_from_cohort_dialog_names_the_person_the_role_and_the_cohort(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding(
        "cohort_viewer", cohort, first_name="Ada", last_name="Lovelace"
    )

    response = admin_client.get(
        _remove_staff_from_cohort_url(organisation, cohort),
        {"user": str(user.pk), "role": "cohort_viewer"},
        HTTP_HX_REQUEST="true",
    )

    text = _text(response)
    assert "Remove Ada Lovelace from Evening group?" in text
    assert (
        "Ada Lovelace will lose Cohort viewer on Evening group. "
        "Their other roles are unchanged." in text
    )


@pytest.mark.django_db
def test_removing_a_deactivated_cohort_role_answers_the_unavailable_fragment(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    deactivate_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)

    response = _remove_staff_from_cohort(
        admin_client, organisation, cohort, user, "cohort_viewer"
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_removing_a_user_outside_the_staff_from_a_cohort_is_404(
    admin_client, organisation
):
    cohort = _cohort(organisation)

    response = _remove_staff_from_cohort(
        admin_client, organisation, cohort, UserFactory(), "cohort_viewer"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_removing_an_organisation_role_from_a_cohort_is_404(admin_client, organisation):
    cohort = _cohort(organisation)
    user = _staff_member_holding("organisation_admin", organisation)

    response = _remove_staff_from_cohort(
        admin_client, organisation, cohort, user, "organisation_admin"
    )

    assert response.status_code == 404
    assert _active_roles(user) == {("organisation_admin", str(organisation.pk))}


@pytest.mark.django_db
def test_removing_a_role_the_actor_may_not_grant_from_a_cohort_is_403(
    admin_client, organisation, monkeypatch
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_admin", cohort)
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles_for",
        lambda request: [GrantableRole("cohort_viewer", (cohort,))],
    )

    response = _remove_staff_from_cohort(
        admin_client, organisation, cohort, user, "cohort_admin"
    )

    assert response.status_code == 403
    assert _active_roles(user) == {("cohort_admin", str(cohort.pk))}


@pytest.mark.django_db
def test_a_cohort_admin_may_remove_themselves_from_their_cohort(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, me = _holder_client(logged_in_client, cohort, "cohort_admin")

    response = _remove_staff_from_cohort(
        client, organisation, cohort, me, "cohort_admin"
    )

    assert response.status_code == 204
    assert _active_roles(me) == set()


def _change_role_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/settings/__panels/staff/__actions/change_role"
    )


def _change_role(
    client: Client,
    organisation: Organisation,
    cohort: Cohort,
    user: User,
    role: str,
    new_role: str,
    **extra: str,
):
    return _post(
        client,
        _change_role_url(organisation, cohort),
        {"user": str(user.pk), "role": role, "new_role": new_role, **extra},
    )


@pytest.mark.django_db
def test_changing_a_role_writes_deactivation_then_assignment_by_the_same_actor(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, actor = _holder_client(logged_in_client, organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    earlier = set(AuditLogEntry.unscoped.values_list("pk", flat=True))

    response = _change_role(
        client,
        organisation,
        cohort,
        user,
        "cohort_viewer",
        "cohort_admin",
        confirmed="1",
    )

    assert response.status_code == 204
    assert _active_roles(user) == {("cohort_admin", str(cohort.pk))}
    entries = list(
        AuditLogEntry.unscoped.exclude(pk__in=earlier).order_by("created_at", "pk")
    )
    assert [entry.action for entry in entries] == ["role.assigned", "role.deactivated"]
    assert {entry.actor for entry in entries} == {actor}


@pytest.mark.django_db
def test_changing_a_role_announces_the_staff_change(admin_client, organisation):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)

    response = _change_role(
        admin_client,
        organisation,
        cohort,
        user,
        "cohort_viewer",
        "cohort_admin",
        confirmed="1",
    )

    assert json.loads(response["HX-Trigger"])[STAFF_CHANGED] == {"ids": [str(user.pk)]}


@pytest.mark.django_db
def test_changing_a_role_without_confirming_asks_first_and_changes_nothing(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding(
        "cohort_viewer", cohort, first_name="Ada", last_name="Lovelace"
    )

    response = _change_role(
        admin_client, organisation, cohort, user, "cohort_viewer", "cohort_admin"
    )

    assert response.status_code == 200
    assert "Ada Lovelace will become Cohort admin on Evening group only." in _text(
        response
    )
    assert _active_roles(user) == {("cohort_viewer", str(cohort.pk))}


@pytest.mark.django_db
def test_choosing_the_held_role_answers_422(admin_client, organisation):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding(
        "cohort_viewer", cohort, first_name="Ada", last_name="Lovelace"
    )

    response = _change_role(
        admin_client,
        organisation,
        cohort,
        user,
        "cohort_viewer",
        "cohort_viewer",
        confirmed="1",
    )

    assert response.status_code == 422
    assert "Ada Lovelace already holds Cohort viewer on Evening group." in _text(
        response
    )


@pytest.mark.django_db
def test_choosing_a_role_outside_the_choices_answers_422(admin_client, organisation):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)

    response = _change_role(
        admin_client,
        organisation,
        cohort,
        user,
        "cohort_viewer",
        "organisation_admin",
        confirmed="1",
    )

    assert response.status_code == 422
    assert _active_roles(user) == {("cohort_viewer", str(cohort.pk))}


@pytest.mark.django_db
def test_changing_to_a_role_outside_the_actors_reach_is_403_and_keeps_the_original(
    admin_client, organisation, monkeypatch
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles_for",
        lambda request: [GrantableRole("cohort_viewer", (cohort,))],
    )

    response = _change_role(
        admin_client,
        organisation,
        cohort,
        user,
        "cohort_viewer",
        "cohort_admin",
        confirmed="1",
    )

    assert response.status_code == 403
    assert _active_roles(user) == {("cohort_viewer", str(cohort.pk))}


@pytest.mark.django_db
def test_a_cohort_admin_may_change_their_own_role_on_their_cohort(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, me = _holder_client(logged_in_client, cohort, "cohort_admin")

    response = _change_role(
        client, organisation, cohort, me, "cohort_admin", "cohort_viewer", confirmed="1"
    )

    assert response.status_code == 204
    assert _active_roles(me) == {("cohort_viewer", str(cohort.pk))}


@pytest.mark.django_db
def test_changing_a_deactivated_role_answers_the_unavailable_fragment(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _staff_member_holding("cohort_viewer", cohort)
    deactivate_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)

    response = _change_role(
        admin_client, organisation, cohort, user, "cohort_viewer", "cohort_admin"
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_the_change_role_dialog_offers_only_grantable_cohort_roles_with_the_held_one_checked(
    admin_client, organisation, monkeypatch
):
    cohort = _cohort(organisation, name="Evening group")
    user = _staff_member_holding(
        "cohort_viewer", cohort, first_name="Ada", last_name="Lovelace"
    )
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles_for",
        lambda request: [
            GrantableRole("cohort_viewer", (cohort,)),
            GrantableRole("cohort_admin", (cohort,)),
            GrantableRole("organisation_admin", None),
        ],
    )

    response = admin_client.get(
        _change_role_url(organisation, cohort),
        {"user": str(user.pk), "role": "cohort_viewer"},
        HTTP_HX_REQUEST="true",
    )

    document = lxml.html.fromstring(response.content.decode())
    radios = {
        radio.get("value"): radio.get("checked") is not None
        for radio in document.cssselect("input[type=radio][name=new_role]")
    }
    assert radios == {"cohort_viewer": True, "cohort_admin": False}
    assert "Change Ada Lovelace's role on Evening group?" in _text(response)


@pytest.mark.django_db
def test_a_refused_role_change_is_a_message_dialog(
    admin_client, organisation, monkeypatch
):
    UserFactory(email="ada@example.com")

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.SELF)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.assign_role", refuse
    )

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    _assert_message_dialog(
        response,
        "This change wasn't made",
        "You can't change your own roles. Ask another organisation admin.",
    )
