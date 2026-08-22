"""Tests for the header user menu partial.

Two separate audiences share one menu: anyone who may enter the educator
interface gets the Educator Interface link, while the Admin Panel link stays
tied to is_staff. Rendering through render_to_string(request=...) runs the
real context processors, so these tests also cover the settings wiring.
"""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

EDUCATOR_LINK_TEXT = "Educator Interface"
ADMIN_LINK_TEXT = "Admin Panel"


def _render_menu(user: User) -> str:
    request = RequestFactory().get("/")
    request.user = user
    return render_to_string("partials/header_bar_user_menu.html", request=request)


def _render_header(user: User | AnonymousUser) -> str:
    request = RequestFactory().get("/")
    request.user = user
    return render_to_string("partials/header_bar.html", request=request)


@pytest.mark.django_db
class TestEducatorInterfaceLink:
    """Shown to everyone the educator interface would let in — which is no
    longer the same set as is_staff."""

    def test_shown_to_an_educator_with_a_role_on_an_organisation(
        self, mock_site_context
    ):
        user = UserFactory()
        assign_object_role(user, OrganisationFactory(), "organisation_staff")

        rendered = _render_menu(user)

        assert EDUCATOR_LINK_TEXT in rendered
        assert f'href="{reverse("educator_interface:root")}"' in rendered

    def test_shown_to_an_educator_with_only_a_cohort_grant(self, mock_site_context):
        user = UserFactory()
        assign_object_role(user, CohortFactory(), "instructor")

        assert EDUCATOR_LINK_TEXT in _render_menu(user)

    def test_shown_to_a_superuser(self, mock_site_context):
        OrganisationFactory()
        user = UserFactory(superuser=True)

        assert EDUCATOR_LINK_TEXT in _render_menu(user)

    def test_hidden_from_a_user_with_neither_role_nor_grant(self, mock_site_context):
        OrganisationFactory()
        user = UserFactory()

        assert EDUCATOR_LINK_TEXT not in _render_menu(user)


@pytest.mark.django_db
class TestAdminPanelLink:
    """Still staff-only. Handing /admin/ to an educator who merely holds an
    organisation role would be a privilege escalation."""

    def test_hidden_from_a_non_staff_educator(self, mock_site_context):
        user = UserFactory()
        assign_object_role(user, OrganisationFactory(), "organisation_staff")

        rendered = _render_menu(user)

        assert ADMIN_LINK_TEXT not in rendered
        assert 'href="/admin/"' not in rendered

    def test_shown_to_a_staff_user(self, mock_site_context):
        user = UserFactory(staff=True)

        assert ADMIN_LINK_TEXT in _render_menu(user)


@pytest.mark.django_db
class TestAnonymousHeader:
    """The header renders for logged-out visitors too."""

    def test_offers_the_login_prompt_instead_of_the_user_menu(self, mock_site_context):
        rendered = _render_header(AnonymousUser())

        assert f'href="{reverse("account_login")}"' in rendered
        assert EDUCATOR_LINK_TEXT not in rendered
