import functools

from django.conf import settings
from django.utils.module_loading import import_string

from freedom_ls.icons.renderer import render_icon


class IconBackend:
    """Base class for custom icon backends."""

    def render(
        self,
        semantic_name: str,
        variant: str = "outline",
        css_class: str = "size-5",
        aria_label: str = "",
    ) -> str:
        raise NotImplementedError


@functools.cache
def get_icon_backend() -> IconBackend | None:
    """Return custom backend instance if configured, else None."""
    backend_path: str | None = getattr(settings, "FREEDOM_LS_ICON_BACKEND", None)
    if backend_path is None:
        return None
    backend_class: type[IconBackend] = import_string(backend_path)
    return backend_class()


def render_icon_html(
    semantic_name: str,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> str:
    """Single entry point for rendering icons. Used by template tags."""
    backend = get_icon_backend()
    if backend is not None:
        return backend.render(
            semantic_name, variant=variant, css_class=css_class, aria_label=aria_label
        )
    return render_icon(
        semantic_name, variant=variant, css_class=css_class, aria_label=aria_label
    )
