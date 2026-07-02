"""Tests for importing the visibility field on Course via the content pipeline."""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.management.commands.content_save import save_course
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.validate import parse_single_file


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
