"""Tests for the resume redirect, last-accessed recording, and player helpers."""

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import FormStrategy
from freedom_ls.learner_interface.utils import (
    current_entry_status,
    get_course_index,
    get_item_part,
    get_resume_index,
)
from freedom_ls.learner_management.factories import UserCourseRegistrationFactory
from freedom_ls.learner_progress.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
)
from freedom_ls.learner_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)
from freedom_ls.role_based_permissions.loader import clear_caches


@pytest.fixture
def course_structure(mock_site_context):
    """Course: part "Chapter 1" [topic A (1), topic B (2)] + top-level topic C (3)."""
    course = CourseFactory(title="Resume Course", slug="resume-course")
    part = CoursePartFactory(title="Chapter 1", slug="chapter-1")
    topic_a = TopicFactory(title="Topic A", slug="topic-a", content="A")
    topic_b = TopicFactory(title="Topic B", slug="topic-b", content="B")
    topic_c = TopicFactory(title="Topic C", slug="topic-c", content="C")
    course.items.create(child=part, order=0)
    part.items.create(child=topic_a, order=0)
    part.items.create(child=topic_b, order=1)
    course.items.create(child=topic_c, order=1)
    return {
        "course": course,
        "part": part,
        "topic_a": topic_a,
        "topic_b": topic_b,
        "topic_c": topic_c,
    }


@pytest.fixture
def enrolled_user(mock_site_context, course_structure):
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_structure["course"])
    return user


def complete_topics(user, *topics):
    """Clear the sequential-unlock gate ahead of the item a test wants to open.

    These tests are about breadcrumbs, titles and resume bookkeeping, not about
    gating, so they open items further in than a learner with no progress could
    reach on their own.
    """
    for topic in topics:
        TopicProgress.objects.create(
            user=user, topic=topic, complete_time=timezone.now()
        )


# --- get_resume_index ---------------------------------------------------------


@pytest.mark.django_db
def test_resume_index_no_progress_returns_one(course_structure, enrolled_user):
    assert get_resume_index(enrolled_user, course_structure["course"]) == 1


@pytest.mark.django_db
def test_resume_index_null_item_returns_one(course_structure, enrolled_user):
    CourseProgress.objects.create(user=enrolled_user, course=course_structure["course"])
    assert get_resume_index(enrolled_user, course_structure["course"]) == 1


@pytest.mark.django_db
def test_resume_index_maps_stored_item_to_its_index(course_structure, enrolled_user):
    cp = CourseProgress.objects.create(
        user=enrolled_user, course=course_structure["course"]
    )
    cp.last_accessed_item = course_structure["topic_b"]
    cp.save()
    # Topic B is the second viewable item.
    assert get_resume_index(enrolled_user, course_structure["course"]) == 2


@pytest.mark.django_db
def test_resume_index_stored_item_no_longer_viewable_falls_back(
    course_structure, enrolled_user
):
    cp = CourseProgress.objects.create(
        user=enrolled_user, course=course_structure["course"]
    )
    cp.last_accessed_item = course_structure["topic_b"]
    cp.save()
    # Remove topic B from the course; it is no longer viewable.
    course_structure["part"].items.filter(
        child_id=course_structure["topic_b"].pk
    ).delete()
    assert get_resume_index(enrolled_user, course_structure["course"]) == 1


# --- get_item_part ------------------------------------------------------------


@pytest.mark.django_db
def test_get_item_part_returns_containing_part(course_structure):
    part = get_item_part(course_structure["course"], course_structure["topic_a"])
    assert part == course_structure["part"]


@pytest.mark.django_db
def test_get_item_part_top_level_item_returns_none(course_structure):
    assert (
        get_item_part(course_structure["course"], course_structure["topic_c"]) is None
    )


# --- current-item marking in get_course_index ---------------------------------


@pytest.mark.django_db
def test_get_course_index_marks_current_item(course_structure, enrolled_user):
    children = get_course_index(
        user=enrolled_user,
        course=course_structure["course"],
        current_index=2,
        can_access_content=True,
    )
    part_dict = children[0]
    assert part_dict["contains_current"] is True
    # Topic B is the second child of the part and the current item.
    assert part_dict["children"][1]["is_current"] is True
    assert part_dict["children"][0]["is_current"] is False
    # Top-level topic C is index 3, not current.
    assert children[1]["is_current"] is False


