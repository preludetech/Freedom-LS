"""Tests for the Course, CoursePart and CourseCategory models."""

from __future__ import annotations

import tempfile
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import time_machine

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import (
    CourseCategoryFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
    save_course,
)
from freedom_ls.content_engine.models import (
    Course,
    CoursePart,
    DifficultyLevel,
    PriceKind,
)
from freedom_ls.content_engine.prices import CoursePrice
from freedom_ls.content_engine.schema import Course as CourseSchema
from freedom_ls.content_engine.validate import parse_single_file
from freedom_ls.form_engine.factories import FormFactory

# CourseCategory: per-site uniqueness, Course ordering, and the dashboard_category FK.


@pytest.mark.django_db
def test_duplicate_slug_within_one_site_raises_integrity_error(mock_site_context):
    CourseCategoryFactory(slug="technical")

    with pytest.raises(IntegrityError), transaction.atomic():
        CourseCategoryFactory(slug="technical")


@pytest.mark.django_db
def test_duplicate_slug_across_two_sites_is_allowed(mock_site_context):
    CourseCategoryFactory(slug="technical")
    other_site = SiteFactory()

    second = CourseCategoryFactory(slug="technical", site=other_site)

    assert second.site == other_site


@pytest.mark.django_db
def test_courses_come_back_ordered_by_title_then_pk(mock_site_context):
    zebra = CourseFactory(title="Zebra")
    alpha_low = CourseFactory(title="Alpha", slug="alpha-1", id=uuid.UUID(int=1))
    alpha_high = CourseFactory(title="Alpha", slug="alpha-2", id=uuid.UUID(int=2))

    assert list(Course.objects.all()) == [alpha_low, alpha_high, zebra]


@pytest.mark.django_db
def test_deleting_a_category_nulls_dashboard_category_on_its_courses(
    mock_site_context,
):
    category = CourseCategoryFactory()
    course = CourseFactory(dashboard_category=category)

    category.delete()
    course.refresh_from_db()

    assert course.dashboard_category is None


# Tests for the collection_items()/collection_items_flat()/viewable_collection_items()
# trio on Course and CoursePart, and their positional relationship to the existing
# children()/children_flat()/viewable_items() accessors.


