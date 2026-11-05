"""System checks for the API app."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.utils.module_loading import autodiscover_modules
from rest_framework.views import APIView

from .pagination import cursor_field_problem
from .routers import router
from .scopes import ApiScope
from .viewsets import ReadOnlyApiViewSet

_PER_PROCESS_BACKENDS = (
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
)


@register(Tags.caches)
def check_throttle_cache_is_shared(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Warning]:
    """Warn when the default cache is per process, so throttle counts are not shared."""
    if settings.DEBUG:
        return []
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if backend not in _PER_PROCESS_BACKENDS:
        return []
    return [
        Warning(
            "The API throttle counts requests in the default cache, and this backend is per process.",
            hint="Use a shared cache backend (the production settings use DatabaseCache), or every "
            "worker process grants API_THROTTLE_RATE on its own.",
            id="freedom_ls_api.W001",
        )
    ]


def viewsets_without_scope(
    registry: Iterable[tuple[str, type[APIView], str]],
) -> list[Error]:
    """One error for each registered viewset whose ``required_scope`` is not an ApiScope."""
    return [
        Error(
            f"{viewset.__module__}.{viewset.__name__} has no required_scope.",
            hint="Set required_scope to an ApiScope on the viewset.",
            id="freedom_ls_api.E001",
        )
        for _prefix, viewset, _basename in registry
        if not isinstance(getattr(viewset, "required_scope", None), ApiScope)
    ]


def viewsets_with_a_bad_cursor_field(
    registry: Iterable[tuple[str, type[APIView], str]],
) -> list[Error]:
    """One error for each registered API viewset whose ``cursor_field`` cannot be paged on.

    A viewset with no ``queryset`` attribute names no model, so it is skipped.
    """
    errors: list[Error] = []
    for _prefix, viewset, _basename in registry:
        if not issubclass(viewset, ReadOnlyApiViewSet) or viewset.queryset is None:
            continue
        problem = cursor_field_problem(viewset.queryset.model, viewset.cursor_field)
        if problem is not None:
            errors.append(
                Error(
                    f"{viewset.__module__}.{viewset.__name__}: {problem}",
                    hint="Set cursor_field to a DateTimeField or DateField of the model "
                    "that is not nullable.",
                    id="freedom_ls_api.E002",
                )
            )
    return errors


@register(Tags.urls)
def check_viewsets_declare_a_scope(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Error]:
    # The registry is filled by the endpoint apps' api.py modules; importing
    # them again is a no-op once urls.py has done it.
    autodiscover_modules("api")
    return viewsets_without_scope(router.registry)


@register(Tags.urls)
def check_viewsets_page_on_a_valid_field(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Error]:
    autodiscover_modules("api")
    return viewsets_with_a_bad_cursor_field(router.registry)
