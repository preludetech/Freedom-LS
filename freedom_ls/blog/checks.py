"""Django system checks for the blog app.

E001 — BLOG_URL_PREFIX is not a valid URL prefix.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import Error, register

_PREFIX_PATTERN = re.compile(r"[a-z0-9-]+(/[a-z0-9-]+)*")


@register()
def check_blog_url_prefix(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Error]:
    from freedom_ls.blog.config import config

    prefix = config.BLOG_URL_PREFIX
    if _PREFIX_PATTERN.fullmatch(prefix):
        return []
    return [
        Error(
            f"BLOG_URL_PREFIX {prefix!r} is not a valid URL prefix.",
            hint=(
                "Use lowercase letters, digits and hyphens, with single slashes "
                "between segments and none at either end, e.g. 'articles' or "
                "'news/blog'."
            ),
            id="freedom_ls_blog.E001",
        )
    ]
