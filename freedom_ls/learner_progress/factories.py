"""Factories for learner_progress models."""

import factory

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class CourseProgressFactory(SiteAwareFactory):
    """Factory for creating CourseProgress instances.

    Builds the record directly rather than registering a learner and waiting
    for the signal receivers: they defer their work to transaction.on_commit,
    which never runs inside a test's rolled-back transaction.

    The default grant is an individual registration for this same learner and
    course, so the pairing clean() guards holds without the caller arranging
    it. For a cohort-granted record pass ``cohort_registration=...`` together
    with ``learner_registration=None``.
    """

    class Meta:
        model = CourseProgress

    learner = factory.SubFactory(LearnerFactory)
    course = factory.SubFactory(CourseFactory)
    learner_registration = factory.SubFactory(
        LearnerCourseRegistrationFactory,
        learner=factory.SelfAttribute("..learner"),
        course=factory.SelfAttribute("..course"),
    )


class TopicProgressFactory(SiteAwareFactory):
    """Factory for creating TopicProgress instances.

    ``topic`` drives the placement: the collection item is built to place that
    topic in the record's course, so ``TopicProgressFactory(topic=t)`` stays
    coherent. Pass ``collection_item=None`` for an orphaned row -- one whose
    placement has since been deleted -- or pass both to place a topic that is
    already in a collection.
    """

    class Meta:
        model = TopicProgress

    course_progress = factory.SubFactory(CourseProgressFactory)
    topic = factory.SubFactory(TopicFactory)
    collection_item = factory.SubFactory(
        ContentCollectionItemFactory,
        collection_object=factory.SelfAttribute("..course_progress.course"),
        child_object=factory.SelfAttribute("..topic"),
        site=factory.SelfAttribute("..site"),
    )


class CourseFormAttemptFactory(SiteAwareFactory):
    """Factory for creating CourseFormAttempt instances.

    Builds the `form_engine` attempt too, since a course-side row without one is
    not a state the application can reach. ``form`` drives both halves: the
    attempt is at that form, and the collection item places it in the record's
    course, so ``CourseFormAttemptFactory(form=f)`` stays coherent.

    Pass ``collection_item=None`` for an orphaned attempt -- one whose placement
    has since been deleted. Pass ``form_progress__completed_time`` and
    ``form_progress__scores`` to seed a finished sitting.
    """

    class Meta:
        model = CourseFormAttempt
        exclude = ("form",)

    #: Not a field on the model -- it exists so both sub-factories below can
    #: agree on one form without the caller naming it twice.
    form = factory.SubFactory(FormFactory)

    course_progress = factory.SubFactory(CourseProgressFactory)
    form_progress = factory.SubFactory(
        FormProgressFactory,
        form=factory.SelfAttribute("..form"),
        user=factory.SelfAttribute("..course_progress.learner.user"),
        site=factory.SelfAttribute("..site"),
    )
    collection_item = factory.SubFactory(
        ContentCollectionItemFactory,
        collection_object=factory.SelfAttribute("..course_progress.course"),
        child_object=factory.SelfAttribute("..form"),
        site=factory.SelfAttribute("..site"),
    )