@pytest.mark.django_db
def test_current_entry_status_reads_a_row_nested_inside_a_part(
    course_structure, enrolled_user
):
    """The player's gate reads its answer off this row, and items inside a part
    are one level further down than the loop's own iteration."""
    children = get_course_index(
        user=enrolled_user,
        course=course_structure["course"],
        current_index=2,
        can_access_content=True,
    )

    assert current_entry_status(children) == "BLOCKED"


@pytest.mark.django_db
def test_current_entry_status_is_none_when_no_row_is_current(
    course_structure, enrolled_user
):
    """Callers read None as "not blocked", so it must only arise with no current row."""
    children = get_course_index(
        user=enrolled_user,
        course=course_structure["course"],
        can_access_content=True,
    )

    assert current_entry_status(children) is None


# --- view_course_item records last-accessed item ------------------------------


@pytest.mark.django_db
def test_viewing_topic_records_last_accessed_item(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    complete_topics(enrolled_user, course_structure["topic_a"])
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 2},
    )
    response = client.get(url)
    assert response.status_code == 200
    cp = CourseProgress.objects.get(
        user=enrolled_user, course=course_structure["course"]
    )
    assert cp.last_accessed_item == course_structure["topic_b"]


# --- course_home redirector ---------------------------------------------------


@pytest.mark.django_db
def test_course_home_enrolled_no_progress_redirects_to_item_one(
    course_structure, enrolled_user
):
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )


@pytest.mark.django_db
def test_course_home_enrolled_with_progress_redirects_to_last_item(
    course_structure, enrolled_user
):
    cp = CourseProgress.objects.create(
        user=enrolled_user, course=course_structure["course"]
    )
    cp.last_accessed_item = course_structure["topic_c"]
    cp.save()
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )


@pytest.mark.django_db
def test_course_home_unenrolled_redirects_to_detail(course_structure):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": "resume-course"}
    )


@pytest.mark.django_db
def test_course_home_anonymous_redirects_to_login(course_structure, client):
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.url


@pytest.mark.django_db
def test_course_home_never_renders_start_page(course_structure, enrolled_user):
    """The bare URL is always a 302, never a 200 HTML start page."""
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302


# --- initiate_course_access lands in the player -------------------------------


# --- view_form GET does not mint a spurious FormProgress ---------------------


@pytest.mark.django_db
def test_viewing_form_does_not_create_form_progress(mock_site_context):
    """A bare GET of a form item must not fabricate an in-progress attempt.

    Resume is driven by CourseProgress.last_accessed_item, not FormProgress
    timestamps, so view_form must not touch FormProgress on GET.
    """
    course = CourseFactory(title="Form Course", slug="form-course")
    form = FormFactory(title="A Form", slug="a-form")
    FormPageFactory(form=form, title="Page 1", slug="page-1", order=0)
    course.items.create(child=form, order=0)
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)

    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "form-course", "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert not FormProgress.objects.filter(user=user, form=form).exists()
    # But the form IS recorded as the resume target.
    cp = CourseProgress.objects.get(user=user, course=course)
    assert cp.last_accessed_item == form


# --- breadcrumb + page title -------------------------------------------------


@pytest.mark.django_db
def test_breadcrumb_includes_part_when_item_in_part(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    # Item index 1 is Topic A, inside the "Chapter 1" part.
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    response = client.get(url)
    html = response.content.decode()
    # The part title appears in the breadcrumb trail.
    assert "Chapter 1" in html
    # The current item is exposed as the current page (non-linked).
    assert 'aria-current="page"' in html
    assert response.context["current_part"] == course_structure["part"]


@pytest.mark.django_db
def test_breadcrumb_drops_part_when_item_top_level(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    complete_topics(
        enrolled_user, course_structure["topic_a"], course_structure["topic_b"]
    )
    # Item index 3 is Topic C, a top-level item with no part.
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )
    response = client.get(url)
    assert response.context["current_part"] is None


@pytest.mark.django_db
def test_page_title_is_item_course_site(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    complete_topics(
        enrolled_user, course_structure["topic_a"], course_structure["topic_b"]
    )
    # Item index 3 (top-level, no part): "{item} — {course} — {site}".
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )
    html = client.get(url).content.decode()
    assert "Topic C — Resume Course —" in html


@pytest.mark.django_db
def test_page_title_includes_part_when_present(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    # Item index 1 (Topic A inside Chapter 1): part sits between item and course.
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    html = client.get(url).content.decode()
    assert "Topic A — Chapter 1 — Resume Course —" in html


@pytest.mark.django_db
def test_initiate_course_access_lands_on_item_url(course_structure):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": "resume-course"},
    )
    response = client.get(url, follow=True)
    # Final landing URL is a concrete item URL, not a rendered start page.
    final_url, _status = response.redirect_chain[-1]
    assert final_url == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )


