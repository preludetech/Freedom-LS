"""Tests for the course listing pages: the all-courses page, the course cards and the anonymous home page."""

from __future__ import annotations

import re

import pytest

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.db.models import QuerySet
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import (
    SiteFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.learner_interface.tests.helpers import (
    rendered_section,
    section_by_slug,
    topic_completion,
)
from freedom_ls.learner_interface.utils import (
    CourseListingEntry,
    CourseListingStatus,
    get_course_listing,
)
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.tests.helpers import course_progress_record

# Tests for the all_courses view at the context level.
#
# These exercise the status/annotation logic the view attaches to each course
# object it puts in the ``all_courses`` context: listing_status, progress
# percentage, accent slot, and the absence of next_up_*
# annotations. Rendered-HTML row assertions follow further down.


# The wrapper the express-interest partial renders around its call to action.
EXPRESS_INTEREST_CTA = 'id="express-interest-cta-'


@pytest.mark.django_db
def test_all_courses_started_course_has_progress_percentage(
    mock_site_context, courses, logged_in_client
):
    """Started courses in the all_courses view should have progress_percentage for progress bars."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    started_course = next(c for c in all_courses_list if c.id == courses[0].id)
    # Real-value assertion: a freshly-registered course with no topic
    # completion has a progress percentage of 0. `hasattr` only proved the
    # attribute existed; this proves the annotation produced the right value.
    assert started_course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_annotates_accent_slot_key(
    mock_site_context, courses, logged_in_client
):
    """Every course returned to the all_courses page has an ``accent_slot_key``."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    from freedom_ls.content_engine.course_accent import PALETTE

    all_courses_list = list(response.context["all_courses"])
    assert all_courses_list, "Expected at least one course in the catalogue"
    assert all(c.accent_slot_key in PALETTE for c in all_courses_list)


# Tests for the rendered HTML of all_courses rows.
#
# These assert on the markup the all_courses page produces for each
# registration state: status labels, preview/link affordances, progress-bar
# presence and value, and decorative status icons. The context-level
# status/annotation logic is covered by the context-level tests above.


def _coming_soon_course(*, slug: str, title: str) -> Course:
    """A coming-soon-visibility course with one topic item."""
    course: Course = CourseFactory(
        title=title, slug=slug, visibility=CourseVisibility.COMING_SOON
    )
    topic = TopicFactory(title=f"{slug}-t", slug=f"{slug}-topic", content="content")
    course.items.create(child=topic, order=0)
    return course


@pytest.mark.django_db
def test_all_courses_renders_four_distinct_status_labels(
    mock_site_context, courses, logged_in_client
):
    """Each of the four registration states renders its own visible label, so a
    registered-but-unstarted course is no longer indistinguishable from an
    unregistered one. The old ambiguous "Not started" label is gone entirely."""
    user = UserFactory()
    # courses[0] -> Not registered (left unregistered)
    # courses[1] -> Registered (enrolled, 0% progress)
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[1])
    # courses[2] -> In progress (enrolled, >0% progress)
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[2])
    course_progress_record(
        courses[2], user, progress_percentage=40, completed_time=None
    )
    # A fourth course -> Completed.
    completed = CourseFactory(title="Course D", slug="course-d")
    completed_topic = TopicFactory(title="Topic D", slug="topic-d", content="content")
    completed.items.create(child=completed_topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=completed)
    course_progress_record(
        completed, user, progress_percentage=100, completed_time=timezone.now()
    )

    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()

    assert "Not registered" in body
    assert "Registered" in body  # the registered-0% row (capital R, standalone)
    assert "In progress" in body
    assert "Completed" in body
    assert "Not started" not in body  # retired ambiguous label


@pytest.mark.django_db
def test_all_courses_not_registered_row_links_to_course_detail(
    mock_site_context, courses, logged_in_client
):
    """A not-registered course row renders a single link to the course_detail URL."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert detail_url in body


@pytest.mark.django_db
def test_all_courses_not_registered_row_has_no_progress_bar(
    mock_site_context, courses, logged_in_client
):
    """A not-registered course row does not render a progress bar."""
    user = UserFactory()
    # No registration — courses[0] is NOT_REGISTERED
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    # The progress bar element is only present for registered/in-progress rows.
    # Locate the not-registered course section by its title and confirm no <progress>
    # appears in the page for the not-registered row.
    # (A simple check: if no courses are registered, NO progress bars exist.)
    assert "<progress" not in body


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_row_links_to_first_item(
    mock_site_context, courses, logged_in_client
):
    """A registered-0% row links to view_course_item at index=1."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    item_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": courses[0].slug, "index": 1},
    )
    body = response.content.decode()
    assert item_url in body


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_row_has_progress_value_zero(
    mock_site_context, courses, logged_in_client
):
    """A registered-0% row renders a progress bar reporting value='0'.

    The shared <c-course-progress-bar> uses a native <progress>, which exposes
    its value to assistive tech via the value attribute (implicit progressbar
    role) rather than an explicit aria-valuenow.
    """
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" in body
    assert 'value="0"' in body


