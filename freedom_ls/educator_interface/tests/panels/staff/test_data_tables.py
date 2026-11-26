"""Tests for the Staff table."""

from __future__ import annotations

from typing import TYPE_CHECKING

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _hold,
    _interface_url,
    _staff_document,
    _staff_member_row,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    StaffMember,
)
from freedom_ls.learner_management.role_assignment import GrantableRole, assign_role
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper


def _grant_staff_member(
    target: Organisation | Cohort, role: str = "organisation_admin", **user_fields: str
) -> None:
    assign_role(UserFactory(superuser=True), UserFactory(**user_fields), role, target)


@pytest.mark.django_db
def test_an_organisation_admin_sees_each_members_name_and_email(role_holder_client):
    organisation = OrganisationFactory()
    _grant_staff_member(
        organisation, first_name="Ada", last_name="Lovelace", email="ada@example.com"
    )
    client = role_holder_client(organisation, "organisation_admin")

    text = _get_document(client, _interface_url(organisation.slug, "staff"))

    assert "Ada Lovelace" in text.text_content()
    assert "ada@example.com" in text.text_content()


@pytest.mark.django_db
def test_a_nameless_member_shows_the_email_alone(role_holder_client):
    organisation = OrganisationFactory()
    _grant_staff_member(
        organisation, first_name="", last_name="", email="bare@example.com"
    )
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(client, _interface_url(organisation.slug, "staff"))

    names = [
        e.text_content() for e in document.cssselect("#main-content span.truncate")
    ]
    assert "bare@example.com" in names
    assert not document.cssselect("#main-content span.truncate.text-muted")


@pytest.mark.django_db
def test_a_member_name_is_escaped(role_holder_client):
    organisation = OrganisationFactory()
    _grant_staff_member(organisation, first_name="<b>x</b>")
    client = role_holder_client(organisation, "organisation_admin")

    response = client.get(_interface_url(organisation.slug, "staff"))

    assert "&lt;b&gt;x&lt;/b&gt;" in response.content.decode()
    assert "<b>x</b>" not in response.content.decode()


def _scope_lines(row) -> list[str]:
    return [e.text_content().strip() for e in row.cssselect("ul li span[title]")]


# Measured for a page of ten: the count must not grow with the number of rows.
QUERY_BOUND = 66


MARKERS = {"You", "Inactive", "Account inactive", "Also a learner"}


def _marker_labels(row) -> set[str]:
    return {e.text_content().strip() for e in row.cssselect("span")} & MARKERS


@pytest.mark.django_db
def test_an_organisation_admins_roles_cell_reads_whole_organisation(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="boss@example.com"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "boss@example.com")

    assert _scope_lines(row) == ["Whole organisation"]
    assert "Organisation admin" in row.text_content()


@pytest.mark.django_db
def test_two_cohorts_read_both_names(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="two@example.com")
    for name in ("Alpha", "Bravo"):
        _hold(user, "cohort_admin", CohortFactory(organisation=organisation, name=name))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "two@example.com")

    assert _scope_lines(row) == ["Alpha, Bravo"]


@pytest.mark.django_db
def test_four_cohorts_read_two_names_and_the_rest_as_a_count(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="four@example.com")
    for name in ("Alpha", "Bravo", "Charlie", "Delta"):
        _hold(
            user, "cohort_viewer", CohortFactory(organisation=organisation, name=name)
        )
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "four@example.com")

    (scope,) = row.cssselect("ul li span[title]")
    assert scope.text_content().strip() == "Alpha, Bravo +2 more"
    assert scope.get("title") == "Alpha, Bravo, Charlie, Delta"


@pytest.mark.django_db
def test_an_inactive_cohort_carries_the_inactive_marker(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Old", is_active=False)
    _hold(UserFactory(email="old@example.com"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "old@example.com")

    assert _scope_lines(row) == ["Old (inactive)"]


def _make_viewer_and_subject(role_holder_client, organisation, case: str):
    """Returns (client, email of the row to inspect) for a marker case."""
    subject = UserFactory(email="subject@example.com")
    _hold(subject, "cohort_viewer", CohortFactory(organisation=organisation))
    viewer_client = role_holder_client(organisation, "organisation_admin")
    if case == "membership_inactive":
        StaffMember.objects.filter(user=subject).update(is_active=False)
    elif case == "account_inactive":
        subject.is_active = False
        subject.save()
    elif case == "learner":
        LearnerFactory(user=subject, organisation=organisation)
    elif case == "inactive_learner":
        LearnerFactory(user=subject, organisation=organisation, is_active=False)
    return viewer_client


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("plain", set()),
        ("membership_inactive", {"Inactive"}),
        ("account_inactive", {"Account inactive"}),
        ("learner", {"Also a learner"}),
        ("inactive_learner", set()),
    ],
)
def test_each_marker_appears_for_its_case_only(role_holder_client, case, expected):
    organisation = OrganisationFactory()
    client = _make_viewer_and_subject(role_holder_client, organisation, case)

    row = _staff_member_row(
        _staff_document(client, organisation), "subject@example.com"
    )

    assert _marker_labels(row) == expected