# --- query-count guard --------------------------------------------------------


@pytest.mark.django_db
def test_player_page_query_count_is_bounded(
    course_structure, enrolled_user, django_assert_max_num_queries
):
    """Pin the player page's query budget so regressions stay visible.

    The player chrome assembles the outline, breadcrumb part lookup, progress,
    and per-item status. The budget is independent of item count because the
    page (a) walks the course tree once -- ``Course.children`` /
    ``CoursePart.children`` memoize per instance, so the repeated chrome
    traversals share one resolution -- and (b) bulk-fetches all topic/form
    progress into maps via ``_fetch_player_progress_maps`` instead of one query
    per item. The ceiling sits just above the current count (41 for this
    4-item fixture) but well below what a reintroduced full traversal or a
    per-item progress N+1 would cost. See
    ``test_player_page_query_count_does_not_grow_with_items``.

    A few of those queries belong to the header, which asks whether this user
    may enter the educator interface. That lookup is memoized in a process-wide
    cache, so the count depends on whether an earlier test happened to warm it.
    Clearing it first makes this the cold-cache number either way, rather than
    leaving a couple of queries of slack for test order to move around in.
    """
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    clear_caches()
    with django_assert_max_num_queries(41):
        response = client.get(url)
    assert response.status_code == 200


@pytest.fixture
def big_course(mock_site_context):
    """Course with a 10-topic part plus 3 top-level forms (13 viewable items).

    Used to prove the player's query budget does not grow per item: a per-item
    progress N+1 or a re-traversal would blow past the same ceiling the tiny
    4-item fixture lives under.
    """
    course = CourseFactory(title="Big Course", slug="big-course")
    part = CoursePartFactory(title="Big Chapter", slug="big-chapter")
    course.items.create(child=part, order=0)
    for n in range(10):
        topic = TopicFactory(title=f"BT {n}", slug=f"bt-{n}", content="x")
        part.items.create(child=topic, order=n)
    for n in range(3):
        form = FormFactory(title=f"BF {n}", slug=f"bf-{n}")
        course.items.create(child=form, order=n + 1)
    return course