@pytest.mark.django_db
def test_all_courses_in_progress_row_links_to_first_item(
    mock_site_context, courses, logged_in_client
):
    """An in-progress row links to view_course_item at index=1."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(
        courses[0], user, progress_percentage=55, completed_time=None
    )
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    item_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": courses[0].slug, "index": 1},
    )
    body = response.content.decode()
    assert item_url in body


@pytest.mark.django_db
def test_all_courses_in_progress_row_has_progress_value_above_zero(
    mock_site_context, courses, logged_in_client
):
    """An in-progress row renders a progress bar reporting its percentage as value.

    The shared <c-course-progress-bar> uses a native <progress>, whose value
    attribute carries the percentage to assistive tech.
    """
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(
        courses[0], user, progress_percentage=55, completed_time=None
    )
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" in body
    assert 'value="55"' in body


@pytest.mark.django_db
def test_all_courses_complete_row_links_to_course_finish(
    mock_site_context, courses, logged_in_client
):
    """A completed-course row links to the course_finish URL."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(
        courses[0], user, progress_percentage=100, completed_time=timezone.now()
    )
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    finish_url = reverse(
        "learner_interface:course_finish",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert finish_url in body


@pytest.mark.django_db
def test_all_courses_complete_row_has_no_progress_bar(
    mock_site_context, courses, logged_in_client
):
    """A completed-course row does not render a progress bar."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(
        courses[0], user, progress_percentage=100, completed_time=timezone.now()
    )
    # Register and complete only courses[0]; courses[1] and [2] remain unregistered.
    # No registered-but-incomplete courses means no progress bars in the whole page.
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" not in body


@pytest.mark.django_db
def test_all_courses_status_icons_are_decorative(
    mock_site_context, courses, logged_in_client
):
    """Status icons are decorative: the icon backend always stamps the semantic
    slug as the svg's aria-label, so each status icon must be wrapped in an
    `aria-hidden="true"` element to keep that slug out of the accessibility tree.
    Status is conveyed by the adjacent visible text (WCAG 1.4.1), never the slug.
    """
    user = UserFactory()
    # In-progress and complete rows exercise the in_progress/complete icons.
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(
        courses[0], user, progress_percentage=40, completed_time=None
    )
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[1])
    course_progress_record(
        courses[1], user, progress_percentage=100, completed_time=timezone.now()
    )
    # courses[2] stays unregistered -> exercises the not_started icon.
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    # Every status-icon svg (which carries aria-label="<slug>") must sit directly
    # inside an aria-hidden wrapper.
    for slug in ("in_progress", "not_started", "complete"):
        assert f'aria-label="{slug}"' in body, f"expected {slug} icon to render"
        assert re.search(
            rf'aria-hidden="true">\s*<svg[^>]*aria-label="{slug}"', body
        ), f"status icon {slug!r} is not wrapped in aria-hidden"


@pytest.mark.django_db
def test_all_courses_registered_row_has_details_link(
    mock_site_context, courses, logged_in_client
):
    """A registered (0%) row renders an explicit "Details" link to course_detail,
    in addition to the progress-linked title."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_complete_row_has_details_link(
    mock_site_context, courses, logged_in_client
):
    """A completed-course row renders an explicit "Details" link to course_detail,
    in addition to the finish-page title link."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(
        courses[0], user, progress_percentage=100, completed_time=timezone.now()
    )
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_not_registered_row_has_details_link(
    mock_site_context, courses, logged_in_client
):
    """A not-registered row renders an explicit "Details" link in addition to
    the stretched title link — both resolve to the same course_detail URL."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_coming_soon_row_has_details_link(mock_site_context):
    """A coming-soon row renders an explicit "Details" link alongside the
    "Coming soon" status eyebrow, in addition to the stretched title link."""
    course = _coming_soon_course(slug="cs-row", title="Coming Soon Row Course")
    client = Client()

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_details_link_renders_for_anonymous_visitor(
    mock_site_context, courses
):
    """The Details link renders on the all-courses page for an anonymous
    visitor, not just for authenticated ones."""
    client = Client()

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_details_link_renders_for_authenticated_unregistered_visitor(
    mock_site_context, courses, logged_in_client
):
    """The Details link renders for an authenticated visitor with no
    registration for the course."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


# Tests for the public all_courses view + access badge.
#
# Covers:
# - Anonymous access (no login redirect)
# - Free vs. application-gated badge labels in rendered rows
# - Anonymous rows suppress the "Not registered" eyebrow
# - Site isolation: courses on another site are absent


@pytest.mark.django_db
def test_all_courses_anonymous_lists_site_courses(mock_site_context):
    """Anonymous visitors see all site courses listed."""
    course = CourseFactory(title="Intro to Django", slug="intro-to-django")
    topic = TopicFactory(slug="t1", content="hi")
    course.items.create(child=topic, order=0)

    client = Client()
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    assert "Intro to Django" in response.content.decode()


@pytest.mark.django_db
@override_settings(
    COURSE_ACCESS_BACKEND="freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)
def test_all_courses_free_course_row_shows_free_badge(mock_site_context):
    """A free course row shows a 'Free' access badge for anonymous users."""
    from freedom_ls.course_access.loader import get_course_access_backend

    # override_settings already activated by decorator; re-clear so the correct
    # backend is resolved (the autouse fixture clears before the decorator runs).
    get_course_access_backend.cache_clear()

    # Default access_config is free (no access_type set)
    course = CourseFactory(title="Free Course", slug="free-course")
    topic = TopicFactory(slug="t-free", content="content")
    course.items.create(child=topic, order=0)

    client = Client()
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Free" in body
    assert "By application" not in body


@pytest.mark.django_db
@override_settings(
    COURSE_ACCESS_BACKEND="freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)
def test_all_courses_gated_course_row_shows_by_application_badge(mock_site_context):
    """An application-gated course row shows 'By application' badge for anonymous users."""
    from freedom_ls.course_access.loader import get_course_access_backend

    # override_settings already activated by decorator; re-clear so the correct
    # backend is resolved (the autouse fixture clears before the decorator runs).
    get_course_access_backend.cache_clear()

    gated_course = CourseFactory(
        title="Gated Course",
        slug="gated-course",
        access_config={"access_type": "application_gated"},
    )
    topic = TopicFactory(slug="t-gated", content="content")
    gated_course.items.create(child=topic, order=0)

    client = Client()
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "By application" in body
    assert "Free" not in body


@pytest.mark.django_db
def test_all_courses_anonymous_not_registered_row_has_no_not_registered_eyebrow(
    mock_site_context,
):
    """Anonymous not-registered rows do not render the 'Not registered' eyebrow text."""
    CourseFactory(title="Some Course", slug="some-course")

    client = Client()
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    assert "Not registered" not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_authenticated_not_registered_row_shows_not_registered_eyebrow(
    mock_site_context,
):
    """Authenticated users still see the 'Not registered' eyebrow on unregistered rows."""
    from freedom_ls.accounts.factories import UserFactory

    CourseFactory(title="Some Course", slug="some-course")
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    assert "Not registered" in response.content.decode()


@pytest.mark.django_db
def test_all_courses_site_isolation(mock_site_context):
    """A course on another site is absent from the anonymous catalogue."""
    other_site = Site.objects.create(name="OtherSite", domain="other.example.com")

    # Course on our site (mock_site_context site)
    CourseFactory(title="Our Course", slug="our-course")

    # Course on another site — override the site after creation
    other_course = CourseFactory(title="Other Site Course", slug="other-site-course")
    other_course.site = other_site
    other_course.save()

    client = Client()
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Our Course" in body
    assert "Other Site Course" not in body


# Unit tests for the get_course_listing helper (Task A1).
#
# Tests cover every classification branch of the helper:
#   - not registered
#   - registered with 0% progress (CourseProgress row exists)
#   - registered with missing CourseProgress row (still 0% → Registered)
#   - in progress (>0%, completed_time is None)
#   - complete (completed_time set)
#   - cross-site isolation (a course on a different site must not appear)
#   - anonymous users respect filter_visible (hidden courses not leaked)


@pytest.mark.django_db
def test_unregistered_course_has_not_registered_status(mock_site_context):
    """A course with no registration is classified as NOT_REGISTERED with 0% progress."""
    user = UserFactory()
    course = CourseFactory()

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.NOT_REGISTERED
    assert entry.progress_percentage == 0


@pytest.mark.django_db
def test_registered_zero_percent_course_has_registered_status(mock_site_context):
    """A registered course with a 0% CourseProgress row is classified as REGISTERED."""
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    course_progress_record(course, user, progress_percentage=0)

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.REGISTERED
    assert entry.progress_percentage == 0


@pytest.mark.django_db
def test_registered_missing_progress_row_has_registered_status(mock_site_context):
    """A registered course with no CourseProgress row is treated as 0% → REGISTERED."""
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    # Deliberately no CourseProgressFactory call — row is absent.

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.REGISTERED
    assert entry.progress_percentage == 0


@pytest.mark.django_db
def test_in_progress_course_has_in_progress_status(mock_site_context):
    """A registered course with >0% progress and no completed_time is IN_PROGRESS."""
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    course_progress_record(course, user, progress_percentage=50, completed_time=None)

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.IN_PROGRESS
    assert entry.progress_percentage == 50


@pytest.mark.django_db
def test_completed_course_has_complete_status(mock_site_context):
    """A registered course with completed_time set is classified as COMPLETE."""
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    course_progress_record(
        course, user, progress_percentage=100, completed_time=timezone.now()
    )

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.COMPLETE
    assert entry.progress_percentage == 100


@pytest.mark.django_db
def test_course_on_different_site_excluded_from_listing(mock_site_context):
    """A course belonging to a different site must not appear in the listing.

    This proves that cross-site data does not leak through get_all_courses(),
    get_course_registrations(), or the CourseProgress read.
    """
    user = UserFactory()
    current_site_course = CourseFactory()

    # Create a course on a completely different site (outside mock_site_context).
    other_site = SiteFactory(name="OtherSite")
    other_site_course = CourseFactory(site=other_site)

    entries = get_course_listing(user)

    entry_courses = [e.course for e in entries]
    assert current_site_course in entry_courses
    assert other_site_course not in entry_courses


@pytest.mark.django_db
def test_anonymous_listing_excludes_hidden_courses(mock_site_context):
    """The anonymous branch routes through filter_visible, so a hidden course
    is excluded while a published course is listed."""
    published = CourseFactory(visibility=CourseVisibility.PUBLISHED)
    hidden = CourseFactory(visibility=CourseVisibility.HIDDEN)

    entries = get_course_listing(AnonymousUser())

    entry_courses = [e.course for e in entries]
    assert published in entry_courses
    assert hidden not in entry_courses


@pytest.mark.django_db
def test_get_course_listing_returns_course_listing_entries(mock_site_context):
    """get_course_listing returns a list of CourseListingEntry instances."""
    user = UserFactory()
    CourseFactory()

    entries = get_course_listing(user)

    assert isinstance(entries, list)
    assert all(isinstance(e, CourseListingEntry) for e in entries)


@pytest.mark.django_db
def test_multiple_courses_all_classified_independently(mock_site_context):
    """With three courses in different states, each is classified correctly."""
    user = UserFactory()

    not_registered_course = CourseFactory()

    registered_course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=registered_course)

    complete_course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=complete_course)
    course_progress_record(
        complete_course, user, progress_percentage=100, completed_time=timezone.now()
    )

    entries = get_course_listing(user)
    by_course = {e.course.id: e for e in entries}

    assert (
        by_course[not_registered_course.id].status == CourseListingStatus.NOT_REGISTERED
    )
    assert by_course[registered_course.id].status == CourseListingStatus.REGISTERED
    assert by_course[complete_course.id].status == CourseListingStatus.COMPLETE


@pytest.mark.django_db
def test_anonymous_user_respects_visible_courses_filter(mock_site_context):
    """Anonymous branch of get_course_listing must honour the visible_courses argument.

    A backend that overrides filter_visible to hide a course must not leak that
    course to anonymous visitors. Previously the anonymous branch unconditionally
    iterated get_all_courses(), ignoring visible_courses entirely.
    """
    visible_course = CourseFactory()
    hidden_course = CourseFactory()

    # Simulate a backend whose filter_visible drops hidden_course.
    visible_qs: QuerySet[Course] = Course.objects.filter(pk=visible_course.pk)

    anon = AnonymousUser()
    entries = get_course_listing(anon, visible_courses=visible_qs)

    entry_courses = [e.course for e in entries]
    assert visible_course in entry_courses
    assert hidden_course not in entry_courses


@pytest.mark.django_db
def test_authenticated_listing_query_count_does_not_scale_with_courses(
    mock_site_context,
):
    """The authenticated listing must not issue registration queries per course.

    Regression guard: the access badge comes from the config-only
    backend.get_access_badge (no per-user queries), so the query count for a
    large catalogue must equal that of a small one.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user = UserFactory()

    CourseFactory()
    with CaptureQueriesContext(connection) as few:
        get_course_listing(user)
    few_count = len(few.captured_queries)

    for _ in range(9):
        CourseFactory()
    with CaptureQueriesContext(connection) as many:
        get_course_listing(user)
    many_count = len(many.captured_queries)

    # 1 course vs 10 courses must issue the same number of queries — a per-course
    # backend.get_access would have added ~2 registration exists() queries each.
    assert many_count == few_count


