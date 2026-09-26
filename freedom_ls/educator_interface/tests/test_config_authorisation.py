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

from typing import cast

import pytest

from django.db.models import Model
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.views import interface_config
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    ListViewConfig,
    ObjectViewConfig,
    SectionConfig,
    sections_by_url_name,
)
from freedom_ls.role_based_permissions.utils import assign_object_role

SECTIONS = list(sections_by_url_name(interface_config).values())


def _seed_instance(model: type[Model] | None, organisation: Organisation) -> Model:
    """One instance of the model, living inside `organisation` where the
    model supports that (Course does not — it is organisation-exempt, per
    CourseConfig.check_access_exempt_reason).

    factory_boy's metaclass makes mypy see these factories as returning the
    factory class rather than the model, per pyproject's mypy override —
    cast() back to Model, the type this function actually returns.
    """
    if model is Cohort:
        return cast(Model, CohortFactory(organisation=organisation))
    if model is Learner:
        return cast(Model, LearnerFactory(organisation=organisation))
    if model is Course:
        return cast(Model, CourseFactory())
    raise NotImplementedError(
        f"test_config_authorisation has no instance seeder for {model}; "
        "add one alongside the new config."
    )


def _panel_paths(panel: Panel, path: str) -> list[str]:
    """`path` itself, every action on the panel, and the same for every shown
    child, recursively."""
    paths = [path]
    paths.extend(f"{path}/__actions/{a.action_name}" for a in panel.get_actions())
    for child in panel.get_children():
        paths.extend(
            _panel_paths(child, f"{path}/{panel.child_segment}/{child.ctx.name}")
        )
    return paths


def _bind(
    panel_class: type[Panel], request: HttpRequest, instance: Model | None
) -> Panel:
    return panel_class(
        PanelContext(request=request, instance=instance, base_url="", name="")
    )


def _config_path_strings(organisation: Organisation) -> list[str]:
    """Every path_string the interface enumerates for `organisation`: each
    section's own path, a detail path with a seeded instance, and every
    __panels / __tabs / __actions path the bound panels declare."""
    paths: list[str] = []
    request = RequestFactory().get("/")
    request.user = UserFactory(superuser=True)

    for section in SECTIONS:
        url_name = section.url_name
        if issubclass(section, BaseViewConfig):
            paths.extend(_panel_paths(_bind(section.panel, request, None), url_name))
            continue

        if issubclass(section, ListViewConfig):
            paths.append(url_name)
            paths.extend(
                f"{url_name}/__actions/{action.action_name}"
                for action in section.get_actions(request)
            )
            instance = _seed_instance(section.model, organisation)
            detail = f"{url_name}/{instance.pk}"
        else:
            assert issubclass(section, ObjectViewConfig)
            instance = section.get_object(request)
            detail = url_name

        assert section.instance_view is not None
        instance_view = section.instance_view(instance)
        paths.extend(
            f"{detail}/__actions/{action.action_name}"
            for action in instance_view.get_actions()
        )
        paths.extend(
            _panel_paths(_bind(instance_view.panel, request, instance), detail)
        )

    return paths


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