@pytest.mark.django_db
def test_player_page_query_count_does_not_grow_with_items(
    big_course, django_assert_max_num_queries
):
    """Nine extra items cost one extra query, not nine.

    The 4-item fixture above sits at 41 cold; this 13-item one sits at 42. A
    per-item progress N+1 (or a per-caller re-traversal) would put it near 50.
    The ceiling is one above the small-course count deliberately -- leaving
    more slack than that would let a real N+1 hide inside it.
    """
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=big_course)
    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "big-course", "index": 1},
    )
    clear_caches()
    with django_assert_max_num_queries(42):
        response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_course_index_status_semantics_preserved(mock_site_context):
    """Bulk-fetched progress yields the same per-item statuses + next_status flow.

    Covers every status value and the next_status propagation (an untouched item
    after a READY one becomes BLOCKED; completed/failed/in-progress items are
    independent of next_status).
    """
    course = CourseFactory(title="Status Course", slug="status-course")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    now = timezone.now()

    topic_complete = TopicFactory(title="T complete", slug="t-complete", content="x")
    topic_ready = TopicFactory(title="T ready", slug="t-ready", content="x")
    topic_blocked = TopicFactory(title="T blocked", slug="t-blocked", content="x")
    topic_in_progress = TopicFactory(title="T wip", slug="t-wip", content="x")
    quiz_passed = FormFactory(
        title="Q passed",
        slug="q-passed",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    quiz_failed = FormFactory(
        title="Q failed",
        slug="q-failed",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    form_done = FormFactory(title="F done", slug="f-done")
    form_untouched = FormFactory(title="F untouched", slug="f-untouched")

    ordered = [
        topic_complete,
        topic_ready,
        topic_blocked,
        topic_in_progress,
        quiz_passed,
        quiz_failed,
        form_done,
        form_untouched,
    ]
    for order, item in enumerate(ordered):
        course.items.create(child=item, order=order)

    TopicProgress.objects.create(user=user, topic=topic_complete, complete_time=now)
    TopicProgress.objects.create(user=user, topic=topic_in_progress)
    FormProgress.objects.create(
        user=user,
        form=quiz_passed,
        completed_time=now,
        scores={"score": 8, "max_score": 10},
    )
    FormProgress.objects.create(
        user=user,
        form=quiz_failed,
        completed_time=now,
        scores={"score": 5, "max_score": 10},
    )
    FormProgress.objects.create(user=user, form=form_done, completed_time=now)

    children = get_course_index(user=user, course=course, can_access_content=True)
    statuses = [c["status"] for c in children]
    assert statuses == [
        "COMPLETE",
        "READY",
        "BLOCKED",
        "IN_PROGRESS",
        "COMPLETE",
        "FAILED",
        "COMPLETE",
        "READY",
    ]


@pytest.mark.django_db
def test_checkbox_quiz_ticking_every_option_blocks_navigation_as_failed(
    mock_site_context,
):
    """Regression test for the exact-match scoring fix: a checkbox quiz answered by
    ticking every option used to score 100% and read COMPLETE; it must now read
    FAILED and block progression via `next_status`."""
    course = CourseFactory(title="Checkbox Course", slug="checkbox-course")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)

    quiz = FormFactory(
        title="Checkbox quiz",
        slug="checkbox-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
    )
    topic_after = TopicFactory(
        title="After the quiz", slug="after-the-quiz", content="x"
    )
    course.items.create(child=quiz, order=0)
    course.items.create(child=topic_after, order=1)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    correct_1 = QuestionOptionFactory(question=question, correct=True, order=0)
    correct_2 = QuestionOptionFactory(question=question, correct=True, order=1)
    wrong_1 = QuestionOptionFactory(question=question, correct=False, order=2)
    wrong_2 = QuestionOptionFactory(question=question, correct=False, order=3)

    form_progress = FormProgressFactory(user=user, form=quiz)
    answer = QuestionAnswerFactory(form_progress=form_progress, question=question)
    answer.selected_options.add(correct_1, correct_2, wrong_1, wrong_2)
    form_progress.complete()

    children = get_course_index(user=user, course=course, can_access_content=True)
    statuses = [c["status"] for c in children]
    assert statuses == ["FAILED", "BLOCKED"]


@pytest.mark.django_db
def test_children_memoized_second_call_issues_no_queries(course_structure):
    """Course.children() caches per instance: a warmed call hits the DB zero times."""
    course = course_structure["course"]
    first = course.children()
    with CaptureQueriesContext(connection) as ctx:
        second = course.children()
    assert len(ctx.captured_queries) == 0
    assert [type(c) for c in second] == [type(c) for c in first]


@pytest.mark.django_db
def test_get_course_index_unregistered_user_skips_progress_queries(mock_site_context):
    """An authenticated-but-unregistered user reads no progress rows (all BLOCKED)."""
    course = CourseFactory(title="Closed Course", slug="closed-course")
    topic = TopicFactory(title="Locked", slug="locked", content="x")
    form = FormFactory(title="Locked form", slug="locked-form")
    course.items.create(child=topic, order=0)
    course.items.create(child=form, order=1)
    user = UserFactory()  # not registered for the course

    with CaptureQueriesContext(connection) as ctx:
        children = get_course_index(user=user, course=course, can_access_content=False)

    assert [c["status"] for c in children] == ["BLOCKED", "BLOCKED"]
    sql = " ".join(q["sql"].lower() for q in ctx.captured_queries)
    assert "learner_progress_topicprogress" not in sql
    assert "learner_progress_formprogress" not in sql
