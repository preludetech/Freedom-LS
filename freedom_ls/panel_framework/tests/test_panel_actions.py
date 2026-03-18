from __future__ import annotations

import pytest

from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.student_management.factories import CohortFactory


class StubPanel(Panel):
    title = "Test Panel"

    def get_content(self, request, base_url="", panel_name=""):
        return "<p>content</p>"


class StubAction(PanelAction):
    label = "Do Thing"
    variant = "primary"
    action_name = "do_thing"


@pytest.mark.django_db
def test_panel_get_actions_returns_empty_list_by_default(mock_site_context):
    """Panel.get_actions() returns empty list by default."""
    cohort = CohortFactory()
    panel = StubPanel(cohort)
    request = RequestFactory().get("/")
    assert panel.get_actions(request) == []


@pytest.mark.django_db
def test_panel_action_render_returns_button_html(mock_site_context):
    """PanelAction.render() returns button HTML."""
    cohort = CohortFactory()
    panel = StubPanel(cohort)
    action = StubAction()
    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = action.render(request, panel, "/test/base")
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_renders_actions_when_present(mock_site_context):
    """Panel container renders action buttons when actions exist."""
    cohort = CohortFactory()

    class PanelWithAction(StubPanel):
        def get_actions(self, request, base_url=""):
            return [StubAction()]

    panel = PanelWithAction(cohort)
    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = panel.render(request, base_url="/test")
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_no_actions_area_when_no_actions(mock_site_context):
    """Panel container renders no actions area when no actions."""
    cohort = CohortFactory()
    panel = StubPanel(cohort)
    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = panel.render(request, base_url="/test")
    assert "Do Thing" not in html


@pytest.mark.django_db
def test_panel_action_has_permission_returns_true_by_default(mock_site_context):
    """PanelAction.has_permission() returns True by default."""
    action = StubAction()
    request = RequestFactory().get("/")
    assert action.has_permission(request) is True
