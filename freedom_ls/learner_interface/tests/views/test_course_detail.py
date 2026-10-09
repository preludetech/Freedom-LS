"""Tests for the course detail page."""

from __future__ import annotations

import itertools
import re
from datetime import timedelta
from decimal import Decimal
from typing import cast

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseCategoryFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart, CourseVisibility
from freedom_ls.content_engine.prices import CoursePrice
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_interface.tests.helpers import form_attempt, topic_completion
from freedom_ls.learner_interface.utils import (
    BLOCKED,
    COMPLETE,
    FAILED,
    IN_PROGRESS,
    READY,
    derive_part_status,
    get_course_index,
)
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory

# The wrapper the express-interest partial renders around its call to action.
EXPRESS_INTEREST_CTA = 'id="express-interest-cta-'


# Tests for the public course_detail view for anonymous users.
#
# Covers:
# - Anonymous GET of a free course detail → 200, CTA "Enrol for free" with access URL
# - Anonymous GET of a gated course detail → 200, CTA "Apply now" with apply URL
# - ToC items render as BLOCKED (no URLs) for anonymous viewers
# - Regression: no crash on application-gated course for anonymous user


@pytest.mark.django_db
def test_anonymous_free_course_detail_cta_label_is_enrol_for_free(
    mock_site_context, course_with_topic
):
    """Anonymous user on a free course detail page sees 'Enrol for free' CTA."""
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert "Enrol for free" in response.content.decode()


@pytest.mark.django_db
def test_anonymous_free_course_detail_cta_href_is_access_url(
    mock_site_context, course_with_topic
):
    """Anonymous user on a free course detail page: CTA href points to initiate_course_access."""
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    access_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    assert access_url in response.content.decode()


