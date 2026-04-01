from collections.abc import Iterator

import pytest

from django.test import override_settings

from freedom_ls.icons.backend import (
    DefaultIconBackend,
    IconBackend,
    get_icon_backend,
)


class MockBackend(IconBackend):
    def render(
        self,
        semantic_name: str,
        variant: str = "outline",
        css_class: str = "size-5",
        aria_label: str = "",
    ) -> str:
        return f"<mock>{semantic_name}|{variant}|{css_class}|{aria_label}</mock>"


@pytest.fixture(autouse=True)
def _clear_backend_cache() -> Iterator[None]:
    get_icon_backend.cache_clear()
    yield
    get_icon_backend.cache_clear()


class TestGetIconBackend:
    def test_returns_default_backend_when_not_configured(self) -> None:
        assert isinstance(get_icon_backend(), DefaultIconBackend)

    @override_settings(
        FREEDOM_LS_ICON_BACKEND="freedom_ls.icons.tests.test_backend.MockBackend"
    )
    def test_returns_custom_backend_instance(self) -> None:
        backend = get_icon_backend()
        assert backend is not None
        assert isinstance(backend, IconBackend)
        assert type(backend).__name__ == "MockBackend"


class TestRenderIconHtml:
    def test_default_uses_builtin_renderer(self) -> None:
        result = get_icon_backend().render("success")
        assert "<svg" in result

    @override_settings(
        FREEDOM_LS_ICON_BACKEND="freedom_ls.icons.tests.test_backend.MockBackend"
    )
    def test_custom_backend_output_is_used(self) -> None:
        result = get_icon_backend().render("success")
        assert "<mock>success|" in result

    @override_settings(
        FREEDOM_LS_ICON_BACKEND="freedom_ls.icons.tests.test_backend.MockBackend"
    )
    def test_custom_backend_receives_all_params(self) -> None:
        result = get_icon_backend().render(
            "success", variant="solid", css_class="size-6", aria_label="Done"
        )
        assert result == "<mock>success|solid|size-6|Done</mock>"
