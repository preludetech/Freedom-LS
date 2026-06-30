"""Sitemaps for the Freedom Learning System.

Uses only URL name reversal (no Python imports from student_interface) so
no new cross-app import dependency is introduced. The Sites framework
supplies the correct domain per request, making sitemaps multi-tenant safe.
"""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.db.models import QuerySet
from django.urls import reverse

from freedom_ls.content_engine.models import Course


class StaticViewSitemap(Sitemap):
    """Sitemap entry for static public views (the course catalogue)."""

    changefreq = "weekly"
    priority = 0.8

    def items(self) -> list[str]:
        return ["student_interface:courses"]

    def location(self, item: str) -> str:
        return reverse(item)


class CourseSitemap(Sitemap):
    """Sitemap entries for individual course detail pages.

    Course.objects.all() is site-filtered automatically by SiteAwareManager,
    so each tenant's sitemap only exposes its own courses.
    """

    changefreq = "weekly"
    priority = 0.7

    def items(self) -> QuerySet[Course]:
        return Course.objects.all().order_by("slug")

    def location(self, obj: Course) -> str:
        return reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": obj.slug},
        )
