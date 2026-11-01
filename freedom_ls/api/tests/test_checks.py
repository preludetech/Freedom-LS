import pytest

from django.test import override_settings
from rest_framework.viewsets import ViewSet

from freedom_ls.api.checks import (
    check_throttle_cache_is_shared,
    check_viewsets_declare_a_scope,
    viewsets_without_scope,
)
from freedom_ls.api.scopes import ApiScope

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
