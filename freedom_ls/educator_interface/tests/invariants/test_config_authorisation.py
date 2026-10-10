"""Coverage of the whole educator surface.

(a) Enumerates educator_interface.views.interface_config — the only URL
pattern behind the whole educator interface, so walking urlpatterns proves
nothing — and checks every section, detail, __panels, __tabs and __actions
path it can build 404s for an organisation the requesting user cannot access
at all. The panel paths come from binding each section's root panel and
walking its shown children, so a new panel or tab is covered without a
change here.

(b) Checks every production section that serves a detail view either
defines its own authorise_instance or declares check_access_exempt_reason,
and that every section names the organisation as a required request
attribute.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.tests.interface_walk import (
    SECTIONS,
    config_path_strings,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.views import BaseViewConfig, SectionConfig
from freedom_ls.role_based_permissions.utils import assign_object_role


def _authorised_sections() -> list[SectionConfig]:
    """Sections that serve a detail view, and so must decide who may see it."""
    return [s for s in SECTIONS if not issubclass(s, BaseViewConfig)]


@pytest.mark.django_db
class TestEveryConfiguredSurface404sForAnInaccessibleOrganisation:
    @pytest.fixture(autouse=True)
    def _site_context(self, mock_site_context):
        """Every test here builds site-aware objects and assigns roles."""

    def test_every_enumerated_path_404s_for_a_user_with_no_access_to_the_organisation(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        paths = config_path_strings(organisation)
        # A role on a *different* organisation — access to organisation
        # itself is what must be denied, not access to the interface at all.
        other_organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, other_organisation, "organisation_admin")
        client = logged_in_client(user)

        assert paths, "interface_config produced no path_strings to test"
        # The paths are enumerated from the config at runtime, so this sweep
        # cannot be parametrized. Collect every offender and assert once, so
        # a failure names all of them rather than only the first.
        served = [
            (path, status)
            for path, status in (
                (
                    path,
                    client.get(
                        reverse(
                            "educator_interface:interface",
                            kwargs={
                                "organisation_slug": organisation.slug,
                                "path_string": path,
                            },
                        )
                    ).status_code,
                )
                for path in paths
            )
            if status != 404
        ]

        assert not served, f"expected 404 for every path, got: {served}"


class TestProductionConfigsDeclareAuthorisation:
    """A new config must make a deliberate choice about authorisation rather
    than silently inheriting deny-by-default and 404ing in production. That
    the prologue itself cannot be bypassed is proven behaviourally in
    panel_framework/tests/test_check_access.py."""

    @pytest.mark.parametrize("config", _authorised_sections(), ids=lambda c: c.__name__)
    def test_config_overrides_authorise_instance_or_declares_an_exemption(self, config):
        overrides_authorise_instance = "authorise_instance" in config.__dict__
        is_declared_exempt = config.check_access_exempt_reason is not None

        assert overrides_authorise_instance or is_declared_exempt, (
            f"{config.__name__} neither overrides authorise_instance nor "
            "declares check_access_exempt_reason — it would silently "
            "inherit deny-by-default"
        )

    @pytest.mark.parametrize("config", SECTIONS, ids=lambda c: c.__name__)
    def test_config_declares_the_organisation_as_a_required_request_attribute(
        self, config
    ):
        """panel_framework's scope check is opt-in, so every config here has to
        name the organisation itself. A config that omits it would serve detail
        views on a request that never resolved one."""
        assert config.required_request_attrs == ("organisation",), (
            f"{config.__name__} does not declare the organisation in "
            "required_request_attrs — its detail views would be served "
            "without a resolved organisation"
        )


@pytest.mark.django_db
class TestCourseDetailIsScopedToTheOrganisation:
    @pytest.fixture(autouse=True)
    def _site_context(self, mock_site_context):
        """Every test here builds site-aware objects and assigns roles."""

    def _course_url(self, organisation, course) -> str:
        return reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"courses/{course.pk}",
            },
        )

    def test_hidden_course_with_no_registration_in_the_organisation_404s(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_admin")
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)

        response = logged_in_client(educator).get(
            self._course_url(organisation, course)
        )

        assert response.status_code == 404

    def test_hidden_course_registered_to_a_visible_cohort_opens(self, logged_in_client):
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_admin")
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=organisation), course=course
        )

        response = logged_in_client(educator).get(
            self._course_url(organisation, course)
        )

        assert response.status_code == 200
