"""Tests for load-time validation via COURSE_ACCESS_CONFIG_VALIDATOR hook (Task A.7).

TDD: tests written first (red), then implementation added (green).

These tests call save_course() directly with a mock pydantic schema item
to verify that the hook fires and validates/normalises access_config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.test import override_settings

DEFAULT_BACKEND = "freedom_ls.course_access.backends.DefaultCourseAccessBackend"
DEFAULT_VALIDATOR = "freedom_ls.course_access.loader.validate_course_access_config"


@pytest.fixture(autouse=True)
def _clear_backend_cache():
    from freedom_ls.course_access.loader import get_course_access_backend

    get_course_access_backend.cache_clear()
    yield
    get_course_access_backend.cache_clear()


def _make_fake_item(tmp_path: Path, slug: str, access_config: dict | None = None):
    """Build a minimal Pydantic-like item suitable for save_course()."""
    # Parse a real pydantic schema item from a dict so save_with_uuid's model_dump works.
    import uuid as _uuid

    from freedom_ls.content_engine.schema import Course as CourseSchema

    uid = str(_uuid.uuid4())
    file_path = tmp_path / f"{slug}.md"
    file_path.touch()

    # Use model_validate (from dict) rather than direct constructor to avoid mypy
    # false-positive about fields with None defaults being "required".
    return CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "title": slug,
            "uuid": uid,
            "file_path": str(file_path),
            "access_config": access_config,
        }
    )


@pytest.mark.django_db
class TestSaveCourseLoadTimeValidation:
    """Task A.7 — save_course normalises and validates access_config via the hook."""

    @override_settings(
        COURSE_ACCESS_BACKEND=DEFAULT_BACKEND,
        COURSE_ACCESS_CONFIG_VALIDATOR=DEFAULT_VALIDATOR,
    )
    def test_unknown_access_config_key_raises_value_error(
        self, mock_site_context, tmp_path
    ):
        from freedom_ls.content_engine.management.commands.content_save import (
            save_course,
        )

        item = _make_fake_item(tmp_path, "key-error-course", {"unknown_key": True})
        site = mock_site_context
        with pytest.raises(ValueError, match="unknown key"):
            save_course(item, site, tmp_path)

    @override_settings(
        COURSE_ACCESS_BACKEND=DEFAULT_BACKEND,
        COURSE_ACCESS_CONFIG_VALIDATOR=DEFAULT_VALIDATOR,
    )
    def test_unknown_access_config_key_includes_file_path(
        self, mock_site_context, tmp_path
    ):
        from freedom_ls.content_engine.management.commands.content_save import (
            save_course,
        )

        item = _make_fake_item(tmp_path, "fp-course", {"unknown_key": True})
        site = mock_site_context
        with pytest.raises(ValueError, match="fp-course"):
            save_course(item, site, tmp_path)

    @override_settings(
        COURSE_ACCESS_BACKEND=DEFAULT_BACKEND,
        COURSE_ACCESS_CONFIG_VALIDATOR=None,
    )
    def test_unset_validator_stores_verbatim_no_validation(
        self, mock_site_context, tmp_path
    ):
        """When COURSE_ACCESS_CONFIG_VALIDATOR is unset, access_config is stored verbatim."""
        from freedom_ls.content_engine.management.commands.content_save import (
            save_course,
        )
        from freedom_ls.content_engine.models import Course

        item = _make_fake_item(
            tmp_path,
            "verbatim-course",
            {"access_type": "application_gated"},
        )
        site = mock_site_context
        # No validator → no error, stored verbatim
        save_course(item, site, tmp_path)
        course = Course.objects.get(slug="verbatim-course")
        assert course.access_config == {"access_type": "application_gated"}
