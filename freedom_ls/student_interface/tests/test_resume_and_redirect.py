"""Tests for the resume redirect, last-accessed recording, and player helpers."""

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    FormPageFactory,
    TopicFactory,
)
from freedom_ls.student_interface.utils import (
    get_course_index,
    get_item_part,
    get_resume_index,
)
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.models import CourseProgress, FormProgress


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
        user=enrolled_user, course=course_structure["course"], current_index=2
    )
    part_dict = children[0]
    assert part_dict["contains_current"] is True
    # Topic B is the second child of the part and the current item.
    assert part_dict["children"][1]["is_current"] is True
    assert part_dict["children"][0]["is_current"] is False
    # Top-level topic C is index 3, not current.
    assert children[1]["is_current"] is False


# --- view_course_item records last-accessed item ------------------------------


@pytest.mark.django_db
def test_viewing_topic_records_last_accessed_item(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "student_interface:view_course_item",
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
        "student_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "student_interface:view_course_item",
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
        "student_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )


@pytest.mark.django_db
def test_course_home_unenrolled_redirects_to_preview(course_structure):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    url = reverse(
        "student_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "student_interface:course_preview", kwargs={"course_slug": "resume-course"}
    )


@pytest.mark.django_db
def test_course_home_anonymous_redirects_to_login(course_structure, client):
    url = reverse(
        "student_interface:course_home", kwargs={"course_slug": "resume-course"}
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
        "student_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302


# --- register_for_course lands in the player ----------------------------------


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
        "student_interface:view_course_item",
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
        "student_interface:view_course_item",
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
    # Item index 3 is Topic C, a top-level item with no part.
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )
    response = client.get(url)
    assert response.context["current_part"] is None


@pytest.mark.django_db
def test_breadcrumb_first_crumb_links_to_item_one_not_course_home(
    course_structure, enrolled_user
):
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )
    html = client.get(url).content.decode()
    item_one_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    assert item_one_url in html


@pytest.mark.django_db
def test_page_title_is_item_course_site(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    # Item index 3 (top-level, no part): "{item} — {course} — {site}".
    url = reverse(
        "student_interface:view_course_item",
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
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    html = client.get(url).content.decode()
    assert "Topic A — Chapter 1 — Resume Course —" in html


@pytest.mark.django_db
def test_register_for_course_lands_on_item_url(course_structure):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    url = reverse(
        "student_interface:register_for_course",
        kwargs={"course_slug": "resume-course"},
    )
    response = client.get(url, follow=True)
    # Final landing URL is a concrete item URL, not a rendered start page.
    final_url, _status = response.redirect_chain[-1]
    assert final_url == reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )


# --- query-count guard --------------------------------------------------------


@pytest.mark.django_db
def test_player_page_query_count_is_bounded(
    course_structure, enrolled_user, django_assert_max_num_queries
):
    """Pin the player page's query budget so regressions stay visible.

    The player chrome assembles the outline, breadcrumb part lookup, progress,
    and per-item status. ``view_course_item`` resolves ``viewable_items`` once
    and threads it into the chrome helper, and ``Course.children`` prefetches
    the generic-FK ``child``, so the page must not re-traverse the course or
    issue a per-item ``child`` lookup. The ceiling is comfortably above the
    current count (~47 for this 4-item fixture) but well below what a
    reintroduced full traversal or a child N+1 would cost.
    """
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    with django_assert_max_num_queries(55):
        response = client.get(url)
    assert response.status_code == 200
