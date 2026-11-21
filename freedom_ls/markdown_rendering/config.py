from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class MarkdownRenderingConfig(AppSettings):
    MARKDOWN_ALLOWED_TAGS: dict[str, set[str]]
    MARKDOWN_TEMPLATE_RENDER_ON: bool
    MARKDOWN_BODY_TAGS: tuple[str, ...]

    declared_settings = {
        "MARKDOWN_ALLOWED_TAGS": Setting(default={}),
        "MARKDOWN_TEMPLATE_RENDER_ON": Setting(default=True),
        # Widgets whose body is markdown: the slot widgets, plus c-slot and
        # the layout wrappers c-grid and c-image-grid that can hold them. A
        # project adds the tag of each custom widget whose body is markdown.
        "MARKDOWN_BODY_TAGS": Setting(
            default=(
                "c-accordion",
                "c-admonition",
                "c-card",
                "c-flashcard",
                "c-pull-quote",
                "c-table",
                "c-audio-clip",
                "c-slot",
                "c-grid",
                "c-image-grid",
            )
        ),
    }


config = MarkdownRenderingConfig()
