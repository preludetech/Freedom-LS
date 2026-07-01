"""Sitemaps for the Freedom Learning System.

All sitemaps are co-located here in the project's composition root, which is
allowed to depend on any app. The Sites framework supplies the correct domain
per request, making every sitemap multi-tenant safe.
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.contrib.sitemaps import Sitemap
from django.db.models import QuerySet
from django.urls import reverse

from freedom_ls.content_engine.models import Course
from freedom_ls.course_access.loader import get_course_access_backend


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
    so each tenant's sitemap only exposes its own courses. Visibility is applied
    through the access backend's canonical filter_visible (as an anonymous
    crawler): hidden courses are excluded, coming-soon courses — whose detail
    pages are publicly reachable — are kept. Routing through filter_visible keeps
    the sitemap from drifting from the catalogue's own visibility rule.
    """

    changefreq = "weekly"
    priority = 0.7

    def items(self) -> QuerySet[Course]:
        return get_course_access_backend().filter_visible(
            user=AnonymousUser(),
            courses=Course.objects.all().order_by("slug"),
        )

    def location(self, obj: Course) -> str:
        return reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": obj.slug},
        )
