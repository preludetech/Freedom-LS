"""Tests for wiring the course-access backend into learner_interface.

Covers:
1. Chokepoint gate in initiate_course_access
2. CTA branching in course_detail
3. Listing visibility (filter_visible)
4. Content-access gate (view_course_item, get_course_index, course_home)
5. Dashboard contributions (plugin dashboard seam)

These tests import course_applications factories/models to *build state* but
learner_interface production code must NOT import course_applications — that rule
is enforced by the architecture, not these tests.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
import time_machine

from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import CourseAudience, CourseVisibility
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    CourseDeadlineConfigFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import (
    AfterAccessEnded,
    CourseDeadlineConfig,
    DeadlineKind,
)
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.learner_interface.tests.helpers import (
    form_attempt,
    learner_with_two_grants,
    rendered_section,
    set_due_date,
)
from freedom_ls.learner_interface.utils import BLOCKED
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation

# ---------------------------------------------------------------------------
# 1. Chokepoint gate — initiate_course_access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_initiate_access_gated_course_redirects_to_apply_url(
    mock_site_context, logged_in_client, course_with_topic
):
    """POST initiate_course_access for a gated course redirects to the apply URL."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.post(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert response.status_code == 302
    assert response["Location"] == apply_url


@pytest.mark.django_db
def test_initiate_access_gets_404_for_an_organisation_course_outside_the_audience(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    course.organisations.add(OrganisationFactory())
    client = logged_in_client(UserFactory())

    response = client.post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_initiate_access_gated_course_creates_no_registration(
    mock_site_context, logged_in_client, course_with_topic
):
    """POST initiate_course_access for a gated course does NOT create a LearnerCourseRegistration."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    client.post(url)

    assert not LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_gated_course_get_also_redirects(
    mock_site_context, logged_in_client, course_with_topic
):
    """GET initiate_course_access for a gated course also redirects (no self-register)."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert response.status_code == 302
    assert response["Location"] == apply_url


@pytest.mark.django_db
def test_initiate_access_free_course_creates_registration(
    mock_site_context, logged_in_client, course_with_topic
):
    """POST initiate_course_access for a free course creates a LearnerCourseRegistration."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    client.post(url)

    assert LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_deletes_the_users_recommendation_for_the_course(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=course)
    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )

    logged_in_client(user).post(url)

    assert not RecommendedCourse.objects.filter(user=user, course=course).exists()


@pytest.mark.django_db
def test_initiate_access_after_an_admin_deactivation_deletes_the_recommendation(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    learner = LearnerFactory()
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)
    RecommendedCourseFactory(user=learner.user, course=course)
    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )

    logged_in_client(learner.user).post(url)

    assert not RecommendedCourse.objects.filter(
        user=learner.user, course=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_reactivates_a_deactivated_registration_and_keeps_its_maker(
    mock_site_context, logged_in_client, course_with_topic
):
    """Reactivation goes through self_register, whose own tests cover the
    history entry it writes; here the registration comes back as the
    admin's, not as a self-registration."""
    course = course_with_topic(access_type="free")
    learner = LearnerFactory(organisation=get_default_organisation(mock_site_context))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=False, self_registered=False
    )

    _initiate_access(logged_in_client(learner.user), course)

    registration.refresh_from_db()
    assert registration.is_active
    assert not registration.self_registered


@pytest.mark.django_db
def test_initiate_access_reactivates_a_deactivated_learner_of_the_default_organisation(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    learner = LearnerFactory(
        user=user,
        organisation=get_default_organisation(mock_site_context),
        is_active=False,
    )

    _initiate_access(logged_in_client(user), course)

    learner.refresh_from_db()
    assert learner.is_active
    assert LearnerCourseRegistration.objects.get(
        learner=learner, course=course
    ).is_active


def _initiate_access(client: Client, course) -> None:
    client.post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "audience", [CourseAudience.ORGANISATION_LEARNERS, CourseAudience.PUBLIC]
)
def test_initiate_access_registers_through_the_users_organisation_of_the_course(
    mock_site_context, logged_in_client, course_with_topic, audience
):
    course = course_with_topic(access_type="free")
    course.audience = audience
    course.save()
    organisation = OrganisationFactory()
    course.organisations.add(organisation)
    user = UserFactory()
    LearnerFactory(user=user, organisation=organisation)

    _initiate_access(logged_in_client(user), course)

    registration = LearnerCourseRegistration.objects.get(
        learner__user=user, course=course
    )
    assert registration.learner.organisation == organisation