@pytest.mark.django_db
def test_viewable_collection_items_names_same_content_as_viewable_items(
    mock_site_context,
):
    """viewable_collection_items()[n].child is viewable_items()[n] at every position.

    The course player's 1-based index depends on this positional identity.
    """
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    inside_form = FormFactory(title="F1", slug="f1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    part.items.create(child=inside_form, order=1)
    course.items.create(child=direct_topic, order=1)

    viewable_items = course.viewable_items()
    viewable_collection_items = course.viewable_collection_items()

    assert len(viewable_items) == len(viewable_collection_items)
    assert [ci.child for ci in viewable_collection_items] == viewable_items


@pytest.mark.django_db
def test_children_unchanged_for_course_without_course_parts(mock_site_context):
    """children() still returns exactly the resolved children, with no CoursePart."""
    course: Course = CourseFactory(title="C", slug="c")
    topic = TopicFactory(title="T1", slug="t1")
    form = FormFactory(title="F1", slug="f1")

    course.items.create(child=topic, order=0)
    course.items.create(child=form, order=1)

    assert course.children() == [topic, form]


@pytest.mark.django_db
def test_children_unchanged_for_course_with_course_parts(mock_site_context):
    """children() still returns the top-level children only, including the CoursePart itself."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    assert course.children() == [part, direct_topic]


@pytest.mark.django_db
def test_children_flat_unchanged_for_course_with_course_parts(mock_site_context):
    """children_flat() still descends into CourseParts in order."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    assert course.children_flat() == [part, inside_topic, direct_topic]


@pytest.mark.django_db
def test_viewable_items_unchanged_for_course_with_course_parts(mock_site_context):
    """viewable_items() still excludes CourseParts, derived through the new trio."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    assert course.viewable_items() == [inside_topic, direct_topic]


@pytest.mark.django_db
def test_collection_items_memoized_issues_one_items_query(
    mock_site_context, django_assert_num_queries
):
    """Two collection_items() calls on one instance issue only one round of queries.

    A single call issues two queries: the items query itself, plus one
    prefetch_related query resolving "child" for the one content type
    present. The second collection_items() call must add none.
    """
    course: Course = CourseFactory(title="C", slug="c")
    topic = TopicFactory(title="T1", slug="t1")
    course.items.create(child=topic, order=0)

    with django_assert_num_queries(2):
        course.collection_items()
        course.collection_items()


@pytest.mark.django_db
def test_course_part_collection_items_names_same_content_as_children(
    mock_site_context,
):
    """CoursePart.collection_items()[n].child is children()[n] at every position."""
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    inside_form = FormFactory(title="F1", slug="f1")

    part.items.create(child=inside_topic, order=0)
    part.items.create(child=inside_form, order=1)

    assert [ci.child for ci in part.collection_items()] == part.children()


# Tests for new Course fields: learning_outcomes, difficulty, estimated_duration.
#
# Display methods, and the content-save round trip of the new fields.


# ---------------------------------------------------------------------------
# display_estimated_duration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_display_estimated_duration_when_none_returns_empty_string(mock_site_context):
    """display_estimated_duration returns '' when field is None."""
    course = CourseFactory(estimated_duration=None)
    assert course.display_estimated_duration() == ""


@pytest.mark.django_db
def test_display_estimated_duration_when_zero_returns_empty_string(mock_site_context):
    """display_estimated_duration returns '' when field is zero timedelta."""
    course = CourseFactory(estimated_duration=timedelta(0))
    assert course.display_estimated_duration() == ""


@pytest.mark.django_db
def test_display_estimated_duration_two_hours(mock_site_context):
    """display_estimated_duration formats exactly 2 hours correctly."""
    course = CourseFactory(estimated_duration=timedelta(hours=2))
    assert course.display_estimated_duration() == "~2 hours"


@pytest.mark.django_db
def test_display_estimated_duration_one_hour(mock_site_context):
    """display_estimated_duration uses singular 'hour' for exactly 1 hour."""
    course = CourseFactory(estimated_duration=timedelta(hours=1))
    assert course.display_estimated_duration() == "~1 hour"


@pytest.mark.django_db
def test_display_estimated_duration_45_minutes(mock_site_context):
    """display_estimated_duration formats 45 minutes correctly."""
    course = CourseFactory(estimated_duration=timedelta(minutes=45))
    assert course.display_estimated_duration() == "~45 min"


@pytest.mark.django_db
def test_display_estimated_duration_one_hour_thirty_minutes(mock_site_context):
    """display_estimated_duration formats 1h30m correctly."""
    course = CourseFactory(estimated_duration=timedelta(hours=1, minutes=30))
    assert course.display_estimated_duration() == "~1 hour 30 min"


# ---------------------------------------------------------------------------
# get_difficulty_display tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_difficulty_display_blank_returns_empty_string(mock_site_context):
    """get_difficulty_display() returns '' when difficulty is blank."""
    course = CourseFactory(difficulty="")
    assert course.get_difficulty_display() == ""


@pytest.mark.django_db
def test_get_difficulty_display_beginner_returns_label(mock_site_context):
    """get_difficulty_display() returns 'Beginner' for BEGINNER choice."""
    course = CourseFactory(difficulty=DifficultyLevel.BEGINNER)
    assert course.get_difficulty_display() == "Beginner"


@pytest.mark.django_db
def test_get_difficulty_display_all_levels_returns_label(mock_site_context):
    """get_difficulty_display() returns 'All levels' for ALL_LEVELS choice."""
    course = CourseFactory(difficulty=DifficultyLevel.ALL_LEVELS)
    assert course.get_difficulty_display() == "All levels"


# ---------------------------------------------------------------------------
# A4 - Pydantic schema / content_save round-trip tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_content_save_round_trip_difficulty_dumps_as_string(
    mock_site_context, make_temp_file
):
    """save_with_uuid accepts difficulty as a bare string value, not an enum object."""
    content = """---
content_type: COURSE
title: Course With Difficulty
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000001
difficulty: beginner
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)
    assert len(parsed_items) == 1
    item = parsed_items[0]

    site = mock_site_context
    save_course(item, site, temp_file.parent)

    course = Course.objects.get(title="Course With Difficulty", site=site)
    assert course.difficulty == "beginner"


