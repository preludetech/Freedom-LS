"""
Schema for yaml structures like this:
"""

import re
from collections import Counter, defaultdict
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from freedom_ls.content_base.schema import (
    BaseBaseContentModel,
    BaseContentModel,
    ContentType,
    MarkdownContentModel,
)

# The section slugs the dashboard reserves for its built-in sections. A
# CourseCategory may not take one of these, because the slug names the
# section's query parameter and its wrapper id. The dashboard mirrors this
# set as `learner_interface.dashboard_sections.BuiltInSection` and a test
# keeps the two equal; the offline validator copies it and runs with no
# Django -- so it stays a plain module constant rather than a Django choice.
RESERVED_SECTION_SLUGS = frozenset(
    {"in-progress", "recommended", "available", "coming-soon", "history"}
)

# The character set Django's `validate_slug` accepts. Defined here rather
# than imported from Django so this module still imports with no Django
# installed, which the offline validator relies on. Always applied with
# `.fullmatch()`: `.match()`/`.search()` don't anchor the end, and would let
# something like "bad slug!" through.
SLUG_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


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


class CourseCategoryEntry(BaseModel):
    """One row of `course_categories.yaml`."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    description: str | None = None
    show_on_dashboard: bool = True
    uuid: str | None = None


class CourseCategories(
    BaseBaseContentModel, content_type=ContentType.COURSE_CATEGORIES
):
    """The single, site-wide declaration of every `CourseCategory`, in display order."""

    categories: list[CourseCategoryEntry]

    def derive_content_type(self, data):
        # A second `---` document in course_categories.yaml omits
        # content_type, and parse_yaml_file falls back to this method on the
        # first document. Without it, that fallback raises AttributeError
        # before the duplicate-declaration check is ever reached.
        return ContentType.COURSE_CATEGORIES

    @model_validator(mode="after")
    def _validate_entries(self) -> "CourseCategories":
        errors: list[str] = []

        slug_counts = Counter(entry.slug for entry in self.categories)
        for slug, count in slug_counts.items():
            if count > 1:
                errors.append(
                    f"Duplicate category slug '{slug}' in {self.file_path}: "
                    "every entry needs its own slug."
                )

        uuid_slugs: dict[str, list[str]] = defaultdict(list)
        for entry in self.categories:
            if entry.uuid is not None:
                uuid_slugs[entry.uuid].append(entry.slug)
        for entry_uuid, slugs in uuid_slugs.items():
            if len(slugs) > 1:
                errors.append(
                    f"Duplicate category uuid '{entry_uuid}' in {self.file_path}, "
                    f"shared by slugs {slugs}: an entry copied without clearing "
                    "its uuid loads as one row overwriting the other."
                )

        for entry in self.categories:
            if not SLUG_PATTERN.fullmatch(entry.slug):
                errors.append(
                    f"Invalid category slug '{entry.slug}' in {self.file_path}: "
                    "a slug may only contain letters, digits, hyphens and underscores."
                )
            if entry.slug in RESERVED_SECTION_SLUGS:
                errors.append(
                    f"Category slug '{entry.slug}' in {self.file_path} is reserved "
                    f"for the dashboard's built-in sections: {sorted(RESERVED_SECTION_SLUGS)}."
                )

        if errors:
            raise ValueError("\n".join(errors))
        return self


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

    categories: list[str] = Field(
        default_factory=list,
        description="Slugs of the CourseCategory rows this course belongs to",
    )
    dashboard_category: str | None = Field(
        None,
        description=(
            "Slug of the one category the dashboard places this course in. "
            "Required when categories has more than one entry."
        ),
    )

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

    application_form: Path | None = Field(
        None,
        description=(
            "Path to the FORM file this course's applicants fill in, relative "
            "to course.md"
        ),
    )

    @field_validator("category", mode="before")
    @classmethod
    def _category_is_retired(cls, value: str | None) -> str | None:
        # A before-validator on an inherited field only runs when the key is
        # present in the input, so a file that never wrote `category:` is
        # untouched -- only one that still carries the retired key fails.
        raise ValueError(
            "'category' is no longer a course field. Use 'categories' (a list "
            "of category slugs), and 'dashboard_category' when there is more "
            "than one."
        )

    def resolve_dashboard_category(self) -> str | None:
        """The slug the dashboard should place this course under, or None.

        An explicit `dashboard_category` wins. Otherwise a single entry in
        `categories` resolves as the shorthand; two or more with no explicit
        choice, or none at all, both resolve to None. The validator (step 4)
        is what tells those two None cases apart and reports the former --
        this method's caller, the loader, doesn't need to.
        """
        if self.dashboard_category is not None:
            return self.dashboard_category
        if len(self.categories) == 1:
            return self.categories[0]
        return None

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
