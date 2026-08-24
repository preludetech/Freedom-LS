"""
Schema for yaml structures like this:
"""

from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from freedom_ls.content_base.schema import (
    BaseContentModel,
    ContentType,
    MarkdownContentModel,
)


class DifficultyLevel(StrEnum):
    """Course difficulty level enumeration (mirrors models.DifficultyLevel)."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ALL_LEVELS = "all_levels"


class CourseVisibility(StrEnum):
    """Course visibility lifecycle state (mirrors models.CourseVisibility)."""

    PUBLISHED = "published"
    COMING_SOON = "coming_soon"
    HIDDEN = "hidden"


class Topic(BaseContentModel, MarkdownContentModel, content_type=ContentType.TOPIC):
    pass


class Activity(
    BaseContentModel, MarkdownContentModel, content_type=ContentType.ACTIVITY
):
    level: int | None = Field(None, description="level 1 is easiest, 2 is harder, etc")


class Child(BaseModel):
    """A child content reference with optional overrides."""

    model_config = ConfigDict(extra="forbid")

    path: Path = Field(..., description="Path to the child content file")
    overrides: dict[str, Any] | None = Field(
        None, description="Optional overrides as key-value pairs"
    )


class Course(BaseContentModel, content_type=ContentType.COURSE):
    """
    You can think of this as a folder. It contains an ordered list of child content.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    children: list[Child] = Field(
        default_factory=list,
        description="List of child content references with optional overrides",
    )

    content: str | None = Field(None, description="Markdown content body")

    icon: str | None = Field(
        None,
        description=(
            "Semantic icon name from SEMANTIC_ICON_NAMES, or a literal glyph "
            "name (e.g. 'drone') resolved against the active icon set."
        ),
    )
    icon_fallback: str | None = Field(
        None,
        description=(
            "Optional explicit '<iconset>:<name>' reference (e.g. "
            "'phosphor:drone') used only when 'icon' fails to resolve in the "
            "active icon set."
        ),
    )

    learning_outcomes: list[str] = Field(
        default_factory=list,
        description="Ordered 'what you'll learn' outcomes",
    )
    difficulty: DifficultyLevel | None = Field(
        None,
        description="Course difficulty level",
    )
    visibility: CourseVisibility | None = Field(
        CourseVisibility.PUBLISHED,
        description="Course visibility lifecycle state",
    )
    table_of_contents_in_development: bool = Field(
        False,
        description="Hide the course's table-of-contents surfaces while it is being built.",
    )
    estimated_duration: timedelta | None = Field(
        None,
        description="Estimated time to complete",
    )
    # Any is correct here: access_config is an opaque, backend-owned JSON blob whose
    # keys are unknown to the schema layer — mirrors the existing `meta: dict[str, Any]`.
    access_config: dict[str, Any] | None = Field(
        None,
        description=(
            "Opaque per-course access configuration passed verbatim to the active "
            "course-access backend. The schema layer does not interpret its keys."
        ),
    )

    @model_validator(mode="after")
    def _validate_icon_fields(self) -> "Course":
        """Mirror the Django-side validation on the schema."""
        from django.core.exceptions import ValidationError

        from freedom_ls.content_engine.icon_validation import (
            validate_course_icon_fields,
        )

        try:
            validate_course_icon_fields(self.icon or "", self.icon_fallback or "")
        except ValidationError as exc:
            # Re-raise as a pydantic-friendly ValueError so the same content
            # validation tooling that handles other schema errors can pick
            # this up.
            raise ValueError(
                f"Invalid course icon fields in {self.file_path}: "
                f"{exc.message_dict if hasattr(exc, 'message_dict') else exc}"
            ) from exc
        return self

    @model_validator(mode="after")
    def _validate_toc_in_development(self) -> "Course":
        # A published course must always show its contents.
        if self.table_of_contents_in_development and (
            self.visibility == CourseVisibility.PUBLISHED
        ):
            raise ValueError(
                f"table_of_contents_in_development must be false for a published "
                f"course (in {self.file_path})"
            )
        return self


class CoursePart(BaseContentModel, content_type=ContentType.COURSE_PART):
    """
    A part of a course, this could represent a chapter or a similar. It may contain multiple topics and forms.
    """

    model_config = ConfigDict(extra="forbid")

    children: list[Child] = Field(
        default_factory=list,
        description="List of child content references with optional overrides",
    )

    # content: Optional[str] = Field(None, description="Markdown content body")