@pytest.mark.django_db
def test_content_save_round_trip_estimated_duration_dumps_as_timedelta(
    mock_site_context, make_temp_file
):
    """save_with_uuid accepts estimated_duration as a timedelta (from HH:MM:SS YAML string)."""
    content = """---
content_type: COURSE
title: Course With Duration
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000002
estimated_duration: "1:30:00"
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)
    assert len(parsed_items) == 1
    item = parsed_items[0]

    site = mock_site_context
    save_course(item, site, temp_file.parent)

    course = Course.objects.get(title="Course With Duration", site=site)
    assert course.estimated_duration == timedelta(hours=1, minutes=30)


@pytest.mark.django_db
def test_content_save_round_trip_learning_outcomes_saves_as_list(
    mock_site_context, make_temp_file
):
    """save_with_uuid accepts learning_outcomes as a list of strings."""
    content = """---
content_type: COURSE
title: Course With Outcomes
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000003
learning_outcomes:
  - Understand A
  - Recognise B
  - Author C
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)
    assert len(parsed_items) == 1
    item = parsed_items[0]

    site = mock_site_context
    save_course(item, site, temp_file.parent)

    course = Course.objects.get(title="Course With Outcomes", site=site)
    assert course.learning_outcomes == ["Understand A", "Recognise B", "Author C"]


