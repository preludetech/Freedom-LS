import pytest

from django.test import override_settings
from rest_framework.viewsets import ViewSet

from freedom_ls.api.checks import (
    check_throttle_cache_is_shared,
    check_viewsets_declare_a_scope,
    check_viewsets_page_on_a_valid_field,
    viewsets_with_a_bad_cursor_field,
    viewsets_without_scope,
)
from freedom_ls.api.models import ApiKey
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
DATABASE = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
    }
}


class ScopedViewSet(ViewSet):
    required_scope = ApiScope.USERS


class UnscopedViewSet(ViewSet):
    pass


@override_settings(DEBUG=False, CACHES=LOCMEM)
def test_per_process_cache_warns_outside_debug():
    warnings = check_throttle_cache_is_shared(None)

    assert [w.id for w in warnings] == ["freedom_ls_api.W001"]


@override_settings(DEBUG=False, CACHES=DATABASE)
def test_shared_cache_does_not_warn():
    assert check_throttle_cache_is_shared(None) == []


@override_settings(DEBUG=True, CACHES=LOCMEM)
def test_per_process_cache_does_not_warn_in_debug():
    assert check_throttle_cache_is_shared(None) == []


def test_viewset_without_scope_is_an_error():
    errors = viewsets_without_scope([("things", UnscopedViewSet, "thing")])

    assert [e.id for e in errors] == ["freedom_ls_api.E001"]
    assert "UnscopedViewSet" in errors[0].msg


def test_viewset_with_scope_is_not_an_error():
    assert viewsets_without_scope([("things", ScopedViewSet, "thing")]) == []


@pytest.mark.django_db
def test_registered_viewsets_all_declare_a_scope():
    assert check_viewsets_declare_a_scope(None) == []


def _paging_on(cursor_field: str) -> type[ReadOnlyApiViewSet]:
    return type(
        "PagedViewSet",
        (ReadOnlyApiViewSet,),
        {"queryset": ApiKey._base_manager.all(), "cursor_field": cursor_field},
    )


@pytest.mark.parametrize(
    "cursor_field",
    [
        pytest.param("name", id="not_a_date_or_datetime"),
        pytest.param("updated", id="not_a_field"),
        pytest.param("expires_at", id="nullable"),
    ],
)
def test_viewset_whose_cursor_field_cannot_be_paged_on_is_an_error(cursor_field):
    errors = viewsets_with_a_bad_cursor_field(
        [("things", _paging_on(cursor_field), "thing")]
    )

    assert [e.id for e in errors] == ["freedom_ls_api.E002"]
    assert "PagedViewSet" in errors[0].msg


def test_viewset_paging_on_a_datetime_is_not_an_error():
    registry = [("things", _paging_on("created_at"), "thing")]

    assert viewsets_with_a_bad_cursor_field(registry) == []


def test_viewset_that_names_no_model_is_skipped():
    registry = [("things", UnscopedViewSet, "thing")]

    assert viewsets_with_a_bad_cursor_field(registry) == []


@pytest.mark.django_db
def test_registered_viewsets_all_page_on_a_valid_field():
    assert check_viewsets_page_on_a_valid_field(None) == []
