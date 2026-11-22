"""Factories for revision models."""

import factory

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.form_engine.factories import FormQuestionFactory
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class RevisionScheduleFactory(SiteAwareFactory):
    class Meta:
        model = RevisionSchedule

    user = factory.SubFactory(UserFactory)
    question = factory.SubFactory(FormQuestionFactory)
    state = 2
    step = None
    stability = 5.0
    difficulty = 5.0
    due = factory.LazyFunction(timezone.now)
    last_review = factory.LazyFunction(timezone.now)
    reps = 1
    lapses = 0


class RevisionReviewFactory(SiteAwareFactory):
    class Meta:
        model = RevisionReview

    user = factory.SubFactory(UserFactory)
    question = factory.SubFactory(FormQuestionFactory)
    course = factory.SubFactory(CourseFactory)
    reviewed_at = factory.LazyFunction(timezone.now)
    selected_option_ids = factory.LazyFunction(list)
    was_correct = True
    guessed = False
    rating = 3
    schedule_before = factory.LazyFunction(dict)