@pytest.mark.django_db
def test_content_save_round_trip_course_without_new_fields_saves_cleanly(
    mock_site_context, make_temp_file
):
    """Existing courses without the new fields save cleanly (no errors, no placeholders)."""
    content = """---
content_type: COURSE
title: Old Style Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000004
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)
    assert len(parsed_items) == 1
    item = parsed_items[0]

    site = mock_site_context
    save_course(item, site, temp_file.parent)

    course = Course.objects.get(title="Old Style Course", site=site)
    assert course.difficulty == ""
    assert course.estimated_duration is None
    assert course.learning_outcomes == []


# Tests for Course price fields, the DB constraint, clean() and current_price().


@pytest.mark.django_db
def test_fixed_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.FIXED,
        price_amount=Decimal("1499.000"),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("1499.000")
    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_range_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.RANGE,
        price_low_amount=Decimal("1200.000"),
        price_high_amount=Decimal("3000.000"),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.RANGE
    assert course.price_low_amount == Decimal("1200.000")
    assert course.price_high_amount == Decimal("3000.000")


@pytest.mark.django_db
def test_open_ended_range_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.RANGE,
        price_low_amount=Decimal("500.000"),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.RANGE
    assert course.price_low_amount == Decimal("500.000")
    assert course.price_high_amount is None


@pytest.mark.django_db
def test_clean_passes_for_an_open_ended_range_price(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.RANGE,
        price_low_amount=Decimal("500.000"),
        price_currency="ZAR",
    )

    course.clean()


@pytest.mark.django_db
def test_range_price_without_a_low_amount_is_rejected(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.RANGE,
            price_high_amount=Decimal("500.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
def test_discounted_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_sale_ends_on=date(2026, 12, 31),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.DISCOUNTED
    assert course.price_amount == Decimal("1499.000")
    assert course.price_sale_amount == Decimal("999.000")
    assert course.price_sale_ends_on == date(2026, 12, 31)


# ---------------------------------------------------------------------------
# CheckConstraint: course_price_fields_match_kind
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fixed_price_rejects_a_stray_low_amount(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("100.000"),
            price_currency="ZAR",
            price_low_amount=Decimal("50.000"),
        )


@pytest.mark.django_db
def test_fixed_price_rejects_a_non_positive_amount(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("0.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
def test_fixed_price_rejects_a_blank_currency(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("100.000"),
            price_currency="",
        )


@pytest.mark.django_db
def test_range_price_rejects_low_not_below_high(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.RANGE,
            price_low_amount=Decimal("100.000"),
            price_high_amount=Decimal("100.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kind", "fields"),
    [
        (PriceKind.FIXED, {}),
        (PriceKind.DISCOUNTED, {"price_amount": Decimal("100.000")}),
        (PriceKind.DISCOUNTED, {"price_sale_amount": Decimal("50.000")}),
    ],
    ids=["fixed-no-amount", "discounted-no-sale", "discounted-no-original"],
)
def test_a_missing_required_amount_is_rejected(
    mock_site_context, kind: PriceKind, fields: dict[str, Decimal]
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(price_kind=kind, price_currency="ZAR", **fields)


@pytest.mark.django_db
def test_discounted_price_rejects_sale_not_below_original(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.DISCOUNTED,
            price_amount=Decimal("100.000"),
            price_sale_amount=Decimal("100.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
def test_on_request_price_rejects_a_stray_currency(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(price_kind=PriceKind.ON_REQUEST, price_currency="ZAR")


@pytest.mark.django_db
def test_no_price_rejects_a_stray_amount(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(price_kind="", price_amount=Decimal("100.000"))


# ---------------------------------------------------------------------------
# Course.clean()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_clean_fills_a_blank_currency_from_the_default(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.FIXED, price_amount=Decimal("100.000")
    )

    with override_settings(DEFAULT_CURRENCY="ZAR"):
        course.clean()

    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_clean_errors_when_currency_missing_and_no_default(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.FIXED, price_amount=Decimal("100.000")
    )

    with (
        override_settings(DEFAULT_CURRENCY=None),
        pytest.raises(ValidationError) as excinfo,
    ):
        course.clean()

    assert "price_currency" in excinfo.value.message_dict


@pytest.mark.django_db
def test_clean_errors_on_a_stray_field_for_the_kind(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.ON_REQUEST, price_amount=Decimal("100.000")
    )

    with pytest.raises(ValidationError) as excinfo:
        course.clean()

    assert "price_amount" in excinfo.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "field_name", "message"),
    [
        (
            {"price_kind": PriceKind.ON_REQUEST, "price_currency": "ZAR"},
            "price_currency",
            "Not used by an on-request price.",
        ),
        (
            {
                "price_kind": PriceKind.FIXED,
                "price_amount": Decimal("100.000"),
                "price_low_amount": Decimal("50.000"),
                "price_currency": "ZAR",
            },
            "price_low_amount",
            "Not used by a fixed price.",
        ),
        (
            {"price_kind": PriceKind.DISCOUNTED, "price_currency": "ZAR"},
            "price_amount",
            "Required for a discounted price.",
        ),
        (
            {
                "price_kind": PriceKind.DISCOUNTED,
                "price_amount": Decimal("100.000"),
                "price_sale_amount": Decimal("150.000"),
                "price_currency": "ZAR",
            },
            "price_sale_amount",
            "Must be less than the full amount.",
        ),
        (
            {
                "price_kind": PriceKind.RANGE,
                "price_low_amount": Decimal("300.000"),
                "price_high_amount": Decimal("100.000"),
                "price_currency": "ZAR",
            },
            "price_high_amount",
            "Must be greater than the low amount.",
        ),
    ],
    ids=["stray-currency", "stray-low-amount", "missing-amount", "sale", "range"],
)
def test_clean_errors_are_worded_for_the_admin(
    mock_site_context, fields: dict[str, object], field_name: str, message: str
) -> None:
    """Each error sits under its own admin input, so it names neither that
    field nor a raw kind value."""
    course = CourseFactory.build(**fields)

    with pytest.raises(ValidationError) as excinfo:
        course.clean()

    assert excinfo.value.message_dict[field_name] == [message]


@pytest.mark.django_db
def test_clean_errors_when_price_fields_set_without_a_kind(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind="", price_amount=Decimal("100.000"), price_currency="ZAR"
    )

    with pytest.raises(ValidationError) as excinfo:
        course.clean()

    assert "price_kind" in excinfo.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["price_amount", "price_low_amount"])
def test_clean_errors_when_a_zero_amount_is_set_without_a_kind(
    mock_site_context, field_name: str
) -> None:
    course = CourseFactory.build(price_kind="", **{field_name: Decimal("0")})

    with pytest.raises(ValidationError) as excinfo:
        course.clean()

    assert "price_kind" in excinfo.value.message_dict


@pytest.mark.django_db
def test_clean_passes_for_a_course_with_no_price(mock_site_context) -> None:
    course = CourseFactory.build()

    course.clean()


# ---------------------------------------------------------------------------
# Course.current_price()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_current_price_is_none_when_no_price_is_set(mock_site_context) -> None:
    course = CourseFactory()

    assert course.current_price() is None


@pytest.mark.django_db
def test_current_price_for_a_fixed_price(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.FIXED,
        price_amount=Decimal("1499.000"),
        price_currency="ZAR",
        price_tax_note="incl. VAT",
    )

    price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.FIXED,
        currency="ZAR",
        amount=Decimal("1499.000"),
        tax_note="incl. VAT",
    )


@pytest.mark.django_db
def test_current_price_for_a_range_price(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.RANGE,
        price_low_amount=Decimal("1200.000"),
        price_high_amount=Decimal("3000.000"),
        price_currency="ZAR",
    )

    price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.RANGE,
        currency="ZAR",
        low_amount=Decimal("1200.000"),
        high_amount=Decimal("3000.000"),
    )


@pytest.mark.django_db
def test_current_price_for_on_request(mock_site_context) -> None:
    course = CourseFactory(price_kind=PriceKind.ON_REQUEST)

    price = course.current_price()

    assert price == CoursePrice(kind=PriceKind.ON_REQUEST)


@pytest.mark.django_db
def test_current_price_discount_is_live_on_the_sale_end_date(
    mock_site_context,
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_sale_ends_on=date(2026, 12, 31),
        price_currency="ZAR",
    )

    with time_machine.travel("2026-12-31T23:00:00Z", tick=False):
        price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.DISCOUNTED,
        currency="ZAR",
        amount=Decimal("1499.000"),
        sale_amount=Decimal("999.000"),
        sale_ends_on=date(2026, 12, 31),
    )


@pytest.mark.django_db
def test_current_price_discount_becomes_fixed_the_day_after_it_ends(
    mock_site_context,
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_sale_ends_on=date(2026, 12, 31),
        price_currency="ZAR",
        price_tax_note="incl. VAT",
    )

    with time_machine.travel("2027-01-01T00:00:00Z", tick=False):
        price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.FIXED,
        currency="ZAR",
        amount=Decimal("1499.000"),
        tax_note="incl. VAT",
    )


@pytest.mark.django_db
def test_current_price_discount_with_no_end_date_never_expires(
    mock_site_context,
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_currency="ZAR",
    )

    with time_machine.travel("2099-01-01T00:00:00Z", tick=False):
        price = course.current_price()

    assert price.kind == PriceKind.DISCOUNTED


@pytest.mark.django_db
def test_current_price_runs_no_queries(
    mock_site_context, django_assert_num_queries
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.FIXED,
        price_amount=Decimal("1499.000"),
        price_currency="ZAR",
    )

    with django_assert_num_queries(0):
        course.current_price()


# Tests for Course.viewable_items().


@pytest.mark.django_db
def test_viewable_items_excludes_course_part_sentinels(mock_site_context):
    """viewable_items() returns only Topic/Form items in order, never CoursePart."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    inside_form = FormFactory(title="F1", slug="f1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    part.items.create(child=inside_form, order=1)
    course.items.create(child=direct_topic, order=1)

    result = course.viewable_items()

    assert result == [inside_topic, inside_form, direct_topic]
    assert not any(isinstance(item, CoursePart) for item in result)


