"""Every learner-facing figure is read off the resolved course progress record.

These read paths fail silently: pointed at the wrong record they render a
perfectly plausible page at a perfectly plausible percentage. So each test here
asserts *whose* data reached the page, never that the page loaded.
"""

from __future__ import annotations

import re

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_interface.utils import (
    CourseListingStatus,
    get_completed_courses,
    get_course_index,
    get_course_listing,
    get_current_courses,
    get_resume_index,
    outstanding_items,
)
from freedom_ls.learner_interface.views import _detail_cta_label
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import course_progress_for

from .conftest import (
    collection_item_for,
    course_progress_record,
    form_attempt,
    learner_with_two_grants,
)


def _course_with_topics(
    title: str, slug: str, count: int
) -> tuple[Course, list[Topic]]:
    course: Course = CourseFactory(title=title, slug=slug)
    topics: list[Topic] = []
    for n in range(count):
        topic: Topic = TopicFactory(
            title=f"{title} {n}", slug=f"{slug}-{n}", content="x"
        )
        course.items.create(child=topic, order=n)
        topics.append(topic)
    return course, topics


def _quiz(title: str, slug: str) -> object:
    """A one-question quiz with a pass mark, so a wrong answer is a real fail."""
    quiz = FormFactory(
        title=title,
        slug=slug,
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=question, text="Right", correct=True, order=0)
    QuestionOptionFactory(question=question, text="Wrong", correct=False, order=1)
    return quiz


# --- get_resume_index ---------------------------------------------------------


@pytest.mark.django_db
def test_resume_index_reads_the_resolved_records_pointer(mock_site_context):
    """Two records, two pointers: the cohort one is the one the learner resumes at."""
    course, topics = _course_with_topics("Resume", "resume-scoping", 3)
    user, cohort_record, individual_record = learner_with_two_grants(course)
    cohort_record.last_accessed_item = collection_item_for(course, topics[1])
    cohort_record.save(update_fields=["last_accessed_item"])
    individual_record.last_accessed_item = collection_item_for(course, topics[2])
    individual_record.save(update_fields=["last_accessed_item"])

    assert get_resume_index(user, course) == 2


# --- _fetch_player_progress_maps / get_content_status -------------------------


