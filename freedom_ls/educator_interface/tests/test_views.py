"""The educator interface shell: navigation, breadcrumbs, the interface root, the routes it no longer serves, the browser-tab title, the organisation switcher and the sidebar."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import lxml.html
import pytest
import pytest_django.fixtures

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.messages import get_messages
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sites.models import Site
from django.core.handlers.wsgi import WSGIRequest
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.panels.common.request import (
    LAST_ORGANISATION_SESSION_KEY,
)
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _interface_url,
    _msg_conversation,
    _msg_educator,
    _msg_learner,
    _msg_url,
    messages_section,
)
from freedom_ls.educator_interface.views import interface
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


@pytest.mark.django_db
def test_an_instance_page_marks_its_section_current_without_naming_the_instance(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("#sidebar-nav")
    (current,) = nav.cssselect("a[aria-current]")
    assert current.text_content().strip().startswith("Cohorts")
    assert current.get("aria-current") == "true"
    assert "Evening group" not in nav.text_content()


@pytest.mark.django_db
def test_an_instance_page_offers_a_back_link_to_its_list(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (back,) = document.cssselect("#breadcrumbs a")
    assert back.get("href") == _interface_url(organisation.slug, "cohorts")
    assert back.text_content().strip() == "Cohorts"


@pytest.mark.django_db
def test_a_list_page_shows_no_breadcrumb(staff_client: Client):
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    assert not document.cssselect("#breadcrumbs a")
    assert not document.cssselect("#breadcrumbs nav")


@pytest.mark.django_db
def test_navigation_toggle_shows_a_menu_icon_not_a_panel_chevron(
    staff_client: Client,
):
    """The content header's navigation toggle drew a chevron instead of a menu icon."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (icon,) = toggle.cssselect("svg")
    assert icon.get("data-icon") == "menu"


@pytest.mark.django_db
def test_navigation_toggle_sits_in_the_page_heading_row(staff_client: Client):
    """On mobile the toggle took a row of its own above the page heading."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (heading,) = document.cssselect("#main-content h1")
    assert toggle.getparent() is heading.getparent().getparent()


@pytest.mark.django_db
def test_organisation_root_page_still_offers_the_navigation_toggle(
    staff_client: Client,
):
    """The organisation root used to render a page with no heading of its
    own, leaving a phone with no way to open the navigation. It now sends the
    visitor to a section, and the page they land on offers the toggle."""
    organisation = OrganisationFactory()

    response = staff_client.get(_interface_url(organisation.slug, ""), follow=True)
    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())

    (toggle,) = document.cssselect(
        "#main-content button[aria-label='Open navigation panel']"
    )
    assert toggle.cssselect("svg[data-icon]")


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_a_cohort_role_holder_sees_no_administration_group(role_holder_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, role)

    document = _get_document(client, _interface_url(organisation.slug, "cohorts"))

    headings = [h.text_content().strip() for h in document.cssselect("#sidebar-nav h2")]
    assert headings == ["Teaching"]


@pytest.mark.django_db
def test_a_cohort_admin_still_sees_the_dashboard(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_admin")

    response = client.get(_interface_url(organisation.slug, ""))

    assert response.status_code == 302
    assert response["Location"] == _interface_url(organisation.slug, "dashboard")


# The educator interface has no Messages section: the conversation with a
# learner lives on the learner page.


@pytest.mark.django_db
@messages_section
@pytest.mark.parametrize("messaging_enabled", [True, False])
def test_the_messages_section_paths_are_404s(
    msg_client_for, settings, messaging_enabled
):
    settings.MESSAGING_ENABLED = messaging_enabled
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    client = msg_client_for(educator)

    assert client.get(_msg_url(organisation, "messages")).status_code == 404
    assert (
        client.get(_msg_url(organisation, f"messages/{conversation.pk}")).status_code
        == 404
    )


def test_the_unread_count_route_no_longer_exists():
    with pytest.raises(NoReverseMatch):
        reverse(
            "educator_interface:messages_unread_count",
            kwargs={"organisation_slug": "any"},
        )


@pytest.fixture
def cohorts_page(
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> tuple[Client, str, Organisation]:
    """An educator logged in against one organisation, plus its cohorts URL."""
    organisation = cast(Organisation, OrganisationFactory(name="Northside Academy"))
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_admin")
    url = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
    )
    return logged_in_client(educator), url, organisation


def _title_text(html: str) -> str:
    """The text inside the response's <title> element, whitespace stripped."""
    return html.split("<title>")[1].split("</title>")[0].strip()


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
def test_full_page_load_titles_the_tab_with_page_organisation_and_site(
    cohorts_page: tuple[Client, str, Organisation], mock_site_context: Site
) -> None:
    client, url, organisation = cohorts_page

    response = client.get(url)

    assert response.status_code == 200
    title = _title_text(response.content.decode())
    assert title == f"Cohorts — {organisation.name} — {mock_site_context.name}"


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
def test_htmx_navigation_title_matches_the_full_page_title(
    cohorts_page: tuple[Client, str, Organisation],
) -> None:
    """The base template's head block and the out-of-band navigation fragment
    are two separate code paths that must agree. What the shared title should
    actually say is pinned by the full-page test above."""
    client, url, _organisation = cohorts_page

    full_page = client.get(url)
    navigation = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="main-content")

    assert _title_text(navigation.content.decode()) == _title_text(
        full_page.content.decode()
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
def test_instance_page_title_names_the_cohort(
    cohorts_page: tuple[Client, str, Organisation], mock_site_context: Site
) -> None:
    """A cohort's page used to title the tab with only the organisation and
    site, because the instance label never reached the document title."""
    client, _url, organisation = cohorts_page
    cohort = CohortFactory(name="Tab Title Cohort", organisation=organisation)
    url = reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )

    full_page = client.get(url)
    navigation = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="main-content")

    expected = f"Tab Title Cohort — {organisation.name} — {mock_site_context.name}"
    assert _title_text(full_page.content.decode()) == expected
    assert _title_text(navigation.content.decode()) == expected


