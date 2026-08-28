"""The player's writes land in the resolved course progress record, and only there.

A learner can hold two registrations for one course, and therefore two records.
Everything the player writes -- the resume pointer, topic completions, form
attempts -- has to land in the one the registration order resolves to, and must
leave the other alone.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.course_access.backends import (
    CourseAccessDecision,
    FreeOnlyCourseAccessBackend,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
)
from freedom_ls.learner_progress.attempts import get_or_create_incomplete
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory

from .conftest import (
    collection_item_for,
    course_progress_record,
    learner_with_two_grants,
    register_user_for_course,
)

BACKEND_PATH = (
    "freedom_ls.learner_interface.tests.test_player_progress_scoping"
    ".ContentWithoutRegistrationBackend"
)


class ContentWithoutRegistrationBackend(FreeOnlyCourseAccessBackend):
    """A downstream-shaped backend that opens content to everyone.

    Core FLS cannot produce a learner with content access and no registration --
    every ``can_access_content=True`` branch is gated on one -- so the read-only
    degradation can only be exercised through a backend like this.
    """

    def get_access(self, *, user, course) -> CourseAccessDecision:
        return CourseAccessDecision(
            cta_label=None,
            cta_url=None,
            can_self_register=False,
            can_access_content=True,
        )


def _item_url(course: Course, index: int) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": index},
    )


def _mark_complete(client, course: Course, index: int) -> None:
    """Complete the item at `index`, which is what unlocks the one after it."""
    client.post(_item_url(course, index), {"mark_complete": "1"})


def _course_with_topics(*titles: str) -> Course:
    course: Course = CourseFactory()
    for order, title in enumerate(titles):
        topic = TopicFactory(title=title)
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=order
        )
    return course


# ---------------------------------------------------------------------------
# Degradation: content access without a registration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_player_renders_for_a_learner_with_no_registration(
    mock_site_context, client
):
    """A backend may open content to an unregistered learner; the player must cope."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        response = client.get(_item_url(course, 1))

    assert response.status_code == 200


@pytest.mark.django_db
def test_no_progress_is_written_for_a_learner_with_no_registration(
    mock_site_context, client
):
    """Nothing grants the course, so nothing may be recorded against it."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        client.get(_item_url(course, 1))

    assert not CourseProgress.objects.exists()
    assert not TopicProgress.objects.exists()


@pytest.mark.django_db
def test_the_player_reports_that_progress_cannot_be_recorded(mock_site_context, client):
    """The templates hide the completion control off this flag."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        response = client.get(_item_url(course, 1))

    assert response.context["can_record_progress"] is False


@pytest.mark.django_db
def test_marking_complete_without_a_registration_is_a_404(mock_site_context, client):
    """There is nowhere to record the completion, so the POST must not succeed."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        response = client.post(_item_url(course, 1), {"mark_complete": "1"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_registered_learner_can_record_progress(mock_site_context, client):
    """The same flag is True on the ordinary path, so the control is offered."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    course_progress_record(course, user)
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert response.context["can_record_progress"] is True


# ---------------------------------------------------------------------------
# The resume pointer and the started_at stamp
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_resume_pointer_records_the_collection_item(mock_site_context, client):
    """The pointer names a position in the course, not the content it resolves to."""
    course = _course_with_topics("First", "Second")
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    _mark_complete(client, course, 1)

    client.get(_item_url(course, 2))

    record.refresh_from_db()
    assert record.last_accessed_item == course.viewable_collection_items()[1]


@pytest.mark.django_db
def test_a_topic_placed_twice_resumes_to_the_position_visited(
    mock_site_context, client
):
    """Two placements of one topic are two positions, and resume must tell them apart."""
    course: Course = CourseFactory()
    topic = TopicFactory(title="Repeated Topic")
    filler = TopicFactory(title="Filler")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=filler, order=1)
    second_placement = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=2
    )
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    _mark_complete(client, course, 1)
    _mark_complete(client, course, 2)

    client.get(_item_url(course, 3))

    record.refresh_from_db()
    assert record.last_accessed_item == second_placement


@pytest.mark.django_db
def test_started_at_is_stamped_on_first_content_access(mock_site_context, client):
    """Registration mints the record; opening the content is what starts it."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    record = course_progress_record(course, user)
    assert record.started_at is None
    client.force_login(user)

    client.get(_item_url(course, 1))

    record.refresh_from_db()
    assert record.started_at is not None


@pytest.mark.django_db
def test_started_at_is_not_re_stamped_on_a_later_visit(mock_site_context, client):
    """ "Started" is the first visit, so a second visit must leave it alone."""
    course = _course_with_topics("First", "Second")
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    client.get(_item_url(course, 1))
    record.refresh_from_db()
    first_stamp = record.started_at

    client.get(_item_url(course, 2))

    record.refresh_from_db()
    assert record.started_at == first_stamp


@pytest.mark.django_db
def test_a_percentage_recalculation_does_not_bump_last_accessed_time(
    mock_site_context, client
):
    """last_accessed_time is the player's to write; a background write is not a visit."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    client.get(_item_url(course, 1))
    record.refresh_from_db()
    visited_at = record.last_accessed_time

    record.progress_percentage = 50
    record.save(update_fields=["progress_percentage"])

    record.refresh_from_db()
    assert record.last_accessed_time == visited_at


# ---------------------------------------------------------------------------
# One learner, two grants
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_completing_an_item_moves_only_the_resolved_records_percentage(
    mock_site_context, client
):
    """The cohort registration wins, so only the cohort record's percentage moves."""
    course = _course_with_topics("Only Topic")
    user, cohort_record, individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    cohort_record.refresh_from_db()
    individual_record.refresh_from_db()
    assert cohort_record.progress_percentage == 100
    assert individual_record.progress_percentage == 0