@pytest.mark.django_db
def test_initiate_access_registers_through_the_earliest_learner_row(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    first = OrganisationFactory()
    second = OrganisationFactory()
    course.organisations.add(first, second)
    user = UserFactory()
    LearnerFactory(user=user, organisation=first)
    LearnerFactory(user=user, organisation=second)

    _initiate_access(logged_in_client(user), course)

    registration = LearnerCourseRegistration.objects.get(
        learner__user=user, course=course
    )
    assert registration.learner.organisation == first


@pytest.mark.django_db
def test_initiate_access_public_organisation_course_without_a_row_uses_default_organisation(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    course.audience = CourseAudience.PUBLIC
    course.save()
    course.organisations.add(OrganisationFactory())
    user = UserFactory()

    _initiate_access(logged_in_client(user), course)

    registration = LearnerCourseRegistration.objects.get(
        learner__user=user, course=course
    )
    assert registration.learner.organisation == get_default_organisation(
        mock_site_context
    )


@pytest.mark.django_db
def test_initiate_access_deactivated_learner_of_the_course_organisation_gets_404(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    organisation = OrganisationFactory()
    course.organisations.add(organisation)
    user = UserFactory()
    learner = LearnerFactory(user=user, organisation=organisation, is_active=False)
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

    response = logged_in_client(user).post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )

    registration.refresh_from_db()
    assert response.status_code == 404
    assert LearnerCourseRegistration.objects.filter(course=course).count() == 1
    assert registration.is_active


@pytest.mark.django_db
def test_initiate_access_organisation_course_closed_to_the_default_organisation_redirects_to_detail(
    mock_site_context, logged_in_client, course_with_topic, settings
):
    # The visibility preview lets a user with no claim on the course past the
    # audience gate; the default organisation is the only one left to register
    # them through, and the course is not open to it.
    settings.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE = True
    course = course_with_topic(access_type="free")
    course.audience = CourseAudience.ORGANISATION_LEARNERS
    course.save()
    course.organisations.set([OrganisationFactory()])
    user = UserFactory()

    response = logged_in_client(user).post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert not LearnerCourseRegistration.objects.filter(course=course).exists()
    assert not Learner.objects.filter(
        user=user, organisation=get_default_organisation(mock_site_context)
    ).exists()


# ---------------------------------------------------------------------------
# 2. CTA branching — course_detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_detail_gated_not_registered_shows_apply_now(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a gated course with an unregistered learner shows 'Apply now'."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    assert "Apply now" in body


@pytest.mark.django_db
def test_course_detail_gated_not_registered_cta_url_is_apply_url(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a gated course: start_url points to the apply view."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert apply_url in response.content.decode()


@pytest.mark.django_db
def test_course_detail_free_not_registered_shows_enrol_for_free_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a free course with an unregistered learner shows the backend's free label."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    # The FreeOnlyCourseAccessBackend label for a free unregistered learner
    assert "Enrol for free" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_gated_shows_application_copy_not_free_copy(
    mock_site_context, logged_in_client, course_with_topic
):
    """The gated detail page must show application funnel copy, not the free copy.

    The funnel copy (enrolment summary, sign-up heading/subtext) is driven by the
    access backend, so a gated course must not claim to be "Free · open" / "One
    click. No credit card." alongside its "Apply now" CTA.
    """
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert "Free · open" not in body
    assert "One click. No credit card." not in body
    assert "By application" in body
    assert "Application required" in body
    assert "Apply and we&#x27;ll review your request." in body


@pytest.mark.django_db
def test_course_detail_free_shows_free_acquisition_copy(
    mock_site_context, logged_in_client, course_with_topic
):
    """The free detail page still shows the free funnel copy (driven by the backend)."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert "Free · open" in body
    assert "One click. No credit card." in body


@pytest.mark.django_db
def test_course_detail_registered_in_progress_shows_continue_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered learner with progress shows 'Continue'."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    record = course_progress_record(course, user)
    record.progress_percentage = 50
    record.save(update_fields=["progress_percentage"])
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Continue" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_registered_completed_shows_review_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered and completed learner shows 'Review course'."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    record = course_progress_record(course, user)
    record.progress_percentage = 100
    record.completed_time = timezone.now()
    record.save(update_fields=["progress_percentage", "completed_time"])
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Review course" in response.content.decode()


# ---------------------------------------------------------------------------
# 3. Listing visibility
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_lists_all_courses_with_default_backend(
    mock_site_context, logged_in_client
):
    """With the default backend, Available courses is unchanged (filter_visible is a no-op)."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    available = rendered_section(response, "available")
    available_ids = {c.id for c in available.courses}
    assert course_a.id in available_ids
    assert course_b.id in available_ids


# ---------------------------------------------------------------------------
# 4. Content-access gate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_view_course_item_unregistered_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """view_course_item for an unregistered learner redirects to course_detail."""
    course = course_with_topic(access_type="free")
    user = UserFactory()  # not registered
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_view_course_item_registered_renders_content(
    mock_site_context, logged_in_client, course_with_topic
):
    """view_course_item for a registered learner renders the content (not a redirect)."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_view_course_item_removed_learner_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """A deactivated learner's active registration grants nothing: view_course_item
    redirects to course_detail exactly as it would for an unregistered user."""
    course = course_with_topic(access_type="free")
    learner = LearnerFactory(is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, course=course)
    client = logged_in_client(learner.user)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_course_detail_unregistered_all_toc_items_blocked(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for an unregistered learner shows all TOC items as BLOCKED."""

    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children  # at least one item exists
    assert all(child["status"] == BLOCKED for child in children)


@pytest.mark.django_db
def test_course_detail_registered_toc_items_not_all_blocked(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered learner has at least one non-BLOCKED TOC item."""

    course = course_with_topic(access_type="free")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children
    statuses = [child["status"] for child in children]
    assert any(s != BLOCKED for s in statuses)


@pytest.mark.django_db
def test_course_home_unregistered_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_home for an unregistered learner redirects to course_detail."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_course_home_removed_learner_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """A deactivated learner's active registration grants nothing: course_home
    redirects to course_detail exactly as it would for an unregistered user."""
    course = course_with_topic(access_type="free")
    learner = LearnerFactory(is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, course=course)
    client = logged_in_client(learner.user)

    url = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_gated_course_detail_unregistered_shows_apply_not_item_content(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a gated course: unregistered learner sees Apply affordance and blocked items."""

    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    assert "Apply now" in body
    # All TOC items must be blocked
    children = response.context["children"]
    assert all(child["status"] == BLOCKED for child in children)


@pytest.mark.django_db
def test_view_course_item_gated_unregistered_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """view_course_item for a gated course with an unregistered learner redirects to course_detail."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


# ---------------------------------------------------------------------------
# 5. Dashboard contributions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_with_active_application_shows_status_link(
    mock_site_context, logged_in_client, course_with_topic
):
    """Dashboard shows the status link for an in-flight application (via ApplicationCourseAccessBackend)."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    application = CourseApplicationFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    body = response.content.decode()
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})
    assert status_url in body


@pytest.mark.django_db
def test_dashboard_without_applications_shows_no_extra_panel(
    mock_site_context, logged_in_client
):
    """Dashboard with no active applications shows no application panel.

    Uses FreeOnlyCourseAccessBackend (which returns [] for get_dashboard_contributions)
    to isolate this test from any active applications that might exist on the site.
    The autouse _clear_course_access_backend_cache fixture clears before/after each
    test; we also clear inside the override_settings context to ensure the override
    takes effect within this test body.
    """
    user = UserFactory()
    client = logged_in_client(user)

    with override_settings(
        COURSE_ACCESS_BACKEND="freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend"
    ):
        get_course_access_backend.cache_clear()
        response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    assert "dashboard_panels" in response.context
    assert response.context["dashboard_panels"] == []


@pytest.mark.django_db
def test_anonymous_dashboard_without_applications_shows_no_extra_panel(
    mock_site_context,
):
    """An anonymous visitor whose session holds nothing gets an empty panel list."""
    response = Client().get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    assert response.context["dashboard_panels"] == []


@pytest.mark.django_db
def test_dashboard_panels_in_context(mock_site_context, logged_in_client):
    """The dashboard view always includes dashboard_panels in context."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    assert "dashboard_panels" in response.context


# ---------------------------------------------------------------------------
# Visibility chokepoints — hidden 404s, coming-soon routing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_home_hidden_unregistered_returns_404(
    mock_site_context, course_with_topic, logged_in_client
):
    """course_home for a hidden course must 404 for an unregistered user, not 302."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    url = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_home_hidden_registered_still_resolves(
    mock_site_context, course_with_topic, logged_in_client
):
    """A registered learner still reaches course_home for a hidden course (redirects into player)."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    url = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 302


@pytest.mark.django_db
def test_course_home_hidden_inactive_cohort_member_returns_404(
    mock_site_context, course_with_topic, logged_in_client
):
    """A member of an inactive cohort loses the access the cohort's registration gave."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    registration = CohortCourseRegistrationFactory(course=course, is_active=True)
    user = UserFactory()
    CohortMembershipFactory(
        learner=LearnerFactory(
            user=user, organisation=registration.cohort.organisation
        ),
        cohort=registration.cohort,
    )
    registration.cohort.is_active = False
    registration.cohort.save()
    client = logged_in_client(user)

    url = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_view_course_item_hidden_unregistered_returns_404(
    mock_site_context, course_with_topic, logged_in_client
):
    """view_course_item for a hidden course must 404 for an unregistered user, not 302."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_view_course_item_hidden_registered_renders_content(
    mock_site_context, course_with_topic, logged_in_client
):
    """A registered learner still views content of a hidden course."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_initiate_access_coming_soon_redirects_to_detail(
    mock_site_context, course_with_topic, logged_in_client
):
    """POST initiate_course_access for a coming-soon course redirects to the detail page.

    The coming-soon CTA url is the POST-only express-interest endpoint; redirecting
    the browser (GET) there would 405. The safe fallback is the detail page.
    """
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.post(url)

    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert response.status_code == 302
    assert response["Location"] == detail_url


