from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class MarkdownRenderingConfig(AppSettings):
    MARKDOWN_ALLOWED_TAGS: dict[str, set[str]]
    MARKDOWN_TEMPLATE_RENDER_ON: bool

    declared_settings = {
        "MARKDOWN_ALLOWED_TAGS": Setting(default=None),
        "MARKDOWN_TEMPLATE_RENDER_ON": Setting(default=True),
    }


config = MarkdownRenderingConfig()
