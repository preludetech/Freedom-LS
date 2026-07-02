"""Factory for CourseInterest."""

from __future__ import annotations

import factory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class CourseInterestFactory(SiteAwareFactory):
    """Factory for CourseInterest instances.

    Extends SiteAwareFactory so that site is set automatically from the
    thread-local mock_site_context in tests. Never set site_id manually.
    """

    class Meta:
        model = CourseInterest

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)