# Tests for coming-soon / hidden visibility in the discovery listings (Task 4.2).
#
# Covers the dashboard "Available courses" grid and the all-courses row list:
#   * a coming-soon course appears in discovery as an ordinary card/row — a plain
#     link to the course detail page carrying a "Coming soon" chip — with NO
#     express-interest CTA and NO enrol control (the CTA lives only on the course
#     detail page).
#   * a hidden course is dropped from discovery for an unregistered user but
#     still appears on the dashboard for a registered user (registered lists
#     bypass filter_visible).
#   * the public home page (anonymous GET /) drops hidden courses while still
#     showing published and coming-soon courses (the anonymous filter_visible
#     branch excludes only HIDDEN).


@pytest.mark.django_db
def test_all_courses_coming_soon_is_plain_detail_link_no_cta(
    mock_site_context, course_with_topic, logged_in_client
):
    """A coming-soon course lists as an ordinary row: a "Coming soon" chip and a
    plain link to the course detail page, with no express-interest CTA."""
    course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:courses"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": "cs"}
    )
    assert response.status_code == 200
    assert "Coming soon" in body
    assert f'href="{detail_url}"' in body
    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_all_courses_coming_soon_no_cta_even_when_interested(
    mock_site_context, course_with_topic, logged_in_client
):
    """The listing never shows the express-interest CTA, even for a learner who
    has already expressed interest (that control lives only on the detail page)."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    body = response.content.decode()

    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_all_courses_hidden_course_absent_for_unregistered(
    mock_site_context, course_with_topic, logged_in_client
):
    course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:courses"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_hidden_course_absent_for_removed_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    """A removed learner's active registration grants nothing, so filter_visible
    must drop the hidden course exactly as it would for an unregistered user."""
    course = course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Course"
    )
    learner = LearnerFactory(is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    client = logged_in_client(learner.user)

    response = client.get(reverse("learner_interface:courses"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_coming_soon_registered_keeps_registered_status(
    mock_site_context, course_with_topic, logged_in_client
):
    """A learner registered for a coming-soon course keeps their registered listing
    status — coming-soon exempts registered users, so no express-interest CTA."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Coming Soon Course" in body
    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_dashboard_coming_soon_is_plain_detail_link_no_cta(
    mock_site_context, course_with_topic, logged_in_client
):
    """A coming-soon course lists as an ordinary card: a "Coming soon" chip and a
    plain link to the course detail page, with no express-interest CTA."""
    course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": "cs"}
    )
    assert response.status_code == 200
    assert "Coming soon" in body
    assert f'href="{detail_url}"' in body
    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_dashboard_coming_soon_no_cta_even_when_interested(
    mock_site_context, course_with_topic, logged_in_client
):
    """The dashboard never shows the express-interest CTA, even for a learner who
    has already expressed interest (that control lives only on the detail page)."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_dashboard_recommended_coming_soon_is_plain_detail_link_no_cta(
    mock_site_context, course_with_topic, logged_in_client
):
    """A recommended coming-soon course renders as a plain detail-link card with a
    "Coming soon" chip and no express-interest CTA."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": "cs"}
    )
    assert "Coming soon" in body
    assert f'href="{detail_url}"' in body
    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_dashboard_hidden_recommended_absent_for_unregistered(
    mock_site_context, course_with_topic, logged_in_client
):
    """A hidden recommended course must not leak as a card for an unregistered
    user — recommendations bypass the available-courses filter_visible pass, so
    the dashboard view must drop hidden-and-unregistered recommendations."""
    course = course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Recommended"
    )
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert "Hidden Recommended" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_recommended_present_for_registered(
    mock_site_context, course_with_topic, logged_in_client
):
    """A hidden recommended course the user IS registered for still appears —
    the "registered keeps access" rule wins over the hidden exclusion."""
    course = course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Recommended"
    )
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course)
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert "Hidden Recommended" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_absent_for_unregistered(
    mock_site_context, course_with_topic, logged_in_client
):
    course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:dashboard"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_present_for_registered_user(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Course"
    )
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert "Hidden Course" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_shows_published_course_for_anonymous(
    mock_site_context, course_with_topic
):
    """Positive control: the anonymous public home page renders published courses
    in its discovery grid, so the hidden-course absence assertion below is
    meaningful (the grid is not simply empty)."""
    course_with_topic(
        visibility=CourseVisibility.PUBLISHED, slug="pub", title="Published Course"
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    assert "Published Course" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_absent_for_anonymous(mock_site_context, course_with_topic):
    """A hidden course must never appear on the public home page for an anonymous
    visitor — the anonymous filter_visible branch excludes HIDDEN."""
    course_with_topic(
        visibility=CourseVisibility.HIDDEN, slug="hid", title="Hidden Course"
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_coming_soon_present_for_anonymous(
    mock_site_context, course_with_topic
):
    """A coming-soon course still appears on the public home page for an anonymous
    visitor, in the Coming soon section — the exclusion is specific to HIDDEN."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "coming-soon").courses == [course]
    assert "Coming Soon Course" in response.content.decode()


@pytest.mark.django_db
def test_all_courses_coming_soon_shows_no_chip_for_anonymous_with_override(
    mock_site_context, course_with_topic
):
    """Anonymous branch of get_course_listing: with the override on, a
    coming-soon course looks like an ordinary published course in the catalogue."""
    course_with_topic(
        visibility=CourseVisibility.COMING_SOON,
        slug="cs",
        title="Preview Launch Course",
    )

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        response = Client().get(reverse("learner_interface:courses"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Preview Launch Course" in body
    assert "Coming soon" not in body


@pytest.mark.django_db
def test_all_courses_coming_soon_shows_no_chip_for_authenticated_with_override(
    mock_site_context, course_with_topic, logged_in_client
):
    """Authenticated branch of get_course_listing: with the override on, a
    coming-soon course looks like an ordinary published course in the catalogue."""
    course_with_topic(
        visibility=CourseVisibility.COMING_SOON,
        slug="cs",
        title="Preview Launch Course",
    )
    client = logged_in_client(UserFactory())

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        response = client.get(reverse("learner_interface:courses"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Preview Launch Course" in body
    assert "Coming soon" not in body


@pytest.mark.django_db
def test_dashboard_available_coming_soon_shows_no_chip_with_override(
    mock_site_context, course_with_topic, logged_in_client
):
    """With the override on, nothing is coming soon: the course discovers as an
    ordinary card in Available courses, and no Coming soon section renders."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON,
        slug="cs",
        title="Preview Launch Course",
    )
    client = logged_in_client(UserFactory())

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    assert response.status_code == 200
    assert rendered_section(response, "available").courses == [course]
    assert section_by_slug(response, "coming-soon") is None
    assert "Preview Launch Course" in body
    assert "Coming soon" not in body


@pytest.mark.django_db
def test_dashboard_recommended_coming_soon_shows_no_chip_with_override(
    mock_site_context, course_with_topic, logged_in_client
):
    """_annotate_recommendations: with the override on, a recommended coming-soon
    course's card carries no "Coming soon" chip."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON,
        slug="cs",
        title="Preview Launch Course",
    )
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course)
    client = logged_in_client(user)

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    assert "Preview Launch Course" in body
    assert "Coming soon" not in body


# Tests for the three course-card variants and the course-detail view.
#
# Per project conventions: no CSS class assertions. We assert on
# content the user sees (course title, eyebrow text, "Next up:" line) and
# on which partial got included.


@pytest.fixture
def course_with_topics(mock_site_context):
    course = CourseFactory(title="Course X", slug="course-x")
    for i in range(3):
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-x-{i}", content="content")
        course.items.create(child=topic, order=i)
    return course


@pytest.mark.django_db
def test_registered_card_for_zero_progress(
    mock_site_context, course_with_topics, logged_in_client
):
    """A registered course with progress_percentage == 0 renders the
    Registered card variant, not the In progress one. The old ambiguous
    "Not started" label (shared with unregistered courses) is retired."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    # No progress => percentage stays 0.
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert 'data-testid="course-status-registered"' in body
    assert 'data-testid="course-status-in_progress"' not in body
    assert "Not started" not in body  # retired label


@pytest.mark.django_db
def test_registered_card_shows_empty_progress_bar(
    mock_site_context, course_with_topics, logged_in_client
):
    """The Registered card always renders an empty (0%) progress bar so it
    visually anchors next to in-progress cards in a mixed grid row."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert "Registered" in body
    assert 'value="0"' in body
    assert "0%" in body


@pytest.mark.django_db
def test_in_progress_card_when_progress_above_zero(
    mock_site_context, course_with_topics, logged_in_client
):
    """A course whose first topic is complete (>0 progress) renders the
    In progress card with the Next up line."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    # Mark first topic complete to push progress >0%.
    first_topic = course_with_topics.children()[0]
    topic_completion(
        course_with_topics, user, first_topic, complete_time=timezone.now()
    )
    # Recompute progress on CourseProgress (the helper expects this row).
    course_progress_record(course_with_topics, user, progress_percentage=33)

    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert 'data-testid="course-status-in_progress"' in body


@pytest.mark.django_db
def test_complete_card_for_completed_course(
    mock_site_context, course_with_topics, logged_in_client
):
    """A completed course renders the Completed eyebrow."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    course_progress_record(course_with_topics, user, completed_time=timezone.now())
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert "Completed" in body


@pytest.mark.django_db
def test_not_registered_card_shows_not_registered_label(
    mock_site_context, course_with_topics, logged_in_client
):
    """A recommended (unregistered) course on the dashboard shows the
    "Not registered" status — distinct from a registered-but-unstarted
    course — instead of the old ambiguous "Not started"."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course_with_topics)
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert "Not registered" in body
    assert "Not started" not in body


@pytest.mark.django_db
def test_course_detail_returns_200_for_authenticated_user(
    mock_site_context, course_with_topics, logged_in_client
):
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert course_with_topics.title in body
    # ToC items render.
    assert all(child.title in body for child in course_with_topics.children())


@pytest.mark.django_db
def test_course_detail_enrol_cta_links_to_initiate_course_access_when_unregistered(
    mock_site_context, course_with_topics, logged_in_client
):
    """The CTA for an unregistered user links to the initiate_course_access URL."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    register_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert register_url in body


@pytest.mark.django_db
def test_course_detail_has_start_button_when_registered_zero_progress(
    mock_site_context, course_with_topics, logged_in_client
):
    """A registered learner with 0 progress lands on the detail page
    and sees a Start course button pointing to the first item."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    first_item_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course_with_topics.slug, "index": 1},
    )
    assert "Start course" in body
    assert first_item_url in body


