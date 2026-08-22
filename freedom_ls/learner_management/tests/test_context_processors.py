"""Tests for learner_management.context_processors.

can_access_educator_interface answers one question for the header menu: may
this person enter the educator interface at all? It must agree with
organisations_accessible_to, which is the interface's own gate, and it must
cost nothing on the many pages that never read the answer.
"""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.template import Context, Template
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils.functional import SimpleLazyObject

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.context_processors import (
    can_access_educator_interface,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


def _context_for(user: User | AnonymousUser) -> dict[str, bool | SimpleLazyObject]:
    request = RequestFactory().get("/")
    request.user = user
    return can_access_educator_interface(request)


def _flag_for(user: User | AnonymousUser) -> bool:
    return bool(_context_for(user)["can_access_educator_interface"])


@pytest.mark.django_db
class TestCanAccessEducatorInterface:
    """The flag mirrors organisations_accessible_to: an organisation role, a
    per-cohort guardian grant, or superuser — never is_staff on its own."""

    def test_educator_with_roles_on_several_organisations_can_access(
        self, mock_site_context
    ):
        user = UserFactory()
        assign_object_role(user, OrganisationFactory(), "organisation_staff")
        assign_object_role(user, OrganisationFactory(), "organisation_staff")

        assert _flag_for(user) is True

    def test_educator_with_a_role_on_one_organisation_can_access(
        self, mock_site_context
    ):
        user = UserFactory()
        assign_object_role(user, OrganisationFactory(), "organisation_staff")

        assert _flag_for(user) is True

    def test_educator_with_only_a_cohort_grant_can_access(self, mock_site_context):
        user = UserFactory()
        assign_object_role(user, CohortFactory(), "instructor")

        assert _flag_for(user) is True

    def test_user_with_neither_role_nor_grant_cannot_access(self, mock_site_context):
        OrganisationFactory()
        user = UserFactory()

        assert _flag_for(user) is False

    def test_staff_flag_alone_does_not_grant_access(self, mock_site_context):
        OrganisationFactory()
        user = UserFactory(staff=True)

        assert _flag_for(user) is False

    def test_superuser_can_access(self, mock_site_context):
        OrganisationFactory()
        user = UserFactory(superuser=True)

        assert _flag_for(user) is True

    def test_anonymous_user_cannot_access(self, mock_site_context):
        OrganisationFactory()

        assert _flag_for(AnonymousUser()) is False

    def test_request_without_an_authenticated_user_cannot_access(
        self, mock_site_context
    ):
        """A request rendered outside AuthenticationMiddleware carries no
        user, and must still produce an answer rather than an AttributeError."""
        OrganisationFactory()
        request = RequestFactory().get("/")

        context = can_access_educator_interface(request)

        assert context["can_access_educator_interface"] is False


@pytest.mark.django_db
class TestCanAccessEducatorInterfaceIsLazy:
    """Every page on the site renders the header, so the answer must only be
    computed on the pages whose template actually asks for it."""

    def test_anonymous_user_costs_no_query(self, mock_site_context):
        anonymous = AnonymousUser()

        with CaptureQueriesContext(connection) as captured:
            _flag_for(anonymous)

        assert len(captured) == 0

    def test_a_template_that_never_reads_the_flag_runs_no_query(
        self, mock_site_context
    ):
        user = UserFactory()
        assign_object_role(user, OrganisationFactory(), "organisation_staff")
        context = _context_for(user)
        template = Template("nothing here reads the flag")

        with CaptureQueriesContext(connection) as captured:
            template.render(Context(context))

        assert len(captured) == 0

    def test_a_template_that_reads_the_flag_evaluates_it(self, mock_site_context):
        user = UserFactory()
        assign_object_role(user, OrganisationFactory(), "organisation_staff")
        context = _context_for(user)
        template = Template("{% if can_access_educator_interface %}yes{% endif %}")

        with CaptureQueriesContext(connection) as captured:
            rendered = template.render(Context(context))

        assert rendered == "yes"
        assert len(captured) > 0
