"""Sitemaps for content_engine models.

Lives in content_engine because it owns the Course model. The Sites framework
supplies the correct domain per request, making the sitemap multi-tenant safe.
"""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.db.models import QuerySet
from django.urls import reverse

from freedom_ls.content_engine.models import Course


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
