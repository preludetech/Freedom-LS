"""Factory for CourseApplication."""

from __future__ import annotations

import factory

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
)
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class AnonymousApplicantFactory(SiteAwareFactory):
    """Factory for AnonymousApplicant instances."""

    class Meta:
        model = AnonymousApplicant

    course = factory.SubFactory(CourseFactory)
    email = factory.Sequence(lambda n: f"applicant{n}@example.com")
    first_name = "Anna"
    last_name = "Applicant"


State = CourseApplication.State


class CourseApplicationFactory(SiteAwareFactory):
    """Factory for CourseApplication instances.

    Extends SiteAwareFactory so that site is set automatically from the
    thread-local mock_site_context in tests. Never set site_id manually.
    """

    class Meta:
        model = CourseApplication

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)
    form_progress = None
    organisation = factory.LazyAttribute(lambda o: get_default_organisation(o.site))
    # An application follows its sitting: a draft while the sitting is open,
    # submitted once it is complete or when there is no sitting.
    state = factory.LazyAttribute(
        lambda o: (
            State.DRAFT
            if o.form_progress is not None and o.form_progress.completed_time is None
            else State.SUBMITTED
        )
    )
    submitted_at = factory.LazyAttribute(
        lambda o: (
            None
            if o.state == State.DRAFT
            else (
                o.form_progress.completed_time
                if o.form_progress is not None
                else timezone.now()
            )
        )
    )

    class Params:
        approved = factory.Trait(
            state=State.APPROVED, decided_at=factory.LazyFunction(timezone.now)
        )
        rejected = factory.Trait(
            state=State.REJECTED,
            decided_at=factory.LazyFunction(timezone.now),
            rejection_message="Not this time.",
        )
        withdrawn = factory.Trait(
            state=State.WITHDRAWN, withdrawn_at=factory.LazyFunction(timezone.now)
        )
        anonymous = factory.Trait(
            user=None,
            anonymous_applicant=factory.SubFactory(
                AnonymousApplicantFactory, course=factory.SelfAttribute("..course")
            ),
        )
        anonymous_draft = factory.Trait(
            user=None,
            anonymous_applicant=factory.SubFactory(
                AnonymousApplicantFactory, course=factory.SelfAttribute("..course")
            ),
            form_progress=factory.SubFactory(FormProgressFactory, user=None),
        )
