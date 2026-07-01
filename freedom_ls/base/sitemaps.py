"""Static-view sitemaps for the Freedom Learning System.

Uses only URL name reversal (no model imports) so no cross-app import
dependency is introduced. The Sites framework supplies the correct domain per
request, making sitemaps multi-tenant safe. Model-backed sitemaps live in the
app that owns the model (e.g. CourseSitemap in content_engine).
"""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap entry for static public views (the course catalogue)."""

    changefreq = "weekly"
    priority = 0.8

    def items(self) -> list[str]:
        return ["student_interface:courses"]

    def location(self, item: str) -> str:
        return reverse(item)