@pytest.mark.django_db
def test_viewable_items_matches_children_flat_filtered(mock_site_context):
    """viewable_items() preserves the relative order of children_flat() minus CourseParts."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    expected = [c for c in course.children_flat() if not isinstance(c, CoursePart)]
    assert course.viewable_items() == expected


@pytest.mark.django_db
def test_viewable_items_empty_when_only_empty_part(mock_site_context):
    """A course whose only child is an empty CoursePart returns an empty list."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    course.items.create(child=part, order=0)

    assert course.viewable_items() == []


# Tests for importing the visibility field on Course via the content pipeline.


@pytest.mark.django_db
class TestCourseVisibilityContentImport:
    """Importing a course file persists visibility through the Pydantic schema."""

    def test_import_coming_soon_persists_coming_soon(
        self, mock_site_context, make_temp_file
    ):
        """A course file with visibility: coming_soon imports as a coming_soon course."""
        content = """---
content_type: COURSE
title: Coming Soon Imported Course
uuid: bbbbbbbb-cccc-dddd-eeee-000000000001
visibility: coming_soon
---
"""
        temp_file = make_temp_file(suffix=".md", content=content)
        parsed_items = parse_single_file(temp_file)
        assert len(parsed_items) == 1

        save_course(parsed_items[0], mock_site_context, temp_file.parent)

        course = Course.objects.get(
            title="Coming Soon Imported Course", site=mock_site_context
        )
        assert course.visibility == "coming_soon"

    def test_import_hidden_persists_hidden(self, mock_site_context, make_temp_file):
        """A course file with visibility: hidden imports as a hidden course."""
        content = """---
content_type: COURSE
title: Hidden Imported Course
uuid: bbbbbbbb-cccc-dddd-eeee-000000000004
visibility: hidden
---
"""
        temp_file = make_temp_file(suffix=".md", content=content)
        parsed_items = parse_single_file(temp_file)
        assert len(parsed_items) == 1

        save_course(parsed_items[0], mock_site_context, temp_file.parent)

        course = Course.objects.get(
            title="Hidden Imported Course", site=mock_site_context
        )
        assert course.visibility == "hidden"

    def test_import_without_visibility_defaults_to_published(
        self, mock_site_context, make_temp_file
    ):
        """A course file omitting visibility defaults to published via the schema default."""
        content = """---
content_type: COURSE
title: No Visibility Imported Course
uuid: bbbbbbbb-cccc-dddd-eeee-000000000002
---
"""
        temp_file = make_temp_file(suffix=".md", content=content)
        parsed_items = parse_single_file(temp_file)
        assert len(parsed_items) == 1

        save_course(parsed_items[0], mock_site_context, temp_file.parent)

        course = Course.objects.get(
            title="No Visibility Imported Course", site=mock_site_context
        )
        assert course.visibility == "published"

    def test_import_invalid_visibility_is_rejected(self, make_temp_file):
        """A course file with an invalid visibility value is rejected by the schema."""
        content = """---
content_type: COURSE
title: Bad Visibility Course
uuid: bbbbbbbb-cccc-dddd-eeee-000000000003
visibility: nonsense
---
"""
        temp_file = make_temp_file(suffix=".md", content=content)
        with pytest.raises(ValueError, match="visibility"):
            parse_single_file(temp_file)


