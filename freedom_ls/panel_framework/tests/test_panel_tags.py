"""Tests for the resolve_url_path_template template tag."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from django.template import Context, RequestContext, Template
from django.test import RequestFactory


@pytest.mark.django_db
def test_resolve_url_path_template_builds_url_from_object_attrs(
    mock_site_context: None,
) -> None:
    """Placeholders in the path template are substituted from object attributes."""
    request = RequestFactory().get("/whatever")
    obj = SimpleNamespace(pk=42)
    template = Template(
        "{% load panel_tags %}"
        "{% resolve_url_path_template obj 'panel_framework_test:interface' 'cohorts/{pk}' %}"
    )
    result = template.render(RequestContext(request, {"obj": obj}))
    assert result.strip() == "/test-panel/cohorts/42"


@pytest.mark.django_db
def test_resolve_url_path_template_merges_panel_url_kwargs(
    mock_site_context: None,
) -> None:
    """request.panel_url_kwargs reaches this tag's reverse() call, same as the sidebar/breadcrumb builders."""
    request = RequestFactory().get("/whatever")
    request.panel_url_kwargs = {"extra": "acme"}
    obj = SimpleNamespace(pk=42)
    template = Template(
        "{% load panel_tags %}"
        "{% resolve_url_path_template obj 'panel_framework_test:scoped_interface' 'cohorts/{pk}' %}"
    )
    result = template.render(RequestContext(request, {"obj": obj}))
    assert result.strip() == "/test-panel/scoped/acme/cohorts/42"


@pytest.mark.django_db
def test_resolve_url_path_template_without_a_request_in_the_context(
    mock_site_context: None,
) -> None:
    """Rendered outside a request, the tag falls back to no extra kwargs
    rather than raising on the missing 'request' context variable."""
    obj = SimpleNamespace(pk=42)
    template = Template(
        "{% load panel_tags %}"
        "{% resolve_url_path_template obj 'panel_framework_test:interface' 'cohorts/{pk}' %}"
    )
    result = template.render(Context({"obj": obj}))
    assert result.strip() == "/test-panel/cohorts/42"