@pytest.mark.django_db
def test_course_detail_renders_breadcrumbs(
    mock_site_context, course_with_topics, logged_in_client
):
    """The detail page renders breadcrumbs including the 'All courses' link
    and the current course title."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    all_courses_url = reverse("learner_interface:courses")
    assert all_courses_url in body
    assert "All courses" in body
    assert course_with_topics.title in body


@pytest.mark.django_db
def test_course_detail_renders_lesson_count_in_stats(
    mock_site_context, course_with_topics, logged_in_client
):
    """The detail page stats strip always shows the lesson count."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    # course_with_topics has 3 topics
    assert "3 lesson" in body


@pytest.mark.django_db
@pytest.mark.parametrize(
    "label", ["Beginner", "Intermediate", "Advanced", "All levels"]
)
def test_course_detail_omits_difficulty_when_not_set(
    mock_site_context, course_with_topics, label, logged_in_client
):
    """When difficulty is not set, no difficulty display value renders."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    assert label not in body


@pytest.mark.django_db
def test_course_detail_omits_duration_when_not_set(
    mock_site_context, course_with_topics, logged_in_client
):
    """When estimated_duration is not set, the detail page shows no duration."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    # The duration stat is omitted entirely — its "Duration" label never renders.
    assert "Duration" not in body