@pytest.mark.django_db
def test_the_inactive_marker_is_muted(role_holder_client):
    organisation = OrganisationFactory()
    client = _make_viewer_and_subject(
        role_holder_client, organisation, "membership_inactive"
    )

    row = _staff_member_row(
        _staff_document(client, organisation), "subject@example.com"
    )

    (marker,) = [
        e
        for e in row.cssselect("[data-tone]")
        if e.text_content().strip() == "Inactive"
    ]
    assert marker.get("data-tone") == "muted"


@pytest.mark.django_db
def test_the_viewers_own_row_is_marked_you(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")
    document = _staff_document(client, organisation)

    (row,) = document.cssselect("#main-content tbody tr")

    assert _marker_labels(row) == {"You"}


@pytest.mark.django_db
def test_a_staff_viewer_sees_names_and_no_roles_or_buttons(role_holder_client):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="subject@example.com", first_name="Sam", last_name="Subject"),
        "organisation_admin",
        organisation,
    )
    client = role_holder_client(organisation, "organisation_staff_viewer")

    response = client.get(_interface_url(organisation.slug, "staff"))
    document = lxml.html.fromstring(response.content)

    assert response.status_code == 200
    assert "Sam Subject" in document.text_content()
    assert (
        "Organisation admin"
        not in document.cssselect("#main-content tbody")[0].text_content()
    )
    assert document.cssselect("#main-content tbody button[hx-get]") == []


@pytest.mark.django_db
def test_the_staff_page_lists_only_the_roles_the_site_defines(
    mock_site_context: Site, settings: SettingsWrapper, role_holder_client
):
    organisation = OrganisationFactory()
    without = frozenset(
        {
            "organisation_staff_viewer",
            "organisation_staff_roles_viewer",
            "question_bank_viewer",
        }
    )
    with custom_role_config(mock_site_context, settings, without=without):
        client = role_holder_client(organisation, "organisation_admin")

        document = _staff_document(client, organisation)

    (role_filter,) = document.cssselect("select[name=staff-role]")
    assert [option.get("value") for option in role_filter.cssselect("option")] == [
        "all",
        "organisation_admin",
        "cohort_admin",
        "cohort_viewer",
    ]


@pytest.mark.django_db
def test_a_roles_viewer_sees_role_names_and_no_buttons(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="subject@example.com"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_staff_roles_viewer")

    document = _staff_document(client, organisation)
    row = _staff_member_row(document, "subject@example.com")

    assert "Organisation admin" in row.text_content()
    assert row.cssselect("button[hx-get]") == []


@pytest.mark.django_db
def test_a_staff_member_with_no_staff_member_row_is_inactive(role_holder_client):
    organisation = OrganisationFactory()
    subject = UserFactory(email="subject@example.com")
    _hold(subject, "organisation_admin", organisation)
    StaffMember.objects.filter(user=subject).delete()
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(
        _staff_document(client, organisation), "subject@example.com"
    )

    assert _marker_labels(row) == {"Inactive"}


@pytest.mark.django_db
def test_a_superuser_holding_one_cohort_role_shows_that_role_only(role_holder_client):
    organisation = OrganisationFactory()
    superuser = UserFactory(superuser=True, email="super@example.com")
    _hold(superuser, "cohort_viewer", CohortFactory(organisation=organisation))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "super@example.com")

    roles = row.cssselect("ul")[0]
    assert len(roles.cssselect("li")) == 1
    assert "Cohort viewer" in roles.text_content()


