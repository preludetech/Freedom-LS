"""Coverage of the whole educator surface.

(a) Enumerates educator_interface.views.interface_config — the only URL
pattern behind the whole educator interface, so walking urlpatterns proves
nothing — and checks every list, detail, __panels, __tabs and __actions path
it can build 404s for an organisation the requesting user cannot access at
all. Also enumerates every ListViewConfig.__subclasses__() rather than
walking urlpatterns, which would sweep in the eight-plus test-only configs
under panel_framework/tests/.

(b) Checks every production ListViewConfig either defines its own
authorise_instance or declares check_access_exempt_reason.
"""

from __future__ import annotations

from typing import cast

import pytest

from django.db.models import Model
from django.http import HttpRequest
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.views import ListViewConfig, interface_config
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.student_management.models import Cohort


def _seed_instance(config: type[ListViewConfig], organisation: Organisation) -> Model:
    """One instance of the config's model, living inside `organisation`
    where the model supports that (Course does not — it is organisation-
    exempt, per CourseConfig.check_access_exempt_reason).

    factory_boy's metaclass makes mypy see these factories as returning the
    factory class rather than the model, per pyproject's mypy override —
    cast() back to Model, the type this function actually returns.
    """
    if config.model is Cohort:
        return cast(Model, CohortFactory(organisation=organisation))
    if config.model is User:
        cohort = CohortFactory(organisation=organisation)
        user = cast(Model, UserFactory())
        CohortMembershipFactory(cohort=cohort, user=user)
        return user
    if config.model is Course:
        return cast(Model, CourseFactory())
    raise NotImplementedError(
        f"test_config_authorisation has no instance seeder for {config.model}; "
        "add one alongside the new config."
    )


def _config_path_strings(organisation) -> list[str]:
    """Every path_string the interface enumerates for `organisation`: one
    list section per config, one detail path with a seeded instance, and
    every __panels / __tabs / __actions segment each config declares."""
    paths: list[str] = []
    fake_request = HttpRequest()

    for url_name, config in interface_config.items():
        paths.append(url_name)
        paths.extend(
            f"{url_name}/__actions/{action.action_name}"
            for action in config.get_actions(fake_request)
        )

        if config.instance_view is None:
            continue

        instance = _seed_instance(config, organisation)
        detail = f"{url_name}/{instance.pk}"
        paths.append(detail)

        instance_view = config.instance_view(instance)
        paths.extend(
            f"{detail}/__actions/{action.action_name}"
            for action in instance_view.get_actions()
        )
        paths.extend(f"{detail}/__panels/{name}" for name in instance_view.panels)
        if instance_view.tabs:
            for tab_name, tab in instance_view.tabs.items():
                tab_path = f"{detail}/__tabs/{tab_name}"
                paths.append(tab_path)
                paths.extend(
                    f"{tab_path}/__panels/{panel_name}" for panel_name in tab.panels
                )

    return paths


@pytest.mark.django_db
class TestEveryConfiguredSurface404sForAnInaccessibleOrganisation:
    @pytest.fixture(autouse=True)
    def _site_context(self, mock_site_context):
        """Every test here builds site-aware objects and assigns roles."""

    def test_every_enumerated_path_404s_for_a_user_with_no_access_to_the_organisation(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        paths = _config_path_strings(organisation)
        # A role on a *different* organisation — access to organisation
        # itself is what must be denied, not access to the interface at all.
        other_organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, other_organisation, "organisation_staff")
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

    @pytest.mark.parametrize(
        "config", list(interface_config.values()), ids=lambda c: c.__name__
    )
    def test_config_overrides_authorise_instance_or_declares_an_exemption(self, config):
        overrides_authorise_instance = "authorise_instance" in config.__dict__
        is_declared_exempt = config.check_access_exempt_reason is not None

        assert overrides_authorise_instance or is_declared_exempt, (
            f"{config.__name__} neither overrides authorise_instance nor "
            "declares check_access_exempt_reason — it would silently "
            "inherit deny-by-default"
        )

    @pytest.mark.parametrize(
        "config", list(interface_config.values()), ids=lambda c: c.__name__
    )
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