@pytest.mark.django_db
def test_course_detail_omits_learning_outcomes_section_when_not_set(
    mock_site_context, course_with_topics, logged_in_client
):
    """When learning_outcomes is empty, the 'What you'll learn' section is absent."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(
        reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    assert "What you'll learn" not in body


@pytest.mark.django_db
def test_registered_card_does_not_link_to_register_url(
    mock_site_context, course_with_topics, logged_in_client
):
    """A registered learner's card never links to the registration URL —
    registering again would be a no-op redirect. Registered courses render
    the progress card (no preview modal), so the register link is absent."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    register_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert register_url not in body


@pytest.mark.django_db
def test_registered_zero_progress_card_links_title_to_first_item(
    mock_site_context, course_with_topics, logged_in_client
):
    """A registered 0-progress course renders the progress card (not a modal):
    the "Registered" eyebrow, a 0% progress bar, and a title that links
    straight to the first course item via the "Next up" target."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    first_item_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course_with_topics.slug, "index": 1},
    )
    assert "Registered" in body
    assert 'value="0"' in body
    assert first_item_url in body


@pytest.mark.django_db
def test_not_registered_card_links_to_course_detail(
    mock_site_context, course_with_topics, logged_in_client
):
    """A not-registered course card links to the course_detail URL (not a modal)."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course_with_topics)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert detail_url in body


