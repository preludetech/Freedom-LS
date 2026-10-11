"""Factory for CourseApplication."""

from __future__ import annotations

import factory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class AnonymousApplicantFactory(SiteAwareFactory):
    """Factory for AnonymousApplicant instances."""

    class Meta:
        model = AnonymousApplicant

    course = factory.SubFactory(CourseFactory)
    email = factory.Sequence(lambda n: f"applicant{n}@example.com")
    first_name = "Anna"
    last_name = "Applicant"


class CourseApplicationFactory(SiteAwareFactory):
    """Factory for CourseApplication instances.

    Extends SiteAwareFactory so that site is set automatically from the
    thread-local mock_site_context in tests. Never set site_id manually.
    """

    class Meta:
        model = CourseApplication

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)

    class Params:
        anonymous = factory.Trait(
            user=None,
            anonymous_applicant=factory.SubFactory(
                AnonymousApplicantFactory, course=factory.SelfAttribute("..course")
            ),
        )
