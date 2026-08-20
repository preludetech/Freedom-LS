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


class ScopedConfig(ListViewConfig):
    """Declares a scope attribute the framework has never heard of.

    "tenant" is deliberately not a word panel_framework knows: the prologue
    must deny on whatever name a config declares, not on a hard-coded one.
    """

    url_name = "scoped-stub"
    menu_label = "Scoped Stub"
    model = StubModel
    instance_view = _StubInstanceView
    required_request_attrs = ("tenant",)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


class ScopeDereferencingConfig(ListViewConfig):
    """authorise_instance dereferences the scope this config declares.

    Used to prove the prologue's checks run, and raise Http404, before this
    override ever executes — if it ran on a bare request this line would
    raise AttributeError instead.
    """

    url_name = "scope-deref-stub"
    menu_label = "Scope Deref Stub"
    model = StubModel
    instance_view = _StubInstanceView
    required_request_attrs = ("tenant",)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        _ = request.tenant.pk


TEMPLATE = "panel_framework/test_interface.html"
URL_NAME = "panel_framework_test:interface"


def _authenticated_request(path: str) -> HttpRequest:
    """A request carrying an authenticated user and no scope attribute at all.

    That is what a host app with no scope concept sends, and it satisfies the
    prologue for any config that declares no required_request_attrs.
    """
    request = RequestFactory().get(path)
    request.user = make_staff_user()
    return request


@pytest.mark.django_db
class TestCheckAccessDenyByDefault:
    def test_config_without_authorise_instance_override_404s_on_detail_path(
        self, mock_site_context: None
    ) -> None:
        stub = _make_stub(name="Denied Stub")
        request = _authenticated_request(f"/test-panel/deny-stub/{stub.pk}")
        with pytest.raises(Http404):
            panel_framework_view(
                config={"deny-stub": DenyByDefaultConfig},
                request=request,
                path_string=f"deny-stub/{stub.pk}",
                template_name=TEMPLATE,
                url_name=URL_NAME,
            )

    def test_config_declaring_no_scope_serves_a_detail_path_unscoped(
        self, mock_site_context: None
    ) -> None:
        """The standalone-host case: a config that overrides authorise_instance
        but declares no required_request_attrs is served on a request that
        carries no scope of any kind."""
        stub = _make_stub(name="Allowed Stub")
        request = _authenticated_request(f"/test-panel/allow-stub/{stub.pk}")
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
    and a declared scope attribute that is missing. Both are pinned against
    configs whose override would otherwise let the request through."""

    @pytest.mark.django_db
    def test_request_missing_a_declared_scope_attribute_is_denied(
        self, mock_site_context: None
    ) -> None:
        request = RequestFactory().get("/test-panel/scoped-stub/1")
        request.user = make_staff_user()

        with pytest.raises(Http404):
            ScopedConfig.check_access(request, StubModel(pk=1, name="unsaved"))

    def test_request_without_an_authenticated_user_is_denied(self) -> None:
        request = RequestFactory().get("/test-panel/scoped-stub/1")
        request.tenant = object()

        with pytest.raises(Http404):
            ScopedConfig.check_access(request, StubModel(pk=1, name="unsaved"))

    def test_bare_request_raises_http404_even_when_override_dereferences_the_scope(
        self,
    ) -> None:
        """The non-overridable prologue must deny before authorise_instance
        runs, even for a subclass whose override would blow up if it ran."""
        instance = StubModel(pk=1, name="unsaved")
        with pytest.raises(Http404):
            ScopeDereferencingConfig.check_access(HttpRequest(), instance)