@pytest.mark.django_db
def test_registered_zero_progress_card_shows_details_link(
    mock_site_context, course_with_topics, logged_in_client
):
    """The Registered (0%) card includes an explicit "Details" link to
    course_detail, distinct from the progress-aware title link."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_in_progress_card_shows_details_link(
    mock_site_context, course_with_topics, logged_in_client
):
    """The In-progress card includes an explicit "Details" link to
    course_detail."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    first_topic = course_with_topics.children()[0]
    topic_completion(
        course_with_topics, user, first_topic, complete_time=timezone.now()
    )
    course_progress_record(course_with_topics, user, progress_percentage=33)

    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_complete_card_shows_details_link(
    mock_site_context, course_with_topics, logged_in_client
):
    """The Completed card includes an explicit "Details" link to
    course_detail."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_with_topics)
    course_progress_record(
        course_with_topics, user, progress_percentage=100, completed_time=timezone.now()
    )

    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_not_registered_card_shows_explicit_details_link(
    mock_site_context, course_with_topics, logged_in_client
):
    """The Not-registered card already stretches its title link to
    course_detail; an explicit "Details" affordance is also present and
    resolves to the identical URL (two occurrences of the same href)."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course_with_topics)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert "Details" in body
    assert body.count(f'href="{detail_url}"') >= 2


