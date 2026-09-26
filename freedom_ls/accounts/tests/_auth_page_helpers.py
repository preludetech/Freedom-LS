"""Shared HTML-scraping helpers for the login/signup page tests."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

from django.urls import reverse


def _hrefs_to(html: str, url_name: str) -> list[str]:
    """Every href on the page that points at `url_name`."""
    target_path = reverse(url_name)
    hrefs = [unescape(h) for h in re.findall(r'href="([^"]*)"', html)]
    return [h for h in hrefs if urlparse(h).path == target_path]


def _header_html(html: str) -> str:
    """The `<header>…</header>` fragment of the page."""
    match = re.search(r"<header.*?</header>", html, re.DOTALL)
    assert match, "page has no <header> element"
    return match.group(0)