# Tests for the Course.table_of_contents_in_development flag.


@pytest.mark.parametrize("visibility", ["published", "coming_soon", "hidden"])
def test_schema_flag_true_is_valid_for_every_visibility(visibility: str) -> None:
    """The flag composes freely with every visibility state."""
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "In Development",
            "visibility": visibility,
            "table_of_contents_in_development": True,
        }
    )
    assert schema.table_of_contents_in_development is True


def test_schema_flag_true_is_valid_with_default_visibility() -> None:
    """Omitting visibility defaults to published, which still accepts the flag.

    This is the application-gated case: applications are open while the
    course's contents are still being written.
    """
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Open For Applications",
            "access_config": {"access_type": "application_gated"},
            "table_of_contents_in_development": True,
        }
    )
    assert schema.visibility == "published"
    assert schema.table_of_contents_in_development is True


def test_schema_flag_defaults_to_false() -> None:
    """table_of_contents_in_development defaults to False when omitted."""
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Default Flag Course",
        }
    )
    assert schema.table_of_contents_in_development is False


# ---------------------------------------------------------------------------
# Django model field + schema<->model reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_content_save_persists_toc_in_development_flag(site, mock_site_context):
    """A published course carrying the flag saves without error.

    Visibility is omitted so it defaults to published -- the shape that used
    to be rejected at load time.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "in_development_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text(
            """---