@pytest.mark.django_db
def test_coming_soon_card_shows_details_link(mock_site_context, logged_in_client):
    """The Coming-soon card includes an explicit "Details" link to
    course_detail."""
    course = _coming_soon_course(slug="cs-details", title="Coming Soon Course")
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert "Details" in body
    assert f'href="{detail_url}"' in body


# Tests for the anonymous home page variant.
#
# They cover:
# - Anonymous GET / returns 200 (no login redirect)
# - Anonymous home renders the anonymous hero with a link to the catalogue
# - Anonymous home does NOT show authenticated-only content
# - Anonymous home offers login / sign-up routes (un-parameterised, no next=)
# - Anonymous GET / does NOT call backend.get_dashboard_contributions
# - Authenticated dashboard unchanged (hero absent for auth user)
#
# The assertions key on template names and structural hooks rather than on the
# copy itself. A downstream project is invited to shadow these templates whole,
# so their wording is not FLS's to pin.

ANONYMOUS_HERO_TEMPLATE = "learner_interface/partials/anonymous_hero.html"


@pytest.mark.django_db
def test_anonymous_dashboard_renders_the_anonymous_hero(mock_site_context):
    """Anonymous home page shows the hero in place of a personalised greeting."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert ANONYMOUS_HERO_TEMPLATE in [t.name for t in response.templates]


@pytest.mark.django_db
def test_anonymous_dashboard_contains_browse_all_courses_cta(mock_site_context):
    """The anonymous hero routes visitors to the course catalogue."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    courses_url = reverse("learner_interface:courses")
    assert ANONYMOUS_HERO_TEMPLATE in [t.name for t in response.templates]
    assert f'href="{courses_url}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_the_authenticated_greeting(
    mock_site_context,
):
    """Anonymous home page must not show the personalised greeting block."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="dashboard-greeting"' not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_in_progress_section(mock_site_context):
    """Anonymous home page must not show the 'In Progress' courses section."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="current-courses"' not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_learning_history(mock_site_context):
    """Anonymous home page must not show the 'Learning History' section."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="learning-history"' not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_unenrolled_placeholder(mock_site_context):
    """Anonymous home page must not show the no-registrations placeholder."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert 'data-testid="in-progress-empty-no-registrations"' not in body


@pytest.mark.django_db
def test_anonymous_dashboard_shows_login_link(mock_site_context):
    """Anonymous home page header offers a route to the login page."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    login_url = reverse("account_login")
    assert f'href="{login_url}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_shows_signup_when_allowed(mock_site_context):
    """Sign up route appears when the site allows signups."""
    SiteSignupPolicyFactory(allow_signups=True)
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    signup_url = reverse("account_signup")
    assert f'href="{signup_url}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_hides_signup_when_disallowed(mock_site_context):
    """Sign up route is hidden when the site disallows signups."""
    SiteSignupPolicyFactory(allow_signups=False)
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    signup_url = reverse("account_signup")
    assert f'href="{signup_url}"' not in response.content.decode()


@pytest.mark.django_db
def test_authenticated_dashboard_does_not_show_hero(mock_site_context):
    """Authenticated dashboard shows the greeting, never the anonymous hero."""
    user = UserFactory(first_name="Ada")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="dashboard-greeting"' in response.content.decode()
    assert ANONYMOUS_HERO_TEMPLATE not in [t.name for t in response.templates]
