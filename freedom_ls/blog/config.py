from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class BlogConfig(AppSettings):
    BLOG_URL_PREFIX: str

    declared_settings = {
        "BLOG_URL_PREFIX": Setting(default="articles"),
    }


config = BlogConfig()