@pytest.mark.django_db
def test_a_cohort_name_is_escaped_in_the_scope(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="<i>x</i>")
    _hold(UserFactory(), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    content = client.get(_interface_url(organisation.slug, "staff")).content.decode()

    assert "&lt;i&gt;x&lt;/i&gt;" in content
    assert "<i>x</i>" not in content


@pytest.mark.django_db
def test_a_full_page_of_members_stays_within_a_fixed_query_bound(
    role_holder_client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    for _ in range(10):
        user = UserFactory()
        _hold(user, "organisation_admin", organisation, grantor)
        _hold(user, "cohort_viewer", CohortFactory(organisation=organisation), grantor)
        LearnerFactory(user=user, organisation=organisation)
    client = role_holder_client(organisation, "organisation_admin")
    url = _interface_url(organisation.slug, "staff")

    with django_assert_max_num_queries(QUERY_BOUND):
        response = client.get(url)

    assert response.status_code == 200
    assert (
        len(
            lxml.html.fromstring(response.content.decode()).cssselect(
                "#main-content tbody tr"
            )
        )
        == 10
    )


def _member_emails(document) -> list[str]:
    return [
        row.cssselect("td")[0].text_content()
        for row in document.cssselect("#main-content tbody tr")
    ]


def _members_search(client: Client, organisation: Organisation, term: str):
    return _get_document(
        client, _interface_url(organisation.slug, "staff") + f"?staff-q={term}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term", ["Wanjiru", "Kamau", "wanjiru.k@"], ids=["first", "last", "email"]
)
def test_members_search_matches_first_name_last_name_and_email(
    role_holder_client, term
):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(first_name="Wanjiru", last_name="Kamau", email="wanjiru.k@x.org"),
        "organisation_admin",
        organisation,
    )
    _hold(UserFactory(email="other@x.org"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    document = _members_search(client, organisation, term)

    (row,) = document.cssselect("#main-content tbody tr")
    assert "wanjiru.k@x.org" in row.text_content()


@pytest.mark.django_db
def test_the_role_filter_narrows_the_members_page(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="viewer@x.org"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "staff") + "?staff-role=cohort_viewer",
    )

    (row,) = document.cssselect("#main-content tbody tr")
    assert "viewer@x.org" in row.text_content()


@pytest.mark.django_db
def test_the_role_filter_narrows_the_staff_page_to_question_bank_viewers(
    role_holder_client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="bank@x.org"), "question_bank_viewer", organisation)
    _hold(UserFactory(email="viewer@x.org"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "staff") + "?staff-role=question_bank_viewer",
    )

    (row,) = document.cssselect("#main-content tbody tr")
    assert "bank@x.org" in row.text_content()


@pytest.mark.django_db
def test_a_question_bank_viewer_is_listed_with_its_role_name(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="bank@x.org"), "question_bank_viewer", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    document = _staff_document(client, organisation)
    row = _staff_member_row(document, "bank@x.org")

    assert "Question bank viewer" in row.text_content()


@pytest.mark.django_db
def test_picking_a_role_from_the_default_drops_all_roles_from_its_link(
    role_holder_client,
):
    """From the default "All roles" state, a role's choice link selected only
    that role instead of keeping "All roles" beside it."""
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _staff_document(client, organisation)

    (link,) = [
        a
        for a in document.cssselect("details a")
        if a.text_content().strip() == "Cohort admin"
    ]
    assert link.get("href").endswith("?staff-role=cohort_admin")


@pytest.mark.django_db
def test_the_mobile_role_select_has_a_single_all_roles_option(role_holder_client):
    """The mobile Role select listed both a blank "All" and "All roles"."""
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _staff_document(client, organisation)

    (select,) = document.cssselect("select[name=staff-role]")
    labels = [o.text_content().strip() for o in select.cssselect("option")]
    assert labels[:2] == ["All roles", "Organisation admin"]


@pytest.mark.django_db
def test_the_member_header_first_links_to_descending_first_name(role_holder_client):
    """The list already arrives by first name, so the first click flips it."""
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(client, _interface_url(organisation.slug, "staff"))

    (link,) = document.xpath("//thead//a[normalize-space()='Staff member']")
    assert "staff-sort=-first_name" in link.get("href")


@pytest.mark.django_db
def test_a_search_with_no_match_says_so_and_offers_to_clear_filters(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _members_search(client, organisation, "nobody-has-this-name")

    (cell,) = document.cssselect("#main-content tbody td")
    (link,) = cell.cssselect("a")
    assert (
        cell.text_content().split("Clear filters")[0].strip()
        == "No staff members match these filters."
    )
    assert "staff-q" not in link.get("href")


@pytest.mark.django_db
def test_a_filter_with_no_match_says_so(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "staff") + "?staff-role=cohort_viewer",
    )

    (cell,) = document.cssselect("#main-content tbody td")
    assert "No staff members match these filters." in cell.text_content()


@pytest.mark.django_db
def test_an_organisation_with_no_members_says_so(mock_site_context, logged_in_client):
    organisation = OrganisationFactory()
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", mock_site_context
    )

    document = _staff_document(logged_in_client(site_admin), organisation)

    (cell,) = document.cssselect("#main-content tbody td")
    assert "No staff yet." in cell.text_content()
    assert "Add staff member" in cell.text_content()


