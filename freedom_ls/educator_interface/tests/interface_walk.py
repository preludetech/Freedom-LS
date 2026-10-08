"""Walks every reachable path of educator_interface's interface_config.

`test_config_authorisation.py` uses the path strings it enumerates for its
404 sweep. `test_permission_matrix.py` uses the actions and their contexts to
check that every capability an action declares is covered by the matrix.
"""

from __future__ import annotations

from typing import NamedTuple, cast

from django.db.models import Model
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.views import interface_config
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    ListViewConfig,
    ListViewPanel,
    ObjectViewConfig,
    SectionConfig,
    sections_by_url_name,
)

SECTIONS = list(sections_by_url_name(interface_config).values())


class WalkedPanel(NamedTuple):
    """A path this walk reached, and the bound panel serving it."""

    path: str
    panel: Panel


class WalkedAction(NamedTuple):
    """A path this walk reached that submits an action, and the context the
    running interface would ask its permission check against."""

    path: str
    action: PanelAction
    ctx: PanelContext


type Walked = WalkedPanel | WalkedAction


def _seed_instance(model: type[Model] | None, organisation: Organisation) -> Model:
    """One instance of the model, living inside `organisation` where the
    model supports that. A Course does not: a published course is visible in
    every organisation, so it needs no organisation of its own.

    factory_boy's metaclass makes mypy see these factories as returning the
    factory class rather than the model, per pyproject's mypy override --
    cast() back to Model, the type this function actually returns.
    """
    if model is Cohort:
        return cast(Model, CohortFactory(organisation=organisation))
    if model is Learner:
        return cast(Model, LearnerFactory(organisation=organisation))
    if model is Course:
        return cast(Model, CourseFactory())
    raise NotImplementedError(
        f"interface_walk has no instance seeder for {model}; "
        "add one alongside the new config."
    )


def _walk_panel(panel: Panel, path: str) -> list[Walked]:
    """`path` itself, every action on the panel, and the same for every shown
    child, recursively."""
    walked: list[Walked] = [WalkedPanel(path, panel)]
    walked.extend(
        WalkedAction(f"{path}/__actions/{a.action_name}", a, panel.ctx)
        for a in panel.get_actions()
    )
    for child in panel.get_children():
        walked.extend(
            _walk_panel(child, f"{path}/{panel.child_segment}/{child.ctx.name}")
        )
    return walked


def _bind(
    panel_class: type[Panel],
    request: HttpRequest,
    instance: Model | None,
    section: SectionConfig,
    base_url: str,
) -> Panel:
    return panel_class(
        PanelContext(
            request=request,
            instance=instance,
            base_url=base_url,
            name="",
            config=section,
            scope=section.get_scope(request),
        )
    )


def walk_interface(organisation: Organisation) -> list[Walked]:
    """Every path_string the interface enumerates for `organisation`, paired
    with the panel or action serving it: each section's own path, a detail
    path with a seeded instance, and every __panels / __tabs / __actions path
    the bound panels declare."""
    walked: list[Walked] = []
    request = RequestFactory().get("/")
    request.user = UserFactory(superuser=True)
    # Every production section requires this to answer get_scope, and the
    # walker enumerates the whole tree for one organisation at a time.
    request.organisation = organisation

    for section in SECTIONS:
        url_name = section.url_name
        if issubclass(section, BaseViewConfig):
            walked.extend(
                _walk_panel(
                    _bind(section.panel, request, None, section, url_name), url_name
                )
            )
            continue

        if issubclass(section, ListViewConfig):
            if section.list_view is None:
                raise ValueError(f"{section.__name__} must define list_view")
            table = cast(
                ListViewPanel, _bind(ListViewPanel, request, None, section, url_name)
            )
            table.data_table = section.list_view
            walked.append(WalkedPanel(url_name, table))
            walked.extend(
                WalkedAction(
                    f"{url_name}/__actions/{action.action_name}", action, table.ctx
                )
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
        instance_panel = _bind(instance_view.panel, request, instance, section, detail)
        walked.extend(
            WalkedAction(
                f"{detail}/__actions/{action.action_name}", action, instance_panel.ctx
            )
            for action in instance_view.get_actions()
        )
        walked.extend(_walk_panel(instance_panel, detail))

    return walked


def config_path_strings(organisation: Organisation) -> list[str]:
    """Every path_string walk_interface reaches for `organisation`."""
    return [item.path for item in walk_interface(organisation)]
