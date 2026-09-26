"""Calling panel_framework_view the way the stub URLconf does."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.panel_framework.views import NavGroup, panel_framework_view

from .conftest import make_staff_user
from .stub_panels import STUB_CONFIG

TEMPLATE = "panel_framework/test_interface.html"
URL_NAME = "panel_framework_test:framework"


def make_request(
    path_string: str,
    *,
    method: str = "get",
    data: dict[str, str] | None = None,
    htmx: bool = False,
    hx_target: str = "",
    restore: bool = False,
) -> HttpRequest:
    """A request from a logged-in staff user for `path_string` under the stub URLconf."""
    headers: dict[str, str] = {}
    if htmx:
        headers["HTTP_HX_REQUEST"] = "true"
    if hx_target:
        headers["HTTP_HX_TARGET"] = hx_target
    if restore:
        headers["HTTP_HX_HISTORY_RESTORE_REQUEST"] = "true"
    request: HttpRequest = getattr(RequestFactory(), method)(
        f"/test-panel/framework/{path_string}", data or {}, **headers
    )
    request.user = make_staff_user()
    return request


def call_view(
    request: HttpRequest,
    path_string: str,
    config: list[NavGroup] | None = None,
    url_name: str = URL_NAME,
) -> HttpResponse:
    return panel_framework_view(
        config=STUB_CONFIG if config is None else config,
        request=request,
        path_string=path_string,
        template_name=TEMPLATE,
        url_name=url_name,
    )


def fetch(path_string: str, **request_kwargs: object) -> HttpResponse:
    """Build a request for `path_string` and dispatch it through the stub config."""
    return call_view(make_request(path_string, **request_kwargs), path_string)