def _remember(client: Client, organisation_slug: str) -> None:
    session = client.session
    session[LAST_ORGANISATION_SESSION_KEY] = organisation_slug
    session.save()


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestInterfaceRoot:
    def test_no_accessible_organisations_404s(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        client = logged_in_client(UserFactory(staff=True))

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "role", ["organisation_staff_viewer", "organisation_staff_roles_viewer"]
    )
    def test_someone_who_sees_staff_alone_is_sent_to_the_staff_section(
        self, logged_in_client: Callable[[AbstractBaseUser], Client], role: str
    ) -> None:
        user = UserFactory(staff=True)
        organisation = OrganisationFactory()
        assign_object_role(user, organisation, role)
        client = logged_in_client(user)

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 302
        assert response["Location"] == _interface_url(organisation.slug, "staff")

    def test_falls_back_to_first_accessible_when_nothing_remembered(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        user = UserFactory(staff=True)
        organisation_a = OrganisationFactory(name="Alpha")
        organisation_b = OrganisationFactory(name="Beta")
        assign_object_role(user, organisation_a, "organisation_admin")
        assign_object_role(user, organisation_b, "organisation_admin")
        client = logged_in_client(user)

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 302
        assert response["Location"] == _interface_url(organisation_a.slug, "dashboard")

    def test_redirects_to_the_remembered_organisation_over_the_alphabetical_default(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        user = UserFactory(staff=True)
        organisation_a = OrganisationFactory(name="Alpha")
        organisation_b = OrganisationFactory(name="Beta")
        assign_object_role(user, organisation_a, "organisation_admin")
        assign_object_role(user, organisation_b, "organisation_admin")
        client = logged_in_client(user)
        _remember(client, organisation_b.slug)

        response = client.get(reverse("educator_interface:root"))

        assert response["Location"] == _interface_url(organisation_b.slug, "dashboard")

    def test_remembered_organisation_is_ignored_if_no_longer_accessible(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        """The session value is only ever a hint — it is re-checked against
        what the user can currently access, never trusted on its own."""
        user = UserFactory(staff=True)
        accessible = OrganisationFactory(name="Accessible")
        inaccessible = OrganisationFactory(name="Inaccessible")
        assign_object_role(user, accessible, "organisation_admin")
        client = logged_in_client(user)
        _remember(client, inaccessible.slug)

        response = client.get(reverse("educator_interface:root"))

        assert response["Location"] == _interface_url(accessible.slug, "dashboard")


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestBareOrganisationUrl:
    """/educator/organisations/<slug>/ names no section, so it sends the
    visitor to the first one their roles show."""

    @pytest.mark.parametrize(
        ("role", "section"),
        [("organisation_staff_viewer", "staff"), ("organisation_admin", "dashboard")],
    )
    def test_sends_the_visitor_to_the_first_section_they_can_see(
        self,
        logged_in_client: Callable[[AbstractBaseUser], Client],
        role: str,
        section: str,
    ) -> None:
        user = UserFactory(staff=True)
        organisation = OrganisationFactory()
        assign_object_role(user, organisation, role)
        client = logged_in_client(user)

        response = client.get(_interface_url(organisation.slug, ""))

        assert response.status_code == 302
        assert response["Location"] == _interface_url(organisation.slug, section)


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestInterfaceResolvesAndAuthorisesOnce:
    def test_unknown_slug_404s(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        client = logged_in_client(UserFactory(staff=True))

        response = client.get(_interface_url("no-such-slug", "cohorts"))

        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestSessionWrite:
    """These two go through RequestFactory rather than the test client
    because they assert on request.session.modified, which the client does
    not expose."""

    def _request(self, user: AbstractBaseUser, organisation_slug: str) -> WSGIRequest:
        request = RequestFactory().get(
            _interface_url(organisation_slug, "cohorts"),
        )
        request.user = user
        request.session = SessionStore()
        return request

    def test_session_write_is_skipped_when_the_value_is_unchanged(self) -> None:
        """An unconditional session write would mark the store dirty on
        every educator page load; the guard must only fire on a real change."""
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_admin")
        request = self._request(user, organisation.slug)
        request.session[LAST_ORGANISATION_SESSION_KEY] = organisation.slug
        request.session.save()
        request.session.modified = False

        interface(request, organisation_slug=organisation.slug, path_string="cohorts")

        assert request.session.modified is False

    def test_session_is_updated_when_the_organisation_changes(self) -> None:
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_admin")
        request = self._request(user, organisation.slug)

        interface(request, organisation_slug=organisation.slug, path_string="cohorts")

        assert request.session[LAST_ORGANISATION_SESSION_KEY] == organisation.slug


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestDetailSegmentThatIsNotAUuid:
    """A segment where a detail view expects a pk is whatever the visitor
    typed, so a guessed URL such as cohorts/create has to come back as a
    plain 404 rather than an error page."""

    @pytest.fixture
    def organisation_and_client(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> tuple[Organisation, Client]:
        organisation = cast(Organisation, OrganisationFactory())
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_admin")
        return organisation, logged_in_client(user)

    @pytest.mark.parametrize("segment", ["create", "new", "__create"])
    def test_non_uuid_segment_404s(
        self, organisation_and_client: tuple[Organisation, Client], segment: str
    ) -> None:
        organisation, client = organisation_and_client

        response = client.get(_interface_url(organisation.slug, f"cohorts/{segment}"))

        assert response.status_code == 404

    def test_well_formed_uuid_for_a_missing_cohort_404s(
        self, organisation_and_client: tuple[Organisation, Client]
    ) -> None:
        organisation, client = organisation_and_client

        response = client.get(_interface_url(organisation.slug, f"cohorts/{uuid4()}"))

        assert response.status_code == 404

    def test_real_cohort_id_still_resolves(
        self, organisation_and_client: tuple[Organisation, Client]
    ) -> None:
        organisation, client = organisation_and_client
        cohort = CohortFactory(organisation=organisation, name="Resolvable Cohort")

        response = client.get(_interface_url(organisation.slug, f"cohorts/{cohort.pk}"))

        assert response.status_code == 200
        assert "Resolvable Cohort" in response.content.decode()


def _switch(client: Client, url: str) -> _MonkeyPatchedWSGIResponse:
    return client.get(
        url,
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="main-content",
        HTTP_X_ORGANISATION_SWITCH="true",
    )


def _switcher(response: _MonkeyPatchedWSGIResponse) -> str:
    """The rendered #organisation-switcher element.

    Selected from the parsed document rather than sliced out of the raw
    response, so the assertions do not depend on what happens to render
    after the switcher.
    """
    document = lxml.html.fromstring(response.content)
    elements = document.cssselect("#organisation-switcher")
    assert elements, "no #organisation-switcher in the response"
    return str(lxml.html.tostring(elements[0], encoding="unicode"))


def _two_organisation_educator() -> tuple[Organisation, Organisation, Cohort, User]:
    """An educator with organisation_admin on two organisations, plus a
    cohort that lives only in the first."""
    organisation_a = cast(Organisation, OrganisationFactory(name="Org A"))
    organisation_b = cast(Organisation, OrganisationFactory(name="Org B"))
    cohort_a = cast(
        Cohort, CohortFactory(organisation=organisation_a, name="Cohort A Only")
    )
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(educator, organisation_a, "organisation_admin")
    assign_object_role(educator, organisation_b, "organisation_admin")
    return organisation_a, organisation_b, cohort_a, educator


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestSwitchOnAListPage:
    def test_switching_to_another_organisations_list_shows_its_content(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        CohortFactory(organisation=organisation_b, name="Cohort B Only")
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        assert response.status_code == 200
        assert b"Cohort B Only" in response.content

    def test_switch_response_carries_the_live_region_announcement(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        # That the announcement rides an out-of-band swap into the persistent
        # live region is panel_framework's contract, asserted in its own
        # test_htmx_navigation. What is host-specific is the wording.
        assert "Now viewing Org B" in response.content.decode()

    def test_switch_response_carries_the_updated_switcher_label(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        assert "Org B" in _switcher(response)

    def test_switching_to_an_organisation_without_the_section_lands_on_one_it_shows(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation_a = OrganisationFactory(name="Org A")
        organisation_b = OrganisationFactory(name="Org B")
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation_a, "organisation_admin")
        assign_object_role(educator, organisation_b, "organisation_staff_viewer")
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        assert response.status_code == 200
        assert response["HX-Push-Url"] == _interface_url(organisation_b.slug, "staff")

    def test_a_hidden_section_is_still_a_404_without_a_switch(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_staff_viewer")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "cohorts"))

        assert response.status_code == 404

    def test_switcher_links_keep_the_visitor_on_the_same_section(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        """Switching from the learners list must land on the other organisation's
        learners list, not bounce the visitor back to cohorts."""
        organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "learners"))

        assert _interface_url(organisation_b.slug, "learners") in _switcher(response)


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestSwitchOnAForeignDetailPage:
    """Switching while sitting on a detail page belonging to the organisation
    being left: the detail row does not exist in the new organisation, so the
    switch softens to that organisation's list rather than 404ing."""

    @pytest.fixture
    def switch_response(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> _MonkeyPatchedWSGIResponse:
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        CohortFactory(organisation=organisation_b, name="Cohort B Only")
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}")
        )
        response.organisation_b = organisation_b
        response.cohort_a = cohort_a
        return response

    def test_returns_the_new_organisations_list_instead_of_a_404(
        self, switch_response: _MonkeyPatchedWSGIResponse
    ) -> None:
        assert switch_response.status_code == 200
        content = switch_response.content.decode()
        assert "Cohort B Only" in content
        assert "Cohort A Only" not in content

    def test_list_urls_hang_off_the_list_not_the_foreign_detail(
        self, switch_response: _MonkeyPatchedWSGIResponse
    ) -> None:
        content = switch_response.content.decode()

        assert f"cohorts/{switch_response.cohort_a.pk}/cohorts" not in content

    def test_sets_hx_push_url_to_the_list(
        self, switch_response: _MonkeyPatchedWSGIResponse
    ) -> None:
        assert switch_response["HX-Push-Url"] == _interface_url(
            switch_response.organisation_b.slug, "cohorts"
        )

    def test_queues_an_info_message_naming_the_new_organisation(
        self, switch_response: _MonkeyPatchedWSGIResponse
    ) -> None:
        messages = [str(m) for m in get_messages(switch_response.wsgi_request)]

        assert messages == [
            "Switched to Org B — that cohort isn't in this organisation"
        ]

    def test_foreign_detail_without_the_switch_header_still_404s(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="main-content",
        )

        assert response.status_code == 404

    def test_switch_to_a_genuinely_nonexistent_path_segment_still_404s(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        """Pins the narrow OrganisationScopeDenied catch: an unknown path
        segment is a different failure than "wrong organisation" and must
        not be relabelled into the softened redirect, switch header or not.
        """
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, "no-such-section")
        )

        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestSwitcherRendering:
    def test_single_accessible_organisation_renders_static_text_not_a_dropdown(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation = OrganisationFactory(name="Solo Org")
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_admin")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "cohorts"))

        switcher = _switcher(response)
        assert "Solo Org" in switcher
        assert 'role="menuitemradio"' not in switcher
        assert (
            "Organisation"
            in lxml.html.fromstring(switcher).cssselect("p")[0].text_content()
        )

    def test_two_accessible_organisations_renders_current_one_as_checked(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation_a, _organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "cohorts"))

        switcher = _switcher(response)
        assert 'role="menuitemradio"' in switcher
        assert 'aria-checked="true"' in switcher
        assert 'aria-checked="false"' in switcher
        assert (
            "Organisation"
            in lxml.html.fromstring(switcher).cssselect("p")[0].text_content()
        )

    def test_the_trigger_opens_a_menu_of_radio_options_with_only_the_current_checked(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation_a, _organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "cohorts"))

        switcher = lxml.html.fromstring(_switcher(response))
        (trigger,) = switcher.cssselect("button[aria-haspopup='menu']")
        assert trigger.get("aria-label") == "Switch organisation"
        (menu,) = switcher.cssselect("[role='menu']")
        assert menu.get("aria-label") == "Switch organisation"
        options = menu.cssselect("[role='menuitemradio']")
        assert [
            (" ".join(option.text_content().split()), option.get("aria-checked"))
            for option in options
        ] == [("OA Org A", "true"), ("OB Org B", "false")]

    def test_the_trigger_and_every_option_carry_an_initials_tile(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation_a, _organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "cohorts"))

        switcher = lxml.html.fromstring(_switcher(response))
        (trigger,) = switcher.cssselect("button[aria-haspopup='menu']")
        (trigger_tile,) = trigger.cssselect("[data-organisation-initials]")
        assert trigger_tile.text_content().strip() == "OA"
        assert trigger_tile.get("aria-hidden") == "true"
        options = switcher.cssselect("[role='menuitemradio']")
        assert [
            option.cssselect("[data-organisation-initials]")[0].text_content().strip()
            for option in options
        ] == ["OA", "OB"]

    def test_the_single_organisation_shell_carries_the_tile_but_no_caret(
        self, logged_in_client: Callable[[AbstractBaseUser], Client]
    ) -> None:
        organisation = OrganisationFactory(name="Solo Org")
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_admin")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "cohorts"))

        switcher = lxml.html.fromstring(_switcher(response))
        (tile,) = switcher.cssselect("[data-organisation-initials]")
        assert tile.text_content().strip() == "SO"
        assert not switcher.cssselect("button")
        assert not switcher.cssselect("svg")


@pytest.mark.django_db
@pytest.mark.usefixtures("_site_context")
class TestSwitchFromAnAttemptReview:
    """A sitting belongs to one organisation's learner and its section has no
    list, so a switch lands on the other organisation's first visible section."""

    def test_lands_on_the_new_organisations_first_visible_section(
        self, logged_in_client: Callable[[User], Client]
    ) -> None:
        organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        attempt = CourseFormAttemptFactory(
            form=FormFactory(strategy=FormStrategy.QUIZ),
            course_progress__learner=LearnerFactory(organisation=organisation_a),
        )
        client = logged_in_client(educator)

        response = _switch(
            client,
            _interface_url(
                organisation_b.slug, f"quiz-attempts/{attempt.form_progress.pk}"
            ),
        )

        assert response.status_code == 200
        assert response["HX-Push-Url"] == _interface_url(
            organisation_b.slug, "dashboard"
        )


@pytest.fixture
def sidebar(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> tuple[lxml.html.HtmlElement, str]:
    """The rendered #sidebar-nav and the whole page, for a logged-in educator."""
    organisation = OrganisationFactory()
    user = UserFactory(
        staff=True, first_name="Ada", last_name="Lovelace", email="ada@example.com"
    )
    assign_object_role(user, organisation, "organisation_admin")
    response = logged_in_client(user).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )
    document = lxml.html.fromstring(response.content)
    (nav,) = document.cssselect("#sidebar-nav")
    return nav, response.content.decode()


@pytest.fixture
def _messaging_off(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    settings.MESSAGING_ENABLED = False


@pytest.mark.django_db
def test_sidebar_groups_its_sections_under_a_teaching_heading(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    headings = [h.text_content().strip() for h in nav.cssselect("h2")]

    assert headings == ["Teaching", "Administration"]


@pytest.mark.django_db
@pytest.mark.usefixtures("_messaging_on")
def test_sidebar_lists_the_six_sections_each_with_an_icon(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    links = nav.cssselect("ul > li > a")

    assert [link.text_content().strip() for link in links] == [
        "Dashboard",
        "Cohorts",
        "Learners",
        "Courses",
        "Staff",
        "Audit log",
    ]
    assert all(link.cssselect("svg") for link in links)


@pytest.mark.django_db
def test_sidebar_link_icons_are_hidden_so_each_link_is_named_by_its_label_alone(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    icons = nav.cssselect("ul > li > a svg")

    assert icons
    assert all(icon.get("aria-hidden") == "true" for icon in icons)
    assert not any(icon.get("aria-label") for icon in icons)


@pytest.mark.django_db
@pytest.mark.usefixtures("_messaging_off")
def test_sidebar_leaves_out_messages_while_messaging_is_off(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    links = nav.cssselect("ul > li > a")

    assert "Messages" not in [link.text_content().strip() for link in links]


@pytest.mark.django_db
def test_sidebar_footer_names_the_signed_in_user(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    _nav, page = sidebar

    assert "Ada Lovelace" in page
    assert "ada@example.com" in page


@pytest.mark.django_db
def test_user_block_follows_the_nav_inside_the_sidebar_dialog(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (user_block,) = dialog.cssselect("#sidebar-user")

    assert user_block.getparent() is nav.getparent()
    assert nav in user_block.itersiblings(preceding=True)


@pytest.mark.django_db
def test_navigation_dialog_has_no_close_control(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    """The navigation sheet used to carry a "Close navigation" button. It has no
    header or close control and closes by a backdrop tap or Esc."""
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    assert not dialog.xpath(".//button[@aria-label='Close navigation']")


@pytest.mark.django_db
def test_nav_links_are_not_underlined(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    links = nav.cssselect("a")

    assert links
    assert all("no-underline" in link.get("class") for link in links)


@pytest.mark.django_db
def test_the_active_item_draws_a_rounded_primary_bar_on_a_tinted_fill(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]

    classes = active.get("class")
    assert "aria-[current]:bg-surface-2" in classes
    assert "aria-[current]:text-primary" in classes
    assert "aria-[current]:shadow-[inset_2px_0_0_var(--color-primary)]" in classes
    assert "border-l" not in classes


@pytest.mark.django_db
def test_the_user_block_shows_an_initials_avatar_the_name_the_email_and_a_settings_link(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (user_block,) = dialog.cssselect("#sidebar-user")

    (avatar,) = user_block.cssselect("[aria-hidden='true'].rounded-full")
    assert avatar.text_content().strip() == "AL"
    assert "Ada Lovelace" in user_block.text_content()
    assert "ada@example.com" in user_block.text_content()
    (settings_link,) = user_block.cssselect("a[aria-label='Account settings']")
    assert settings_link.get("href") == reverse("accounts:account_profile")
    assert settings_link.cssselect("svg")


@pytest.mark.django_db
def test_the_rule_above_the_user_block_runs_the_full_sidebar_width(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (user_block,) = dialog.cssselect("#sidebar-user")

    classes = user_block.get("class")
    assert "border-t" in classes
    assert "-mx-4" in classes
    assert "lg:-mx-6" in classes


@pytest.mark.django_db
def test_a_user_with_no_name_shows_their_email_once(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(
        staff=True, first_name="", last_name="", email="nameless@example.com"
    )
    assign_object_role(user, organisation, "organisation_admin")
    response = logged_in_client(user).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )

    (user_block,) = lxml.html.fromstring(response.content).cssselect("#sidebar-user")

    assert user_block.text_content().count("nameless@example.com") == 1
    (avatar,) = user_block.cssselect("[aria-hidden='true'].rounded-full")
    assert avatar.text_content().strip() == "NA"


@pytest.mark.django_db
@pytest.mark.parametrize("messaging_enabled", [True, False])
def test_sidebar_has_no_messages_item(
    mock_site_context: Site,
    logged_in_client: Callable[[AbstractBaseUser], Client],
    settings: pytest_django.fixtures.SettingsWrapper,
    messaging_enabled: bool,
) -> None:
    settings.MESSAGING_ENABLED = messaging_enabled
    organisation = OrganisationFactory()
    user = UserFactory(staff=True)
    assign_object_role(user, organisation, "organisation_admin")
    response = logged_in_client(user).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )
    (nav,) = lxml.html.fromstring(response.content).cssselect("#sidebar-nav")

    labels = [link.text_content().strip() for link in nav.cssselect("ul > li > a")]

    assert "Messages" not in labels


def _sidebar_user_blocks(
    client: Client, organisation_slug: str
) -> tuple[list[lxml.html.HtmlElement], str]:
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation_slug, "path_string": "cohorts"},
        )
    )
    page = response.content.decode()
    return lxml.html.fromstring(page).cssselect("#sidebar-user"), page


@pytest.mark.django_db
def test_the_user_block_shows_the_picture_of_a_user_who_has_one(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(staff=True, with_profile_picture=True)
    assign_object_role(user, organisation, "organisation_admin")

    blocks, _page = _sidebar_user_blocks(logged_in_client(user), organisation.slug)

    sources = [
        image.get("src")
        for block in blocks
        for image in block.cssselect("img[data-profile-picture]")
    ]
    assert blocks
    assert sources == [user.profile_picture_url] * len(blocks)


@pytest.mark.django_db
def test_the_user_block_shows_initials_alone_for_a_user_without_a_picture(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(staff=True, first_name="Ada", last_name="Lovelace")
    assign_object_role(user, organisation, "organisation_admin")

    blocks, page = _sidebar_user_blocks(logged_in_client(user), organisation.slug)

    assert blocks
    assert not [image for block in blocks for image in block.cssselect("img")]
    assert 'src="None"' not in page


@pytest.mark.django_db
def test_the_educator_shell_loads_the_profile_picture_fallback_script(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(staff=True, with_profile_picture=True)
    assign_object_role(user, organisation, "organisation_admin")

    _blocks, page = _sidebar_user_blocks(logged_in_client(user), organisation.slug)

    scripts = lxml.html.fromstring(page).cssselect(
        "head script[src$='base/js/profile-picture-fallback.js']"
    )
    assert len(scripts) == 1
    assert scripts[0].get("defer") is None


@pytest.mark.django_db
def test_sidebar_has_no_quiz_attempts_entry(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    labels = [link.text_content().strip() for link in nav.cssselect("a")]

    assert "Quiz attempts" not in labels