content_type: COURSE
title: In Development Course
table_of_contents_in_development: true
uuid: 00000000-0000-0000-0000-000000000030
---

Body
"""
        )

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="In Development Course", site=site)
        assert course.table_of_contents_in_development is True


# Tests for Course.iso_estimated_duration() — ISO-8601 duration serialiser.
#
# TDD: written before the method is implemented.


@pytest.mark.django_db
def test_iso_estimated_duration_returns_empty_string_when_unset(mock_site_context):
    """iso_estimated_duration() returns '' when estimated_duration is None."""
    course = CourseFactory(estimated_duration=None)
    assert course.iso_estimated_duration() == ""


@pytest.mark.django_db
def test_iso_estimated_duration_returns_empty_string_for_zero(mock_site_context):
    """iso_estimated_duration() returns '' for a zero timedelta."""
    course = CourseFactory(estimated_duration=timedelta(0))
    assert course.iso_estimated_duration() == ""


@pytest.mark.django_db
def test_iso_estimated_duration_returns_empty_string_for_sub_minute(mock_site_context):
    """A non-zero duration under 30s rounds to 0 minutes and must return ''.

    Guards against emitting the malformed bare prefix "PT" (invalid ISO-8601),
    which would leak into the course JSON-LD timeRequired field.
    """
    course = CourseFactory(estimated_duration=timedelta(seconds=20))
    assert course.iso_estimated_duration() == ""


@pytest.mark.django_db
def test_iso_estimated_duration_returns_empty_string_for_thirty_seconds(
    mock_site_context,
):
    """30s rounds to 0 whole minutes (banker's rounding) and must return ''."""
    course = CourseFactory(estimated_duration=timedelta(seconds=30))
    assert course.iso_estimated_duration() == ""


@pytest.mark.django_db
def test_iso_estimated_duration_hours_only(mock_site_context):
    """iso_estimated_duration() returns 'PT2H' for exactly 2 hours."""
    course = CourseFactory(estimated_duration=timedelta(hours=2))
    assert course.iso_estimated_duration() == "PT2H"


@pytest.mark.django_db
def test_iso_estimated_duration_minutes_only(mock_site_context):
    """iso_estimated_duration() returns 'PT45M' for 45 minutes."""
    course = CourseFactory(estimated_duration=timedelta(minutes=45))
    assert course.iso_estimated_duration() == "PT45M"


@pytest.mark.django_db
def test_iso_estimated_duration_hours_and_minutes(mock_site_context):
    """iso_estimated_duration() returns 'PT1H30M' for 1 hour 30 minutes."""
    course = CourseFactory(estimated_duration=timedelta(hours=1, minutes=30))
    assert course.iso_estimated_duration() == "PT1H30M"


@pytest.mark.django_db
def test_iso_estimated_duration_large_duration(mock_site_context):
    """iso_estimated_duration() handles 3 hours 15 minutes correctly."""
    course = CourseFactory(estimated_duration=timedelta(hours=3, minutes=15))
    assert course.iso_estimated_duration() == "PT3H15M"