@pytest.mark.django_db
def test_a_topic_placed_twice_shows_independent_status_at_each_position(
    mock_site_context,
):
    """Completing the first placement must not complete the second.

    The progress maps key on the collection item; a topic-keyed map would read
    both positions as COMPLETE off the one completion.
    """
    course: Course = CourseFactory(title="Twice", slug="twice")
    topic = TopicFactory(title="Repeated", slug="repeated", content="x")
    course.items.create(child=topic, order=0)
    course.items.create(child=topic, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    first_placement, _second_placement = course.viewable_collection_items()
    TopicProgressFactory(
        course_progress=course_progress_record(course, user),
        collection_item=first_placement,
        topic=topic,
        complete_time=timezone.now(),
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert [child["status"] for child in children] == ["COMPLETE", "READY"]


@pytest.mark.django_db
def test_a_topic_placed_twice_inside_a_part_shows_independent_status(
    mock_site_context,
):
    """The same, one level down -- the branch get_content_status recurses into."""
    course: Course = CourseFactory(title="Twice in a part", slug="twice-part")
    part = CoursePartFactory(title="Chapter", slug="twice-chapter")
    topic = TopicFactory(title="Repeated", slug="repeated-nested", content="x")
    course.items.create(child=part, order=0)
    part.items.create(child=topic, order=0)
    part.items.create(child=topic, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    first_placement, _second_placement = course.viewable_collection_items()
    TopicProgressFactory(
        course_progress=course_progress_record(course, user),
        collection_item=first_placement,
        topic=topic,
        complete_time=timezone.now(),
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert [child["status"] for child in children[0]["children"]] == [
        "COMPLETE",
        "READY",
    ]


@pytest.mark.django_db
def test_the_outline_reads_the_resolved_records_completions(mock_site_context):
    """A completion recorded against the other record leaves the outline untouched."""
    course, topics = _course_with_topics("Outline", "outline-scoping", 2)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    TopicProgressFactory(
        course_progress=individual_record,
        collection_item=collection_item_for(course, topics[0]),
        topic=topics[0],
        complete_time=timezone.now(),
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert [child["status"] for child in children] == ["READY", "BLOCKED"]


# --- outstanding_items --------------------------------------------------------


@pytest.mark.django_db
def test_a_quiz_failed_in_another_course_does_not_withhold_this_completion(
    mock_site_context,
):
    """The same quiz can be placed in two courses; only this course's sitting counts."""
    quiz = _quiz("Shared quiz", "shared-quiz")
    this_course: Course = CourseFactory(title="This", slug="this-course")
    this_course.items.create(child=quiz, order=0)
    other_course: Course = CourseFactory(title="Other", slug="other-course")
    other_course.items.create(child=quiz, order=0)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=this_course)
    LearnerCourseRegistrationFactory(learner__user=user, collection=other_course)

    form_attempt(
        other_course,
        user,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    form_attempt(
        this_course,
        user,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},
    )

    record = course_progress_for(user, this_course)
    assert record is not None
    assert outstanding_items(record, this_course) == []


@pytest.mark.django_db
def test_a_fail_under_the_other_record_does_not_withhold_this_completion(
    mock_site_context,
):
    """One course, two records: only the resolved record's sittings are read."""
    course: Course = CourseFactory(title="Two grants quiz", slug="two-grants-quiz")
    quiz = _quiz("Gate", "gate-quiz")
    course.items.create(child=quiz, order=0)
    _user, cohort_record, individual_record = learner_with_two_grants(course)
    placement = collection_item_for(course, quiz)
    CourseFormAttemptFactory(
        course_progress=individual_record,
        collection_item=placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 0, "max_score": 1},
    )
    CourseFormAttemptFactory(
        course_progress=cohort_record,
        collection_item=placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert outstanding_items(cohort_record, course) == []


@pytest.mark.django_db
def test_passing_one_placement_of_a_twice_placed_quiz_leaves_the_other_unpassed(
    mock_site_context,
):
    """Each placement is sat on its own, so a pass at one position cannot clear
    a fail at the other -- the learner still has that position to get right."""
    course: Course = CourseFactory(title="Twice", slug="twice-placed-quiz")
    quiz = _quiz("Repeated", "repeated-quiz")
    first_placement = course.items.create(child=quiz, order=0)
    second_placement = course.items.create(child=quiz, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=second_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 0, "max_score": 1},
    )
    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=first_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert [entry.index for entry in outstanding_items(record, course)] == [2]


@pytest.mark.django_db
def test_a_never_sat_placement_of_a_twice_placed_quiz_is_outstanding(mock_site_context):
    """Passing one placement leaves the other to sit, not to skip.

    The completion this withholds is the one QA caught being stamped at 88%
    with the second placement still reading "Not started".
    """
    course: Course = CourseFactory(title="Twice unsat", slug="twice-placed-unsat")
    quiz = _quiz("Repeated unsat", "repeated-unsat-quiz")
    first_placement = course.items.create(child=quiz, order=0)
    course.items.create(child=quiz, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=first_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert [entry.index for entry in outstanding_items(record, course)] == [2]


@pytest.mark.django_db
def test_a_retry_is_only_offered_where_there_is_a_sitting_to_retry(mock_site_context):
    """The two kinds of outstanding quiz are told apart, so the page can word each one."""
    course: Course = CourseFactory(title="Retry flag", slug="retry-flag-course")
    failed = _quiz("Failed", "retry-flag-failed")
    untouched = _quiz("Untouched", "retry-flag-untouched")
    failed_placement = course.items.create(child=failed, order=0)
    course.items.create(child=untouched, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=failed_placement,
        form=failed,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 0, "max_score": 1},
    )

    assert [
        (entry.index, entry.is_retry) for entry in outstanding_items(record, course)
    ] == [
        (1, True),
        (2, False),
    ]


@pytest.mark.django_db
def test_an_unread_topic_is_outstanding_alongside_the_quizzes(mock_site_context):
    """A course is complete when every item is, so a topic withholds it too."""
    course: Course = CourseFactory(title="Mixed", slug="outstanding-mixed")
    topic: Topic = TopicFactory(
        title="Read me", slug="outstanding-read-me", content="x"
    )
    quiz = _quiz("Gate", "outstanding-gate")
    course.items.create(child=topic, order=0)
    quiz_placement = course.items.create(child=quiz, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=quiz_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert [entry.content for entry in outstanding_items(record, course)] == [topic]


# --- the three listings -------------------------------------------------------


@pytest.mark.django_db
def test_completed_courses_follow_the_resolved_record(mock_site_context):
    """A completion on the losing record must not mark the course finished."""
    course, _topics = _course_with_topics("Listing", "listing-completion", 1)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    individual_record.completed_time = timezone.now()
    individual_record.save(update_fields=["completed_time"])

    assert get_completed_courses(user) == []


@pytest.mark.django_db
def test_a_course_completed_on_the_resolved_record_is_listed_once(mock_site_context):
    """Two records for one course, one row in the history -- not two."""
    course, _topics = _course_with_topics("Listing", "listing-once", 1)
    user, cohort_record, _individual_record = learner_with_two_grants(course)
    cohort_record.completed_time = timezone.now()
    cohort_record.save(update_fields=["completed_time"])

    assert get_completed_courses(user) == [course]


@pytest.mark.django_db
def test_current_courses_show_the_resolved_records_percentage(mock_site_context):
    course, _topics = _course_with_topics("Listing", "listing-current", 1)
    user, cohort_record, individual_record = learner_with_two_grants(course)
    cohort_record.progress_percentage = 40
    cohort_record.save(update_fields=["progress_percentage"])
    individual_record.progress_percentage = 90
    individual_record.save(update_fields=["progress_percentage"])

    current = get_current_courses(user)

    assert [c.progress_percentage for c in current] == [40]


@pytest.mark.django_db
def test_a_course_completed_on_the_losing_record_stays_in_current_courses(
    mock_site_context,
):
    """Still in progress under the registration the learner is studying through."""
    course, _topics = _course_with_topics("Listing", "listing-still-current", 1)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    individual_record.completed_time = timezone.now()
    individual_record.save(update_fields=["completed_time"])

    assert get_current_courses(user) == [course]


@pytest.mark.django_db
def test_the_all_courses_listing_shows_the_resolved_records_percentage(
    mock_site_context,
):
    course, _topics = _course_with_topics("Listing", "listing-all-courses", 1)
    user, cohort_record, individual_record = learner_with_two_grants(course)
    cohort_record.progress_percentage = 25
    cohort_record.save(update_fields=["progress_percentage"])
    individual_record.progress_percentage = 100
    individual_record.completed_time = timezone.now()
    individual_record.save(update_fields=["progress_percentage", "completed_time"])

    entries = [entry for entry in get_course_listing(user) if entry.course == course]

    assert len(entries) == 1
    assert entries[0].progress_percentage == 25
    assert entries[0].status == CourseListingStatus.IN_PROGRESS


# --- _detail_cta_label --------------------------------------------------------


@pytest.mark.django_db
def test_a_registered_learner_who_never_opened_the_course_is_offered_start(
    mock_site_context,
):
    """The record exists from registration, so row-existence cannot mean "started"."""
    course, _topics = _course_with_topics("CTA", "cta-start", 1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)

    assert record.progress_percentage == 0
    assert record.started_at is None
    assert _detail_cta_label(course, user) == "Start course"


@pytest.mark.django_db
def test_the_cta_reads_the_resolved_records_progress(mock_site_context):
    """Progress on the losing record must not turn Start into Continue."""
    course, _topics = _course_with_topics("CTA", "cta-continue", 1)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    individual_record.progress_percentage = 60
    individual_record.save(update_fields=["progress_percentage"])

    assert _detail_cta_label(course, user) == "Start course"


# --- the completion page's Started row ----------------------------------------


@pytest.mark.django_db
def test_course_finish_dates_the_start_from_content_access_not_registration(
    mock_site_context,
):
    """The registration is old; the learner began this month. The page says this month.

    ``created_at`` is the registration date, so binding the row to it would
    label the wrong day -- and Django resolves a wrong attribute name to the
    empty string rather than raising, so nothing else catches it.
    """
    course, _topics = _course_with_topics("Finish", "finish-started", 1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)
    registered_at = timezone.now() - timezone.timedelta(days=400)
    CourseProgress.objects.filter(pk=record.pk).update(created_at=registered_at)
    began_at = timezone.now()
    record.started_at = began_at
    record.save(update_fields=["started_at"])

    client = Client()
    client.force_login(user)
    body = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    ).content.decode()

    summary = re.sub(r"\s+", " ", body)
    assert f"Started:</span> <span>{began_at.strftime('%B %-d, %Y')}</span>" in summary
    assert registered_at.strftime("%B %-d, %Y") not in summary


@pytest.mark.django_db
def test_course_finish_omits_the_started_row_when_nothing_was_recorded(
    mock_site_context,
):
    """A null start renders no row at all, never a labelled blank."""
    course, _topics = _course_with_topics("Finish", "finish-no-start", 1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    record = course_progress_record(course, user)
    assert record.started_at is None

    client = Client()
    client.force_login(user)
    body = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    ).content.decode()

    assert "Course Summary" in body
    assert "Started:" not in body


# --- the topic player's mark-complete button ----------------------------------


@pytest.mark.django_db
def test_a_learner_with_no_record_is_offered_no_mark_complete_button(
    mock_site_context, settings
):
    """Read-only degradation: nothing to write to, so no button that cannot work."""
    from freedom_ls.course_access.loader import get_course_access_backend

    course, _topics = _course_with_topics("Degraded", "degraded-topic", 2)
    user: User = UserFactory()  # never registered -- no record can be resolved
    settings.COURSE_ACCESS_BACKEND = (
        "freedom_ls.learner_interface.tests.test_player_progress_scoping"
        ".ContentWithoutRegistrationBackend"
    )
    get_course_access_backend.cache_clear()

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    get_course_access_backend.cache_clear()

    assert response.status_code == 200
    assert response.context["can_record_progress"] is False
    assert 'name="mark_complete"' not in response.content.decode()


@pytest.mark.django_db
def test_a_registered_learner_is_offered_the_mark_complete_button(mock_site_context):
    """The positive control -- otherwise the absence test above proves nothing."""
    course, _topics = _course_with_topics("Recorded", "recorded-topic", 2)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    assert response.context["can_record_progress"] is True
    assert 'name="mark_complete"' in response.content.decode()