@pytest.mark.django_db
def test_an_organisation_admins_own_row_offers_role_triggers_but_no_state_trigger(
    role_holder_client,
):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True, email="me@example.com")
    assign_role(UserFactory(superuser=True), viewer, "organisation_admin", organisation)
    client = Client()
    client.force_login(viewer)

    row = _staff_member_row(_staff_document(client, organisation), "me@example.com")

    urls = [button.get("hx-get") for button in row.cssselect("button[hx-get]")]
    assert any("add_role" in url for url in urls)
    assert any("deactivate_role" in url for url in urls)
    assert not any(
        url.split("?")[0].endswith(("/deactivate", "/reactivate")) for url in urls
    )
    assert not row.cssselect("[aria-label='Locked']")


def _remove_triggers(row) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if "deactivate_role" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_a_cohort_admins_own_row_offers_the_roles_they_may_give(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    viewer = UserFactory(staff=True, email="me@example.com")
    superuser = UserFactory(superuser=True)
    assign_role(superuser, viewer, "cohort_admin", cohort)
    assign_role(superuser, viewer, "organisation_staff_roles_viewer", organisation)
    client = Client()
    client.force_login(viewer)

    row = _staff_member_row(_staff_document(client, organisation), "me@example.com")

    labels = {b.text_content().strip() for b in row.cssselect("button[hx-get]")}
    assert {"Add role", "Deactivate role"} <= labels
    assert "Deactivate staff member" not in labels
    assert "You can't change your own roles" not in row.text_content()


@pytest.mark.django_db
def test_another_members_entry_offers_remove_to_an_organisation_admin(
    role_holder_client,
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    cohort = CohortFactory(organisation=organisation)
    _hold(user, "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _remove_triggers(row)
    assert f"user={user.pk}&role=cohort_viewer" in trigger


def _change_cohorts_triggers(row) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if "change_cohorts" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_a_cohort_role_entry_offers_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _change_cohorts_triggers(row)
    assert f"user={user.pk}&role=cohort_viewer" in trigger


@pytest.mark.django_db
def test_an_organisation_admin_entry_offers_no_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="boss@example.com"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "boss@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_viewer_role_entry_offers_no_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="watcher@example.com"),
        "organisation_staff_roles_viewer",
        organisation,
    )
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(
        _staff_document(client, organisation), "watcher@example.com"
    )

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_role_the_viewer_may_not_give_has_no_change_cohorts(
    role_holder_client, monkeypatch
):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="other@example.com"),
        "cohort_viewer",
        CohortFactory(organisation=organisation),
    )
    client = role_holder_client(organisation, "organisation_admin")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_turned_off_accounts_row_has_no_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="off@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    User.objects.filter(pk=user.pk).update(is_active=False)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "off@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_an_entry_the_viewer_may_not_revoke_has_no_remove(
    role_holder_client, monkeypatch
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="other@example.com"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.panels.staff.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    assert _remove_triggers(row) == []


@pytest.mark.django_db
def test_a_turned_off_accounts_row_offers_remove_and_nothing_else(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="off@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    User.objects.filter(pk=user.pk).update(is_active=False)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "off@example.com")

    assert len(row.cssselect("button[hx-get]")) == 1
    assert len(_remove_triggers(row)) == 1


def _state_triggers(row, action: str) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if f"__actions/{action}?" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_an_active_member_row_offers_deactivate_and_not_reactivate(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _state_triggers(row, "deactivate")
    assert f"user={user.pk}" in trigger
    assert _state_triggers(row, "reactivate") == []


@pytest.mark.django_db
@pytest.mark.parametrize("row_state", ["inactive", "missing"])
def test_an_inactive_member_row_offers_reactivate_and_not_deactivate(
    role_holder_client, row_state
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    members = StaffMember.objects.filter(user=user)
    if row_state == "inactive":
        members.update(is_active=False)
    else:
        members.delete()
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _state_triggers(row, "reactivate")
    assert f"user={user.pk}" in trigger
    assert _state_triggers(row, "deactivate") == []


def _make_site_level(user: User, organisation: Organisation) -> None:
    assign_role(UserFactory(superuser=True), user, "site_admin", organisation.site)


def _turn_off(user: User, organisation: Organisation) -> None:
    User.objects.filter(pk=user.pk).update(is_active=False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prepare", [_make_site_level, _turn_off], ids=["site_level", "turned_off"]
)
def test_a_site_level_or_turned_off_row_offers_neither_state_action(
    role_holder_client, prepare
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    prepare(user, organisation)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    assert _state_triggers(row, "deactivate") == []
    assert _state_triggers(row, "reactivate") == []


@pytest.mark.django_db
def test_the_viewers_own_row_offers_neither_state_action(role_holder_client):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True, email="me@example.com")
    assign_role(UserFactory(superuser=True), viewer, "organisation_admin", organisation)
    client = Client()
    client.force_login(viewer)

    row = _staff_member_row(_staff_document(client, organisation), "me@example.com")

    assert _state_triggers(row, "deactivate") == []
    assert _state_triggers(row, "reactivate") == []