@pytest.mark.django_db
def test_anonymous_gated_course_detail_returns_200(
    mock_site_context, course_with_topic
):
    """Anonymous GET of a gated course detail returns 200 — no crash, no login redirect.

    Regression test: ApplicationCourseAccessBackend.get_access previously crashed
    for anonymous users due to an unsafe application DB query.
    """
    course = course_with_topic(access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_gated_course_detail_cta_label_is_apply_now(
    mock_site_context, course_with_topic
):
    """Anonymous user on a gated course detail page sees 'Apply now' CTA."""
    course = course_with_topic(access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert "Apply now" in response.content.decode()


@pytest.mark.django_db
def test_anonymous_gated_course_detail_cta_href_is_apply_url(
    mock_site_context, course_with_topic
):
    """Anonymous user on a gated course detail page: CTA href points to apply view."""
    course = course_with_topic(access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert apply_url in response.content.decode()


@pytest.mark.django_db
def test_anonymous_gated_course_detail_shows_by_application(
    mock_site_context, course_with_topic
):
    """Anonymous gated course detail shows 'By application' near the CTA."""
    course = course_with_topic(access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert "By application" in response.content.decode()


@pytest.mark.django_db
def test_anonymous_free_course_detail_toc_items_all_blocked(
    mock_site_context, course_with_topic
):
    """All ToC items are BLOCKED for an anonymous viewer on a free course."""
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children, "Expected at least one ToC item"
    assert all(child["status"] == BLOCKED for child in children)


@pytest.mark.django_db
def test_anonymous_gated_course_detail_toc_items_all_blocked(
    mock_site_context, course_with_topic
):
    """All ToC items are BLOCKED for an anonymous viewer on a gated course."""
    course = course_with_topic(access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children, "Expected at least one ToC item"
    assert all(child["status"] == BLOCKED for child in children)


@pytest.mark.django_db
def test_anonymous_free_course_detail_toc_items_have_no_url(
    mock_site_context, course_with_topic
):
    """BLOCKED ToC items for an anonymous viewer carry no URL."""
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    children = response.context["children"]
    assert children, "Expected at least one ToC item"
    assert all(not child.get("url") for child in children)


# Tests for course_detail visibility behaviour (Task 4.1).
#
# Covers the three detail-page rules added for coming-soon / hidden courses:
#   * hidden + unregistered -> 404; hidden + registered -> 200 accessible.
#   * coming_soon detail renders the shared express-interest affordance (not the
#     generic enrol button), reflecting the user's current interest state.
#   * published detail unchanged (still renders the generic CTA).


def _detail_url(course: Course) -> str:
    return reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_hidden_course_unregistered_user_gets_404(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))

    assert response.status_code == 404


@pytest.mark.django_db
def test_hidden_course_registered_user_gets_200(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(_detail_url(course))

    assert response.status_code == 200


@pytest.mark.django_db
def test_hidden_course_removed_learner_gets_404(
    mock_site_context, course_with_topic, logged_in_client
):
    """A removed learner's active registration grants nothing: the hidden
    course 404s again, exactly as it would for an unregistered user."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    learner = LearnerFactory(is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    client = logged_in_client(learner.user)

    response = client.get(_detail_url(course))

    assert response.status_code == 404


@pytest.mark.django_db
def test_hidden_course_registered_through_two_organisations_gets_200(
    mock_site_context, course_with_topic, logged_in_client
):
    """A learner can hold two registrations for one course, one per
    organisation. The detail page must still render, not 500."""
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user,
        course=course,
        is_active=True,
        learner__organisation=OrganisationFactory(),
    )
    LearnerCourseRegistrationFactory(
        learner__user=user,
        course=course,
        is_active=True,
        learner__organisation=OrganisationFactory(),
    )
    client = logged_in_client(user)

    response = client.get(_detail_url(course))

    assert response.status_code == 200
    assert course.title in response.content.decode()


@pytest.mark.django_db
def test_coming_soon_detail_renders_express_interest_not_enrol(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert response.status_code == 200
    assert "I'm interested" in body
    assert "Enrol & start" not in body


@pytest.mark.django_db
def test_coming_soon_detail_default_state_is_not_interested(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert "I'm interested" in body
    assert "Remove interest" not in body


@pytest.mark.django_db
def test_coming_soon_detail_interested_state_when_interest_exists(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert "Remove interest" in body
    assert "I'm interested" not in body


@pytest.mark.django_db
def test_coming_soon_registered_user_gets_generic_cta_not_express_interest(
    mock_site_context, course_with_topic, logged_in_client
):
    """A registered learner on a coming-soon course keeps the normal registered CTA.

    coming_soon exempts already-registered learners, so the detail page must not
    show the express-interest control (which would bounce / hide their content).
    """
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert response.status_code == 200
    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_published_detail_renders_generic_cta(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.PUBLISHED, slug="published-course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))
    body = response.content.decode()

    # The free backend's acquisition CTA for an unregistered learner on a
    # published course is "Enrol for free"; the express-interest affordance must
    # not appear for a published course.
    assert response.status_code == 200
    assert "Enrol for free" in body
    assert EXPRESS_INTEREST_CTA not in body


@pytest.mark.django_db
def test_hidden_course_unregistered_user_gets_200_with_visibility_override(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        get_course_access_backend.cache_clear()
        response = client.get(_detail_url(course))

    assert response.status_code == 200


@pytest.mark.django_db
def test_coming_soon_detail_shows_generic_cta_with_visibility_override(
    mock_site_context, course_with_topic, logged_in_client
):
    """With the override on, a coming-soon course looks fully published: the
    generic enrol CTA renders instead of the express-interest affordance."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        get_course_access_backend.cache_clear()
        response = client.get(_detail_url(course))
    body = response.content.decode()

    assert response.status_code == 200
    assert EXPRESS_INTEREST_CTA not in body


# The course detail hero shows a chip naming the course's dashboard_category.


@pytest.mark.django_db
def test_chip_shows_the_dashboard_category_title(mock_site_context, course_with_topic):
    category = CourseCategoryFactory(title="Data literacy")
    course = course_with_topic(access_type="free", dashboard_category=category)
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    html = response.content.decode()
    assert 'data-testid="course-category-chip"' in html
    assert "Data literacy" in html


@pytest.mark.django_db
def test_chip_absent_when_dashboard_category_is_null(
    mock_site_context, course_with_topic
):
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert 'data-testid="course-category-chip"' not in response.content.decode()


# Behaviour tests for the ``table_of_contents_in_development`` course flag.
#
# Covers the three TOC surfaces on the course detail page (Lessons stat card,
# "This course includes" panel, "Course content" section) being omitted while
# a course's contents are still being built.


@pytest.mark.django_db
def test_toc_in_development_hides_all_three_surfaces(
    mock_site_context, course_with_topic
):
    """Flag on, no assessments, no certificate: no TOC surface renders at all."""
    course = course_with_topic(
        access_type="free", table_of_contents_in_development=True
    )
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert course.title in content
    assert "Lessons" not in content
    assert "This course includes" not in content
    assert "Course content" not in content


@pytest.mark.django_db
def test_toc_in_development_with_assessments_shows_only_assessments_line(
    mock_site_context, course_with_topic
):
    """Flag on with assessments: panel shows only 'Includes assessments'."""
    from freedom_ls.form_engine.factories import FormFactory

    course = course_with_topic(
        access_type="free", table_of_contents_in_development=True
    )
    course.items.create(child=FormFactory(), order=1)
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert "This course includes" in content
    assert "Includes assessments" in content
    assert "Lessons" not in content
    assert "1 lesson" not in content
    assert "Course content" not in content


@pytest.mark.django_db
def test_toc_in_development_off_shows_all_three_surfaces(
    mock_site_context, course_with_topic
):
    """Flag omitted (default False): page renders exactly as before — all three surfaces present."""
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert "Lessons" in content
    assert "This course includes" in content
    assert "1 lesson" in content
    assert "Course content" in content


# Tests for where the course-price component is placed: the course card, the
# course row, the course page's stats strip and its sign-up panel.
#
# Per project conventions: no CSS class assertions. We assert on the
# component's ``data-testid`` and on visible text.

PRICE_TESTID = 'data-testid="course-price"'


def _priced(course_with_topic, **kwargs: object) -> Course:
    return cast(
        "Course",
        course_with_topic(
            price_kind="fixed",
            price_amount=Decimal("1499.00"),
            price_currency="ZAR",
            **kwargs,
        ),
    )


def _priced_coming_soon(*, slug: str, title: str) -> Course:
    course: Course = CourseFactory(
        title=title,
        slug=slug,
        visibility=CourseVisibility.COMING_SOON,
        price_kind="fixed",
        price_amount=Decimal("1499.00"),
        price_currency="ZAR",
    )
    topic = TopicFactory(title=f"{slug}-t", slug=f"{slug}-topic", content="content")
    course.items.create(child=topic, order=0)
    return course


@pytest.mark.django_db
def test_dashboard_card_shows_price_to_anonymous_visitor(
    mock_site_context, course_with_topic
):
    _priced(course_with_topic)
    client = Client()

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_shows_price_to_signed_in_not_registered_visitor(
    mock_site_context, course_with_topic, logged_in_client
):
    _priced(course_with_topic)
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_hides_price_for_registered_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    course = _priced(course_with_topic)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_shows_price_for_coming_soon_course(mock_site_context):
    _priced_coming_soon(slug="coming-soon-priced", title="Coming Soon Priced")
    client = Client()

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_with_no_price_shows_no_price_component(
    mock_site_context, course_with_topic
):
    course_with_topic()
    client = Client()

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_shows_price_to_anonymous_visitor(
    mock_site_context, course_with_topic
):
    _priced(course_with_topic)
    client = Client()

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_shows_price_to_signed_in_not_registered_visitor(
    mock_site_context, course_with_topic, logged_in_client
):
    _priced(course_with_topic)
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_hides_price_for_registered_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    course = _priced(course_with_topic)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_shows_price_for_coming_soon_course(mock_site_context):
    _priced_coming_soon(slug="coming-soon-priced-row", title="Coming Soon Priced Row")
    client = Client()

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_with_no_price_shows_no_price_component(
    mock_site_context, course_with_topic
):
    course_with_topic()
    client = Client()

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID not in response.content.decode()


@pytest.mark.django_db
def test_course_detail_shows_price_twice_for_anonymous_visitor(
    mock_site_context, course_with_topic
):
    """The stats-strip cell and the sign-up panel each render their own
    price, so an anonymous (not-registered) visitor sees two."""
    course = _priced(course_with_topic)
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert body.count(PRICE_TESTID) == 2


@pytest.mark.django_db
def test_course_detail_shows_price_once_for_registered_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    """The sign-up panel price is withheld once registered, so only the
    stats-strip cell remains."""
    course = _priced(course_with_topic)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert body.count(PRICE_TESTID) == 1


@pytest.mark.django_db
def test_course_detail_application_gated_priced_course_still_shows_apply_cta(
    mock_site_context, course_with_topic
):
    course = _priced(course_with_topic, access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert "By application" in body
    assert "Apply now" in body
    assert PRICE_TESTID in body


@pytest.mark.django_db
def test_course_detail_with_no_price_shows_no_price_component(
    mock_site_context, course_with_topic
):
    course = course_with_topic()
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert PRICE_TESTID not in body


# Tests for the <c-course-price /> cotton component.
#
# Renders the component through a template string with a ``CoursePrice`` in the
# context, the same pattern ``test_button_component.py`` and
# ``test_error_page_component.py`` use for other cotton components.

_cotton_compiler = CottonCompiler()


def _render(template_string: str, price: CoursePrice) -> str:
    processed = _cotton_compiler.process(template_string)
    t = Template(processed)
    return t.render(Context({"price": price}))


FIXED = CoursePrice(kind="fixed", currency="ZAR", amount=Decimal("1499.00"))


RANGE = CoursePrice(
    kind="range",
    currency="ZAR",
    low_amount=Decimal("1200.00"),
    high_amount=Decimal("3000.00"),
)


OPEN_RANGE = CoursePrice(kind="range", currency="ZAR", low_amount=Decimal("500.00"))


DISCOUNTED = CoursePrice(
    kind="discounted",
    currency="ZAR",
    amount=Decimal("1499.00"),
    sale_amount=Decimal("999.00"),
)


ON_REQUEST = CoursePrice(kind="on_request")


class TestFixedPrice:
    def test_compact_shows_formatted_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', FIXED)
        assert FIXED.formatted_amount in result

    def test_full_shows_formatted_amount(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', FIXED)
        assert FIXED.formatted_amount in result

    def test_compact_omits_tax_note(self) -> None:
        priced = CoursePrice(
            kind="fixed",
            currency="ZAR",
            amount=Decimal("1499.00"),
            tax_note="incl. VAT",
        )
        result = _render('<c-course-price :price="price" />', priced)
        assert "incl. VAT" not in result

    def test_full_shows_tax_note_when_set(self) -> None:
        priced = CoursePrice(
            kind="fixed",
            currency="ZAR",
            amount=Decimal("1499.00"),
            tax_note="incl. VAT",
        )
        result = _render('<c-course-price :price="price" variant="full" />', priced)
        assert "incl. VAT" in result


class TestRangePrice:
    def test_compact_shows_from_low_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', RANGE)
        assert f"From {RANGE.formatted_low_amount}" in result
        assert RANGE.formatted_high_amount not in result

    def test_full_shows_low_and_high_amount(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', RANGE)
        assert RANGE.formatted_low_amount in result
        assert RANGE.formatted_high_amount in result


class TestOpenEndedRangePrice:
    def test_compact_shows_from_low_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', OPEN_RANGE)
        assert f"From {OPEN_RANGE.formatted_low_amount}" in result

    def test_full_shows_from_low_amount_with_no_upper_end(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', OPEN_RANGE)
        assert f"From {OPEN_RANGE.formatted_low_amount}" in result
        assert "\N{EN DASH}" not in result


class TestDiscountedPrice:
    def test_compact_shows_original_and_sale_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert DISCOUNTED.formatted_amount in result
        assert DISCOUNTED.formatted_sale_amount in result

    def test_compact_has_sr_only_original_price_label(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert "sr-only" in result
        assert "Original price:" in result

    def test_compact_has_sr_only_now_label(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert "Now:" in result

    def test_full_shows_tax_note_when_set(self) -> None:
        priced = CoursePrice(
            kind="discounted",
            currency="ZAR",
            amount=Decimal("1499.00"),
            sale_amount=Decimal("999.00"),
            tax_note="incl. VAT",
        )
        result = _render('<c-course-price :price="price" variant="full" />', priced)
        assert "incl. VAT" in result


class TestOnRequestPrice:
    def test_compact_shows_price_on_request(self) -> None:
        result = _render('<c-course-price :price="price" />', ON_REQUEST)
        assert "Price on request" in result

    def test_full_shows_price_on_request(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', ON_REQUEST)
        assert "Price on request" in result


@pytest.mark.django_db
def test_course_part_children_have_status_and_url(mock_site_context):
    """Test that CoursePart children have proper status and url fields."""
    # Create a course with a CoursePart that contains children
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    course_part: CoursePart = CoursePartFactory(title="Chapter 1", slug="chapter-1")
    topic = TopicFactory(title="Topic 1", slug="topic-1", content="Test content")
    form = FormFactory(title="Quiz 1", slug="quiz-1")

    # Add course part as child of course
    course.items.create(child=course_part, order=0)

    # Add topic and form as children of course part
    course_part.items.create(child=topic, order=0)
    course_part.items.create(child=form, order=1)

    # Create a user and register them for the course
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    # Get the course index
    children = get_course_index(user=user, course=course, can_access_content=True)

    # Find the course part in the children
    course_part_dict = children[0]

    assert course_part_dict["type"] == "COURSE_PART"
    assert "children" in course_part_dict
    assert len(course_part_dict["children"]) == 2

    # Check that children have url and status
    topic_dict = course_part_dict["children"][0]
    assert topic_dict["title"] == "Topic 1"
    assert topic_dict["type"] == "TOPIC"
    assert "url" in topic_dict, "CoursePart child should have url"
    assert "status" in topic_dict, "CoursePart child should have status"
    assert topic_dict["status"] == READY  # First item should be READY
    assert topic_dict["url"] is not None  # Should have a URL

    form_dict = course_part_dict["children"][1]
    assert form_dict["title"] == "Quiz 1"
    assert form_dict["type"] == "FORM"
    assert "url" in form_dict
    assert "status" in form_dict
    assert form_dict["status"] == BLOCKED  # Second item should be BLOCKED


@pytest.mark.django_db
def test_course_part_status_based_on_children(mock_site_context):
    """Test that CoursePart status is calculated based on its children."""
    # Create a course with a CoursePart
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    course_part: CoursePart = CoursePartFactory(title="Chapter 1", slug="chapter-1")
    topic = TopicFactory(title="Topic 1", slug="topic-1", content="Test content")

    course.items.create(child=course_part, order=0)
    course_part.items.create(child=topic, order=0)

    # Create a user and register them
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    # Get the course index
    children = get_course_index(user=user, course=course, can_access_content=True)
    course_part_dict = children[0]

    # CoursePart should have READY status if first child is READY
    assert course_part_dict["status"] == READY
    # CoursePart URL should point to the READY child's URL
    topic_child_dict = course_part_dict["children"][0]
    assert course_part_dict["url"] == topic_child_dict["url"]


@pytest.mark.django_db
def test_course_part_row_url_resolves_to_first_viewable_child_index(mock_site_context):
    """A CoursePart's TOC row url must point to its first viewable child's URL."""
    course: Course = CourseFactory(title="Multi", slug="multi")
    p1: CoursePart = CoursePartFactory(title="P1", slug="p1")
    p2: CoursePart = CoursePartFactory(title="P2", slug="p2")
    p1a = TopicFactory(title="P1A", slug="p1a")
    p1b = TopicFactory(title="P1B", slug="p1b")
    p2a = TopicFactory(title="P2A", slug="p2a")

    course.items.create(child=p1, order=0)
    course.items.create(child=p2, order=1)
    p1.items.create(child=p1a, order=0)
    p1.items.create(child=p1b, order=1)
    p2.items.create(child=p2a, order=0)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    # Complete all viewable items so every item has a non-BLOCKED status (and thus a URL).
    now = timezone.now()
    for topic in (p1a, p1b, p2a):
        topic_completion(course, user, topic, complete_time=now)

    children = get_course_index(user=user, course=course, can_access_content=True)

    # Independent oracle: viewable order is [p1a, p1b, p2a] -> indices [1, 2, 3].
    viewable_order = course.viewable_items()
    p1_first_child_idx = viewable_order.index(p1a) + 1
    p2_first_child_idx = viewable_order.index(p2a) + 1

    p1_dict = children[0]
    p2_dict = children[1]

    expected_p1_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": p1_first_child_idx},
    )
    expected_p2_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": p2_first_child_idx},
    )

    assert p1_dict["url"] == expected_p1_url
    assert p2_dict["url"] == expected_p2_url


@pytest.mark.django_db
def test_consecutive_viewable_items_have_dense_indices(mock_site_context):
    """URLs of consecutive viewable items in the TOC differ by exactly 1 in index."""
    course: Course = CourseFactory(title="Dense", slug="dense")
    p1: CoursePart = CoursePartFactory(title="P1", slug="p1")
    p2: CoursePart = CoursePartFactory(title="P2", slug="p2")
    p1a = TopicFactory(title="P1A", slug="p1a")
    p1b = TopicFactory(title="P1B", slug="p1b")
    p2a = TopicFactory(title="P2A", slug="p2a")
    direct = TopicFactory(title="Direct", slug="direct")

    course.items.create(child=p1, order=0)
    course.items.create(child=p2, order=1)
    course.items.create(child=direct, order=2)
    p1.items.create(child=p1a, order=0)
    p1.items.create(child=p1b, order=1)
    p2.items.create(child=p2a, order=0)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    # Complete all viewable items so every viewable row has a URL we can compare.
    now = timezone.now()
    for topic in (p1a, p1b, p2a, direct):
        topic_completion(course, user, topic, complete_time=now)

    children = get_course_index(user=user, course=course, can_access_content=True)

    # Flatten viewable rows in URL-order: each part's children, then direct items.
    flat_rows = []
    for row in children:
        if "children" in row:
            flat_rows.extend(row["children"])
        else:
            flat_rows.append(row)

    indices = [int(row["url"].rstrip("/").rsplit("/", 1)[-1]) for row in flat_rows]
    diffs = [b - a for a, b in itertools.pairwise(indices)]
    assert diffs == [1] * len(diffs)
    # Sanity check: we actually had multiple rows to compare.
    assert len(indices) >= 2


@pytest.mark.django_db
def test_course_part_url_resumes_at_in_progress_child(mock_site_context):
    """When a part has a completed child and an in-progress child, the part row routes to in-progress."""
    course: Course = CourseFactory(title="Resume", slug="resume")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="chapter")
    first = TopicFactory(title="First", slug="first", content="first")
    second = TopicFactory(title="Second", slug="second", content="second")
    third = TopicFactory(title="Third", slug="third", content="third")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)
    part.items.create(child=third, order=2)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    # First item completed; second item started but not complete.
    topic_completion(course, user, first, complete_time=timezone.now())
    topic_completion(course, user, second, complete_time=None)

    children = get_course_index(user=user, course=course, can_access_content=True)
    part_dict = children[0]

    second_index = course.viewable_items().index(second) + 1
    expected_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": second_index},
    )
    assert part_dict["status"] == IN_PROGRESS
    assert part_dict["url"] == expected_url


@pytest.mark.django_db
def test_course_part_url_skips_completed_first_child_to_first_ready(mock_site_context):
    """The part row routes past a completed child to the first one still open.

    Routing and labelling are separate questions: the row links to the READY
    child, but a part with work already behind it reads as in progress.
    """
    course: Course = CourseFactory(title="ReadyAfter", slug="ready-after")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="chapter")
    first = TopicFactory(title="First", slug="first", content="first")
    second = TopicFactory(title="Second", slug="second", content="second")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    # Complete first item; second item has no progress (becomes READY).
    topic_completion(course, user, first, complete_time=timezone.now())

    children = get_course_index(user=user, course=course, can_access_content=True)
    part_dict = children[0]

    second_index = course.viewable_items().index(second) + 1
    expected_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": second_index},
    )
    assert part_dict["status"] == IN_PROGRESS
    assert part_dict["url"] == expected_url


@pytest.mark.parametrize(
    ("child_statuses", "expected"),
    [
        ([], BLOCKED),
        ([COMPLETE, COMPLETE], COMPLETE),
        ([COMPLETE, COMPLETE, COMPLETE, READY], IN_PROGRESS),
        ([READY, COMPLETE], IN_PROGRESS),
        ([COMPLETE, IN_PROGRESS, BLOCKED], IN_PROGRESS),
        ([COMPLETE, FAILED, BLOCKED], FAILED),
        ([COMPLETE, BLOCKED], BLOCKED),
        ([READY, BLOCKED], READY),
        ([BLOCKED, BLOCKED], BLOCKED),
    ],
)
def test_derive_part_status_precedence(child_statuses, expected):
    """The whole precedence table, without the cost of building a course."""
    assert derive_part_status(child_statuses) == expected


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_a_part_whose_remaining_child_is_locked_reads_as_blocked(mock_site_context):
    """A part with nothing left to open cannot report work in flight.

    The completed child would otherwise carry the part to "In progress" while
    the routing chain found no child to link to, leaving a row labelled as
    under way with no way into it.
    """
    course: Course = CourseFactory(title="Locked Tail", slug="locked-tail")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="locked-chapter")
    done = TopicFactory(title="Done", slug="locked-done", content="x")
    locked = TopicFactory(title="Locked", slug="locked-locked", content="x")

    course.items.create(child=part, order=0)
    part.items.create(child=done, order=0)
    part.items.create(child=locked, order=1)

    user = UserFactory()
    registration = LearnerCourseRegistrationFactory(learner__user=user, course=course)
    topic_completion(course, user, done, complete_time=timezone.now())
    LearnerDeadlineFactory(
        learner_course_registration=registration,
        content_item=locked,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    part_dict = get_course_index(user=user, course=course, can_access_content=True)[0]

    assert [child["status"] for child in part_dict["children"]] == [COMPLETE, BLOCKED]
    assert part_dict["status"] == BLOCKED
    assert part_dict["url"] is None


@pytest.mark.django_db
def test_course_part_partly_complete_reads_as_in_progress(mock_site_context):
    """A part with some children complete and one not started reads "In progress".

    The part row must never be labelled from the one child it links to: with
    three children complete and a fourth not, that reads "Not started" directly
    above three rows reading "Completed".
    """
    course: Course = CourseFactory(title="Partly", slug="partly")
    part: CoursePart = CoursePartFactory(title="Core Concepts", slug="core-concepts")
    done = [
        TopicFactory(title=f"Done {n}", slug=f"done-{n}", content="x") for n in range(3)
    ]
    outstanding = TopicFactory(title="Outstanding", slug="outstanding", content="x")

    course.items.create(child=part, order=0)
    for order, topic in enumerate([*done, outstanding]):
        part.items.create(child=topic, order=order)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    for topic in done:
        topic_completion(course, user, topic, complete_time=timezone.now())

    children = get_course_index(user=user, course=course, can_access_content=True)
    part_dict = children[0]

    assert [child["status"] for child in part_dict["children"]] == [
        COMPLETE,
        COMPLETE,
        COMPLETE,
        READY,
    ]
    assert part_dict["status"] == IN_PROGRESS

    outstanding_index = course.viewable_items().index(outstanding) + 1
    assert part_dict["url"] == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": outstanding_index},
    )


@pytest.mark.django_db
def test_course_part_with_a_later_completion_reads_as_in_progress(mock_site_context):
    """The inverse ordering: the open child comes first, the completed one after."""
    course: Course = CourseFactory(title="LaterDone", slug="later-done")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="chapter")
    first = TopicFactory(title="First", slug="first", content="x")
    second = TopicFactory(title="Second", slug="second", content="x")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    topic_completion(course, user, second, complete_time=timezone.now())

    children = get_course_index(user=user, course=course, can_access_content=True)
    part_dict = children[0]

    assert part_dict["status"] == IN_PROGRESS


@pytest.mark.django_db
def test_empty_course_part_row_has_no_url(mock_site_context):
    """A CoursePart with no viewable children gets url=None."""
    course: Course = CourseFactory(title="WithEmpty", slug="with-empty")
    empty_part: CoursePart = CoursePartFactory(title="Empty", slug="empty")
    course.items.create(child=empty_part, order=0)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert children[0]["url"] is None


@pytest.mark.django_db
def test_course_part_holding_a_failed_quiz_reads_as_needing_a_retry(mock_site_context):
    """A part whose only open work is a re-sit routes to it instead of locking.

    The quiz itself stays reachable so it can be retried, so a part row drawn as
    BLOCKED with no url would deny what its own child allows.
    """
    course: Course = CourseFactory(title="Retry", slug="retry")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="chapter")
    first = TopicFactory(title="First", slug="first", content="first")
    quiz = FormFactory(
        title="Quiz",
        slug="quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    after = TopicFactory(title="After", slug="after", content="after")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=quiz, order=1)
    part.items.create(child=after, order=2)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    topic_completion(course, user, first, complete_time=timezone.now())
    form_attempt(
        course,
        user,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )

    children = get_course_index(user=user, course=course, can_access_content=True)
    part_dict = children[0]

    quiz_index = course.viewable_items().index(quiz) + 1
    expected_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": quiz_index},
    )
    assert part_dict["status"] == FAILED
    assert part_dict["url"] == expected_url


# The outline's course-part rows are what a screen reader walks, so the
# accessible text of each is asserted on the rendered markup.


def _outline_part_buttons(logged_in_client, user, course) -> list[str]:
    """The markup of every course-part toggle button in the player's outline."""
    response = logged_in_client(user).get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    content = response.content.decode()
    outline = content.split('<nav aria-label="Course outline">')[1].split("</nav>")[0]
    return re.findall(
        r'<button x-on:click="toggleExpanded".*?</button>', outline, re.DOTALL
    )


@pytest.mark.django_db
def test_course_part_toggle_hides_its_chevron_from_assistive_technology(
    mock_site_context, logged_in_client
):
    """State is conveyed by aria-expanded, so the expand/collapse icons never reach a screen reader."""
    course: Course = CourseFactory(title="Chevron", slug="chevron")
    part: CoursePart = CoursePartFactory(title="Chapter One", slug="chapter-one")
    course.items.create(child=TopicFactory(title="Landing", slug="landing"), order=0)
    course.items.create(child=part, order=1)
    part.items.create(child=TopicFactory(title="Inner", slug="inner"), order=0)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)

    (button,) = _outline_part_buttons(logged_in_client, user, course)

    announced, chevron = button.split('aria-hidden="true"', 1)
    assert "Chapter One" in announced
    assert "x-bind:aria-expanded" in announced
    announced_text = re.sub(r"<[^>]+>", " ", announced)
    announced_labels = re.findall(r'aria-label="([^"]*)"', announced)
    assert not re.search(r"expand|collapse", announced_text, re.IGNORECASE)
    assert not re.search(r"expand|collapse", " ".join(announced_labels), re.IGNORECASE)
    assert re.search(r"expand|collapse", chevron)


@pytest.mark.django_db
def test_course_part_row_announces_in_progress_over_completed_children(
    mock_site_context, logged_in_client
):
    """A part with three finished children and one outstanding is announced "In progress"."""
    course: Course = CourseFactory(title="Announce", slug="announce")
    part: CoursePart = CoursePartFactory(title="Core Concepts", slug="core-concepts")
    done = [
        TopicFactory(title=f"Done {n}", slug=f"done-{n}", content="x") for n in range(3)
    ]
    outstanding = TopicFactory(title="Outstanding", slug="outstanding", content="x")
    course.items.create(child=TopicFactory(title="Landing", slug="landing"), order=0)
    course.items.create(child=part, order=1)
    for order, topic in enumerate([*done, outstanding]):
        part.items.create(child=topic, order=order)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    for topic in done:
        topic_completion(course, user, topic, complete_time=timezone.now())

    response = logged_in_client(user).get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    outline = (
        response.content.decode()
        .split('<nav aria-label="Course outline">')[1]
        .split("</nav>")[0]
    )
    (button,) = re.findall(
        r'<button x-on:click="toggleExpanded".*?</button>', outline, re.DOTALL
    )
    button_text = " ".join(re.sub(r"<[^>]+>", " ", button).split())

    assert re.search(r"In progress.*Core Concepts", button_text)
    assert "Not started" not in button_text
    assert outline.count(">Completed<") == 3
