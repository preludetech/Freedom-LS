import uuid

import factory

from django.contrib.contenttypes.models import ContentType

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.feedback.models import (
    FeedbackDismissal,
    FeedbackForm,
    FeedbackResponse,
    FeedbackTriggerLog,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class FeedbackFormFactory(SiteAwareFactory):
    class Meta:
        model = FeedbackForm

    name = factory.Sequence(lambda n: f"Feedback Form {n}")
    trigger_point = "course_completed"
    is_active = True


class FeedbackTriggerLogFactory(SiteAwareFactory):
    class Meta:
        model = FeedbackTriggerLog

    user = factory.SubFactory(UserFactory)
    trigger_point = "course_completed"
    count = 0


class FeedbackResponseFactory(SiteAwareFactory):
    class Meta:
        model = FeedbackResponse

    form = factory.SubFactory(FeedbackFormFactory)
    user = factory.SubFactory(UserFactory)
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(Course)
    )
    object_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    rating = 4
    comment = "Great course!"


class FeedbackDismissalFactory(SiteAwareFactory):
    class Meta:
        model = FeedbackDismissal

    form = factory.SubFactory(FeedbackFormFactory)
    user = factory.SubFactory(UserFactory)
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(Course)
    )
    object_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
