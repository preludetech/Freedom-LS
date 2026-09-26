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


def _alert_html(html: str) -> str:
    """The last `role="alert"` region, including whatever it nests, or "" if absent.

    The base layout's always-present toast region also carries role="alert",
    ahead of page content in the document, so the page's own alert (when
    there is one) is the later of the two.
    """
    marker = html.rfind('role="alert"')
    if marker == -1:
        return ""
    start = html.rfind("<div", 0, marker)
    depth = 0
    index = start
    while True:
        next_open = html.find("<div", index + 1)
        next_close = html.find("</div>", index + 1)
        if next_close == -1:
            return ""
        if next_open != -1 and next_open < next_close:
            depth += 1
            index = next_open
            continue
        if depth == 0:
            return html[start : next_close + len("</div>")]
        depth -= 1
        index = next_close
