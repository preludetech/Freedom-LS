"""Tests for new Course fields: learning_outcomes, difficulty, estimated_duration.

Stage A1: model field round-trip and display methods.
Stage A4: content schema (Pydantic) round-trip via save_with_uuid.
"""

from datetime import timedelta

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, DifficultyLevel

# ---------------------------------------------------------------------------
# A1 - Model field tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_has_learning_outcomes_field(mock_site_context):
    """Course.learning_outcomes stores and retrieves a list of strings."""
    outcomes = ["Learn A", "Learn B", "Learn C"]
    course = CourseFactory(learning_outcomes=outcomes)
    course.refresh_from_db()
    assert course.learning_outcomes == outcomes


@pytest.mark.django_db
def test_course_learning_outcomes_defaults_to_empty_list(mock_site_context):
    """Course.learning_outcomes defaults to an empty list when not supplied."""
    course = CourseFactory()
    course.refresh_from_db()
    assert course.learning_outcomes == []


@pytest.mark.django_db
def test_course_has_difficulty_field(mock_site_context):
    """Course.difficulty stores and retrieves a DifficultyLevel value."""
    course = CourseFactory(difficulty=DifficultyLevel.BEGINNER)
    course.refresh_from_db()
    assert course.difficulty == DifficultyLevel.BEGINNER


@pytest.mark.django_db
def test_course_difficulty_defaults_to_empty_string(mock_site_context):
    """Course.difficulty defaults to blank when not supplied."""
    course = CourseFactory()
    course.refresh_from_db()
    assert course.difficulty == ""


@pytest.mark.django_db
def test_course_has_estimated_duration_field(mock_site_context):
    """Course.estimated_duration stores and retrieves a timedelta."""
    course = CourseFactory(estimated_duration=timedelta(hours=2))
    course.refresh_from_db()
    assert course.estimated_duration == timedelta(hours=2)


@pytest.mark.django_db
def test_course_estimated_duration_defaults_to_none(mock_site_context):
    """Course.estimated_duration defaults to None when not supplied."""
    course = CourseFactory()
    course.refresh_from_db()
    assert course.estimated_duration is None


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
    from freedom_ls.content_engine.management.commands.content_save import save_course
    from freedom_ls.content_engine.validate import parse_single_file

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
    from freedom_ls.content_engine.management.commands.content_save import save_course
    from freedom_ls.content_engine.validate import parse_single_file

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
    from freedom_ls.content_engine.management.commands.content_save import save_course
    from freedom_ls.content_engine.validate import parse_single_file

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
    from freedom_ls.content_engine.management.commands.content_save import save_course
    from freedom_ls.content_engine.validate import parse_single_file

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