@pytest.mark.django_db
def test_the_unresolved_record_keeps_no_resume_pointer(mock_site_context, client):
    """The individual record is a separate pass; visiting the course is not its visit."""
    course = _course_with_topics("Only Topic")
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    individual_record.refresh_from_db()
    assert individual_record.last_accessed_item is None


@pytest.mark.django_db
def test_the_unresolved_record_is_never_started(mock_site_context, client):
    """started_at belongs to the pass the learner actually made."""
    course = _course_with_topics("Only Topic")
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    individual_record.refresh_from_db()
    assert individual_record.started_at is None


@pytest.mark.django_db
def test_the_completion_is_recorded_against_the_resolved_record(
    mock_site_context, client
):
    """One TopicProgress row, and it hangs off the cohort record."""
    course = _course_with_topics("Only Topic")
    user, cohort_record, _individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    completions = TopicProgress.objects.filter(complete_time__isnull=False)
    assert [c.course_progress_id for c in completions] == [cohort_record.id]


@pytest.mark.django_db
def test_the_finish_page_mints_the_record_a_bare_registration_never_had(
    mock_site_context, client
):
    """Every player entry point self-heals, the finish page included.

    A registration made before course progress records existed has no record
    until the learner opens the course. Reaching the finish page directly --
    a bookmark, or the back button after the completion redirect -- has to
    mint it too, or the page 404s on a registration that plainly grants the
    course.
    """
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    register_user_for_course(course, user)
    CourseProgress.objects.all().delete()
    assert not CourseProgress.objects.exists()
    client.force_login(user)

    response = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )

    assert response.status_code == 200
    assert CourseProgress.objects.filter(learner__user=user, course=course).count() == 1


# ---------------------------------------------------------------------------
# One user, two organisations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_finishing_the_course_in_one_organisation_leaves_the_others_completed_time_and_resume_pointer_untouched(
    mock_site_context, client
):
    """A person studying the same course through two organisations holds two
    Learner rows and therefore two records. Finishing under the registration
    order resolves to must not stamp completed_time or the resume pointer
    onto the other organisation's record -- each organisation's pass is its
    own."""
    course = _course_with_topics("Only Topic")
    user = UserFactory()
    other_registration = LearnerCourseRegistrationFactory(
        learner__user=user,
        collection=course,
        learner__organisation=OrganisationFactory(),
    )
    resolved_registration = LearnerCourseRegistrationFactory(
        learner__user=user,
        collection=course,
        learner__organisation=OrganisationFactory(),
    )
    other_record = ensure_course_progress_record(
        other_registration.learner, course, other_registration
    )
    ensure_course_progress_record(
        resolved_registration.learner, course, resolved_registration
    )
    client.force_login(user)
    # Stamps last_accessed_item on whichever record the registration order
    # resolves to -- the more recently registered one, per learner_for_course.
    _mark_complete(client, course, 1)

    client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )

    other_record.refresh_from_db()
    assert other_record.completed_time is None
    assert other_record.last_accessed_item is None


# ---------------------------------------------------------------------------
# Form attempts are scoped to the record and the placement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_an_open_attempt_under_another_record_is_not_resumed(
    mock_site_context, client, course_with_scored_quiz
):
    """An attempt started under one registration must never be resumed under another."""
    course, form, _question, _right, _wrong = course_with_scored_quiz()
    user, cohort_record, individual_record = learner_with_two_grants(course)
    get_or_create_incomplete(individual_record, collection_item_for(course, form))
    client.force_login(user)

    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    assert CourseFormAttempt.objects.filter(course_progress=cohort_record).count() == 1


@pytest.mark.django_db
def test_the_start_screen_ignores_an_attempt_under_another_record(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A sitting made under the other registration is not this record's history."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    sit_quiz(individual_record, form, question, right)
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert list(response.context["completed_form_progress"]) == []


@pytest.mark.django_db
def test_two_placements_of_one_form_keep_separate_attempts(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Answering a quiz at one position says nothing about the same quiz elsewhere."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    user = UserFactory()
    record = course_progress_record(course, user)
    sit_quiz(record, form, question, right)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=1)
    client.force_login(user)

    response = client.get(_item_url(course, 2))

    assert list(response.context["completed_form_progress"]) == []


@pytest.mark.django_db
def test_a_completed_attempt_in_another_course_is_not_this_courses_history(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """The same form placed in two courses is answered separately in each."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    other_course: Course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=other_course, child_object=form, order=0
    )
    user = UserFactory()
    other_record = course_progress_record(other_course, user)
    course_progress_record(course, user)
    sit_quiz(other_record, form, question, right)
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert list(response.context["completed_form_progress"]) == []


@pytest.mark.django_db
def test_a_deadline_lock_ignores_a_completion_in_another_course(
    mock_site_context, client, settings
):
    """A hard deadline locks the item here even though the topic is done elsewhere."""
    settings.DEADLINES_ACTIVE = True
    topic = TopicFactory(title="Shared Topic")
    course: Course = CourseFactory()
    other_course: Course = CourseFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(
        collection_object=other_course, child_object=topic, order=0
    )
    user = UserFactory()
    record = course_progress_record(course, user)
    other_record = course_progress_record(other_course, user)
    TopicProgressFactory(
        course_progress=other_record,
        collection_item=collection_item_for(other_course, topic),
        topic=topic,
        complete_time=timezone.now(),
    )
    LearnerDeadlineFactory(
        learner_course_registration=record.learner_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
