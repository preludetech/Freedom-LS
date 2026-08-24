"""Factories for learner_progress models."""

import factory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class CourseProgressFactory(SiteAwareFactory):
    """Factory for creating CourseProgress instances."""

    class Meta:
        model = CourseProgress

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)


class TopicProgressFactory(SiteAwareFactory):
    """Factory for creating TopicProgress instances."""

    class Meta:
        model = TopicProgress

    user = factory.SubFactory(UserFactory)
    topic = factory.SubFactory(TopicFactory)
