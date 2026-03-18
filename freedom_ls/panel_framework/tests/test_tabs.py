from __future__ import annotations

import pytest

from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.tabs import Tab
from freedom_ls.panel_framework.views import InstanceView
from freedom_ls.student_management.factories import CohortFactory


class StubPanelA(Panel):
    title = "Panel A"

    def get_content(self, request, base_url="", panel_name=""):
        return "<p>panel-a-content</p>"


class StubPanelB(Panel):
    title = "Panel B"

    def get_content(self, request, base_url="", panel_name=""):
        return "<p>panel-b-content</p>"


class TabbedInstanceView(InstanceView):
    tabs = {
        "first_tab": Tab(label="First Tab", panels={"panel_a": StubPanelA}),
        "second_tab": Tab(label="Second Tab", panels={"panel_b": StubPanelB}),
    }


def _make_request(path: str = "/", user=None) -> HttpRequest:
    request = RequestFactory().get(path)
    request.user = user or UserFactory(staff=True)
    return request


@pytest.mark.django_db
def test_tabbed_render_includes_tab_labels(mock_site_context):
    """InstanceView.render() includes tab labels and role='tablist'."""
    cohort = CohortFactory()
    view = TabbedInstanceView(cohort)
    html = view.render(_make_request(), base_url="/test")
    assert "First Tab" in html
    assert "Second Tab" in html
    assert 'role="tablist"' in html


@pytest.mark.django_db
def test_first_tab_content_rendered_inline(mock_site_context):
    """First tab content is rendered inline; active tab is set via data attribute."""
    cohort = CohortFactory()
    view = TabbedInstanceView(cohort)
    html = view.render(_make_request(), base_url="/test")
    assert "tab-content-first_tab" in html
    assert 'data-active-tab="first_tab"' in html
    assert "panel-a-content" in html


@pytest.mark.django_db
def test_inactive_tab_has_htmx_lazy_load(mock_site_context):
    """Inactive tabs have HTMX lazy-load trigger."""
    cohort = CohortFactory()
    view = TabbedInstanceView(cohort)
    html = view.render(_make_request(), base_url="/test")
    assert "/__tabs/second_tab" in html
    assert "load-tab" in html


@pytest.mark.django_db
def test_render_tab_returns_panels_fragment(mock_site_context):
    """render_tab() returns just the panel HTML without page chrome."""
    cohort = CohortFactory()
    view = TabbedInstanceView(cohort)
    html = view.render_tab(_make_request(), "second_tab", base_url="/test")
    assert "panel-b-content" in html
    assert "<nav" not in html


@pytest.mark.django_db
def test_render_with_active_tab_override(mock_site_context):
    """Passing active_tab renders that tab's content inline instead of the first."""
    cohort = CohortFactory()
    view = TabbedInstanceView(cohort)
    html = view.render(_make_request(), base_url="/test", active_tab="second_tab")
    assert 'data-active-tab="second_tab"' in html
    assert "panel-b-content" in html


@pytest.mark.django_db
def test_tab_buttons_have_data_tab_name(mock_site_context):
    """Tab buttons include data-tab-name attributes for Alpine.js."""
    cohort = CohortFactory()
    view = TabbedInstanceView(cohort)
    html = view.render(_make_request(), base_url="/test")
    assert 'data-tab-name="first_tab"' in html
    assert 'data-tab-name="second_tab"' in html
