"""Tests for ListViewConfig.check_access and authorise_instance.

These exercise the mechanism directly, on hand-built requests, because the
scope is deliberately opaque to the framework. The end-to-end coverage --
every configured surface 404ing for a user with no access, through the real
client -- lives in educator_interface/tests/test_config_authorisation.py.
"""

from __future__ import annotations

import pytest

from django.db.models import Model
from django.http import Http404, HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.views import (
    InstanceView,
    ListViewConfig,
    panel_framework_view,
)

from .conftest import StubModel, _make_stub, make_staff_user


class _StubInstanceView(InstanceView):
    pass


class DenyByDefaultConfig(ListViewConfig):
    """Defines model and instance_view but never overrides authorise_instance."""

    url_name = "deny-stub"
    menu_label = "Deny Stub"
    model = StubModel
    instance_view = _StubInstanceView


class PermissiveConfig(ListViewConfig):
    url_name = "allow-stub"
    menu_label = "Allow Stub"
    model = StubModel
    instance_view = _StubInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


class OrganisationDereferencingConfig(ListViewConfig):
    """authorise_instance dereferences request.organisation.

    Used to prove the prologue's checks run, and raise Http404, before this
    override ever executes — if it ran on a bare request this line would
    raise AttributeError instead.
    """

    url_name = "org-deref-stub"
    menu_label = "Org Deref Stub"
    model = StubModel
    instance_view = _StubInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        _ = request.organisation.pk


TEMPLATE = "panel_framework/test_interface.html"
URL_NAME = "panel_framework_test:interface"


def _authorised_request(path: str) -> HttpRequest:
    """A request that satisfies check_access's prologue: authenticated user
    and a resolved (generic, opaque) scope."""
    request = RequestFactory().get(path)
    request.user = make_staff_user()
    request.organisation = object()
    return request


@pytest.mark.django_db
class TestCheckAccessDenyByDefault:
    def test_config_without_authorise_instance_override_404s_on_detail_path(
        self, mock_site_context: None
    ) -> None:
        stub = _make_stub(name="Denied Stub")
        request = _authorised_request(f"/test-panel/deny-stub/{stub.pk}")
        with pytest.raises(Http404):
            panel_framework_view(
                config={"deny-stub": DenyByDefaultConfig},
                request=request,
                path_string=f"deny-stub/{stub.pk}",
                template_name=TEMPLATE,
                url_name=URL_NAME,
            )

    def test_config_with_permissive_override_serves_detail_path(
        self, mock_site_context: None
    ) -> None:
        stub = _make_stub(name="Allowed Stub")
        request = _authorised_request(f"/test-panel/allow-stub/{stub.pk}")
        response = panel_framework_view(
            config={"allow-stub": PermissiveConfig},
            request=request,
            path_string=f"allow-stub/{stub.pk}",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        assert response.status_code == 200
        assert "Allowed Stub" in response.content.decode()


class TestCheckAccessPrologueIsNonBypassable:
    """The prologue denies on two independent grounds -- no authenticated user,
    and no resolved scope. Both are pinned against PermissiveConfig, whose
    override would otherwise let the request through."""

    @pytest.mark.django_db
    def test_request_without_a_resolved_scope_is_denied(
        self, mock_site_context: None
    ) -> None:
        request = RequestFactory().get("/test-panel/allow-stub/1")
        request.user = make_staff_user()

        with pytest.raises(Http404):
            PermissiveConfig.check_access(request, StubModel(pk=1, name="unsaved"))

    def test_request_without_an_authenticated_user_is_denied(self) -> None:
        request = RequestFactory().get("/test-panel/allow-stub/1")
        request.organisation = object()

        with pytest.raises(Http404):
            PermissiveConfig.check_access(request, StubModel(pk=1, name="unsaved"))

    def test_bare_request_raises_http404_even_when_override_dereferences_organisation(
        self,
    ) -> None:
        """The non-overridable prologue must deny before authorise_instance
        runs, even for a subclass whose override would blow up if it ran."""
        instance = StubModel(pk=1, name="unsaved")
        with pytest.raises(Http404):
            OrganisationDereferencingConfig.check_access(HttpRequest(), instance)
