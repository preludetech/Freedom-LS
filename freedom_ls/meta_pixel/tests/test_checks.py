from __future__ import annotations

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.meta_pixel.checks import check_meta_pixel_needs_visitor_country


def test_meta_pixel_check_is_registered_via_app_ready() -> None:
    assert check_meta_pixel_needs_visitor_country in registry.registry.registered_checks


@override_settings(META_PIXEL_ID="123", VISITOR_COUNTRY_HEADER=None)
def test_pixel_id_without_visitor_country_header_returns_w001() -> None:
    warnings = check_meta_pixel_needs_visitor_country(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_meta_pixel.W001"]


@override_settings(META_PIXEL_ID="123", VISITOR_COUNTRY_HEADER="X-Visitor-Country")
def test_pixel_id_with_visitor_country_header_returns_no_warnings() -> None:
    warnings = check_meta_pixel_needs_visitor_country(None)

    assert warnings == []


@override_settings(META_PIXEL_ID=None, VISITOR_COUNTRY_HEADER=None)
def test_no_pixel_id_returns_no_warnings() -> None:
    warnings = check_meta_pixel_needs_visitor_country(None)

    assert warnings == []


@override_settings(META_PIXEL_ID=None, VISITOR_COUNTRY_HEADER="X-Visitor-Country")
def test_header_alone_returns_no_warnings() -> None:
    warnings = check_meta_pixel_needs_visitor_country(None)

    assert warnings == []