@pytest.mark.django_db
def test_initiate_access_coming_soon_creates_no_registration(
    mock_site_context, course_with_topic, logged_in_client
):
    """initiate_course_access for a coming-soon course does not self-register the learner."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    client.post(url)

    assert not LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_hidden_unregistered_returns_404(
    mock_site_context, course_with_topic, logged_in_client
):
    """initiate_course_access for a hidden course 404s for an unregistered user."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.post(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_initiate_access_coming_soon_self_registers_with_visibility_override(
    mock_site_context, course_with_topic, logged_in_client
):
    """With OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE on, a coming-soon course flows
    through to the backend's free self-registration instead of bouncing back to
    the detail page."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        get_course_access_backend.cache_clear()
        response = client.post(url)

    assert response.status_code == 302
    assert response["Location"] != reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_gated_course_records_no_course_registered_event(
    mock_site_context, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="application_gated")
    client = logged_in_client(UserFactory())

    client.post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )

    assert "google_analytics_events" not in client.session


# ---------------------------------------------------------------------------
# 6. Access ended by a deadline policy
# ---------------------------------------------------------------------------

REGISTERED_AT = datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC)
AFTER_END = datetime.datetime(2026, 9, 1, 10, 0, tzinfo=datetime.UTC)


def _ended_course() -> tuple:
    """A time-limited course (a topic, then a form) whose access ends under its policy."""
    course = CourseFactory(time_limit_days=30)
    course.items.create(child=TopicFactory(), order=0)
    form = FormFactory(submit_on_exit=True)
    course.items.create(child=form, order=1)
    CourseDeadlineConfigFactory(
        course=course,
        end_course_access="on",
        after_access_ended=AfterAccessEnded.NOTHING,
    )
    return course, form


def _ended_learner(course) -> tuple:
    user = UserFactory()
    record = course_progress_record(course, user, created_at=REGISTERED_AT)
    client = Client()
    client.force_login(user)
    return user, record, client


def _detail_url(course) -> str:
    return reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


def _player_urls(course) -> dict[str, str]:
    kwargs = {"course_slug": course.slug}
    return {
        "course_home": reverse("learner_interface:course_home", kwargs=kwargs),
        "view_course_item": reverse(
            "learner_interface:view_course_item", kwargs={**kwargs, "index": 1}
        ),
        "form_start": reverse(
            "learner_interface:form_start", kwargs={**kwargs, "index": 2}
        ),
        "form_fill_page": reverse(
            "learner_interface:form_fill_page",
            kwargs={**kwargs, "index": 2, "page_number": 1},
        ),
        "course_finish": reverse("learner_interface:course_finish", kwargs=kwargs),
        "course_form_complete": reverse(
            "learner_interface:course_form_complete", kwargs={**kwargs, "index": 2}
        ),
        "form_submit_and_exit": reverse(
            "learner_interface:form_submit_and_exit", kwargs={**kwargs, "index": 2}
        ),
    }


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
@pytest.mark.parametrize(
    "route",
    [
        "course_home",
        "view_course_item",
        "form_start",
        "form_fill_page",
        "course_finish",
        "course_form_complete",
    ],
)
def test_an_ended_learner_is_sent_to_the_detail_page(mock_site_context, route):
    course, _form = _ended_course()
    _user, _record, client = _ended_learner(course)

    response = client.get(_player_urls(course)[route])

    assert response.status_code == 302
    assert response["Location"] == _detail_url(course)


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_an_ended_learner_cannot_finish_the_course(mock_site_context):
    course, _form = _ended_course()
    _user, record, client = _ended_learner(course)

    client.get(_player_urls(course)["course_finish"])

    record.refresh_from_db()
    assert record.completed_time is None


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_submit_and_exit_finalises_an_open_attempt_for_an_ended_learner(
    mock_site_context,
):
    course, form = _ended_course()
    user, _record, client = _ended_learner(course)
    attempt = form_attempt(course, user, form)

    client.post(_player_urls(course)["form_submit_and_exit"])

    attempt.refresh_from_db()
    assert attempt.completed_time is not None


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_results_of_a_completed_attempt_stay_open_to_an_ended_learner(
    mock_site_context,
):
    course, form = _ended_course()
    user, _record, client = _ended_learner(course)
    form_attempt(course, user, form, completed_time=REGISTERED_AT)

    response = client.get(_player_urls(course)["course_form_complete"])

    assert response.status_code == 200


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_an_ended_registration_stays_active_and_fires_no_unregistered_webhook(
    mock_site_context,
):
    course, _form = _ended_course()
    user, _record, client = _ended_learner(course)

    with patch("freedom_ls.webhooks.events.fire_webhook_event") as fire:
        client.get(_player_urls(course)["course_home"])
        client.get(_detail_url(course))

    assert (
        LearnerCourseRegistration.objects.filter(
            learner__user=user, course=course, is_active=True
        ).count()
        == 1
    )
    assert "course.unregistered" not in [call.args[0] for call in fire.call_args_list]


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_initiate_access_for_an_ended_learner_creates_no_second_registration(
    mock_site_context,
):
    course, _form = _ended_course()
    user, _record, client = _ended_learner(course)

    response = client.post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )

    assert response["Location"] == _detail_url(course)
    assert LearnerCourseRegistration.objects.filter(learner__user=user).count() == 1


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_an_ended_learner_is_offered_no_enrol_for_free(
    mock_site_context,
):
    course, _form = _ended_course()
    user, _record, _client = _ended_learner(course)

    decision = get_course_access_backend().get_access(user=user, course=course)

    assert decision.cta_label is None
    assert decision.can_self_register is False


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_a_fixed_date_learner_override_restores_access_and_changes_nothing_stored(
    mock_site_context,
):
    course, form = _ended_course()
    user, record, client = _ended_learner(course)
    attempt = form_attempt(course, user, form, completed_time=REGISTERED_AT)
    stored_before = (
        record.completed_time,
        record.progress_percentage,
        CourseFormAttempt.objects.count(),
    )
    LearnerDeadlineOverrideFactory(
        course_progress=record,
        kind=DeadlineKind.FIXED,
        due_date=datetime.date(2026, 9, 2),
        due_days_after_registration=None,
    )

    response = client.get(_player_urls(course)["view_course_item"])

    record.refresh_from_db()
    attempt.refresh_from_db()
    assert response.status_code == 200
    assert (
        record.completed_time,
        record.progress_percentage,
        CourseFormAttempt.objects.count(),
    ) == stored_before
    assert attempt.completed_time == REGISTERED_AT


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_a_cohort_override_restores_a_cohort_member(mock_site_context):
    course, _form = _ended_course()
    user, cohort_record, _individual = learner_with_two_grants(course)
    cohort_record.created_at = REGISTERED_AT
    cohort_record.save(update_fields=["created_at"])
    client = Client()
    client.force_login(user)
    client_response = client.get(_player_urls(course)["view_course_item"])
    assert client_response.status_code == 302
    CohortDeadlineOverrideFactory(
        cohort_registration=cohort_record.cohort_registration,
        kind=DeadlineKind.FIXED,
        due_date=datetime.date(2026, 9, 2),
        due_days_after_registration=None,
    )

    response = client.get(_player_urls(course)["view_course_item"])

    assert response.status_code == 200


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_a_closed_item_stays_closed_after_access_is_restored(mock_site_context):
    course, _form = _ended_course()
    set_due_date(course, course.viewable_items()[0], due_date=datetime.date(2020, 1, 1))
    CourseDeadlineConfig.objects.filter(course=course).update(close_items="on")
    _user, record, client = _ended_learner(course)
    LearnerDeadlineOverrideFactory(
        course_progress=record,
        kind=DeadlineKind.FIXED,
        due_date=datetime.date(2026, 9, 2),
        due_days_after_registration=None,
    )

    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    assert response.status_code == 200
    assert "learner_interface/course_item_closed.html" in [
        template.name for template in response.templates
    ]
