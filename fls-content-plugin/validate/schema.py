# Bundled from freedom_ls/content_engine/schema.py — re-sync via /update_claude_plugin_fls_content
# Patches applied:
#   1. Course._validate_icon_fields: body replaced with `return self` to drop the deferred
#      Django/icon import (from django.core.exceptions and from freedom_ls...icon_validation).
#      Keep the method present so the model shape is unchanged.
#   2. Course.access_config validation. The real schema declares access_config as an opaque
#      field and leaves all interpretation to the active COURSE_ACCESS_BACKEND
#      (validate_course_config). The standalone validator has no backend, so
#      Course._validate_access_config below catches author-time mistakes (unknown keys,
#      unrecognised access_type) offline. The valid access-type vocabulary is
#      DEPLOYMENT-SPECIFIC and is NOT hard-coded here — exactly like admonition_types, it is
#      owned by the repo's .fls-content.yaml (authoritative) and injected by validate.py into
#      ALLOWED_ACCESS_TYPES before validation. This module owns no vocabulary: when nothing has
#      been injected (None) only the structural rule is enforced. Re-apply on every re-sync.
"""
Schema for yaml structures like this:
"""

from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContentType(StrEnum):
    """Content type enumeration."""

    TOPIC = "TOPIC"
    ACTIVITY = "ACTIVITY"
    FORM = "FORM"
    COURSE = "COURSE"
    COURSE_PART = "COURSE_PART"
    FORM_PAGE = "FORM_PAGE"
    FORM_QUESTION = "FORM_QUESTION"
    FORM_CONTENT = "FORM_CONTENT"


class QuestionType(StrEnum):
    """Question type enumeration."""

    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"


class FormStrategy(StrEnum):
    """Form strategy enumeration."""

    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM"
    QUIZ = "QUIZ"


class DifficultyLevel(StrEnum):
    """Course difficulty level enumeration (mirrors models.DifficultyLevel)."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ALL_LEVELS = "all_levels"


class BaseBaseContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] | None = Field(
        None, description="Optional metadata as key-value pairs"
    )
    tags: list[str] | None = Field(None, description="Optional list of tags")
    content_type: ContentType = Field(..., description="Type of content")
    file_path: Path = Field(..., description="Path to the content file")
    uuid: str | None = Field(None, description="Optional unique identifier")

    _registry: ClassVar[dict[ContentType, type["BaseBaseContentModel"]]] = {}

    def __init_subclass__(cls, content_type: ContentType | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if content_type is not None:
            BaseBaseContentModel._registry[content_type] = cls


class BaseContentModel(BaseBaseContentModel):
    title: str = Field(..., description="Title of the content item")
    subtitle: str | None = Field(None, description="Optional subtitle")
    description: str | None = Field(None, description="Optional description")

    category: str | None = Field(
        None, description="Optional category for this activity"
    )
    image: str | None = Field(None, description="Optional category for this activity")


class MarkdownContentModel(BaseModel):
    content: str | None = Field(None, description="Markdown content body")


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


# Patch 2: the access-type vocabulary is deployment-specific (it comes from the active
# COURSE_ACCESS_BACKEND) and is therefore NOT hard-coded here — the same way admonition_types
# are not hard-coded in this validator. validate.py injects the set at runtime from the repo's
# .fls-content.yaml `access_types` (authoritative). That config is required and read from the
# repo root; a missing/malformed file is a hard error, and a config with no `access_types` key
# uses a documented shipped base set. While this is None, _validate_access_config enforces only
# the structural rule (no value check). validate.py always injects a set before validating.
ALLOWED_ACCESS_TYPES: frozenset[str] | None = None


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
    def _validate_access_config(self) -> "Course":
        """Patch 2: catch access_config mistakes offline.

        The real schema leaves access_config interpretation to the active
        COURSE_ACCESS_BACKEND. The standalone validator has no backend, so this
        catches author-time mistakes offline.

        Structural rule (always enforced): absent/empty config defaults to "free";
        only the `access_type` key is permitted.

        Value rule (enforced only when the deployment vocabulary has been injected):
        `access_type` must be one of ALLOWED_ACCESS_TYPES. That set is owned by the
        repo's .fls-content.yaml `access_types` and injected by validate.py — it is
        never hard-coded here. While it is None (e.g. schema imported without
        validate.py), the value is not checked.
        """
        raw = self.access_config
        if not raw:
            return self

        allowed_keys = {"access_type"}
        extra_keys = set(raw.keys()) - allowed_keys
        if extra_keys:
            raise ValueError(
                f"access_config has unknown key(s) in {self.file_path}: "
                f"{sorted(extra_keys)!r}. Allowed keys: {sorted(allowed_keys)!r}"
            )

        access_type = raw.get("access_type", "free")
        if ALLOWED_ACCESS_TYPES is not None and access_type not in ALLOWED_ACCESS_TYPES:
            raise ValueError(
                f"access_config has invalid access_type={access_type!r} in "
                f"{self.file_path}. Valid values for this content repo: "
                f"{sorted(ALLOWED_ACCESS_TYPES)!r}. (The valid set is declared in "
                f".fls-content.yaml `access_types`, mirroring the deployment's "
                f"COURSE_ACCESS_BACKEND.)"
            )
        return self

    @model_validator(mode="after")
    def _validate_icon_fields(self) -> "Course":
        """Mirror the Django-side validation on the schema."""
        # Patch 1: stub — the original body imports Django and freedom_ls.content_engine.icon_validation,
        # which are unavailable in the standalone bundled validator. The icon field itself is still
        # declared above; structural validation (type, extra="forbid") still runs. Icon-semantic
        # validation (valid icon name against the active icon set) requires the FLS host and is
        # intentionally skipped here. Re-apply this stub on every D4 re-sync.
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


class Form(BaseContentModel, MarkdownContentModel, content_type=ContentType.FORM):
    """
    A form file will be in a directory containing all the different form pages. Ensure that there are form pages in the directory.

    A form page is a yaml file, the first object defined will have the FORM_PAGE content type
    """

    strategy: FormStrategy = Field(..., description="Strategy for form scoring")
    quiz_show_incorrect: bool | None = Field(
        None,
        description="Required if strategy is QUIZ. Should incorrect answers be shown after completion?",
    )
    quiz_pass_percentage: int | None = Field(
        None,
        description="Required if strategy is QUIZ. Percentage (0-100) required to pass the quiz",
    )

    submit_on_exit: bool = Field(
        False,
        description="If True, leaving the test mid-attempt finalises and scores it. Default False.",
    )

    @model_validator(mode="after")
    def validate_quiz_fields(self):
        """Validate that quiz fields are set correctly based on strategy."""
        if self.strategy == FormStrategy.QUIZ:
            # If QUIZ strategy, both fields must be provided
            if self.quiz_show_incorrect is None:
                raise ValueError(
                    f"quiz_show_incorrect is required when strategy is QUIZ (in {self.file_path})"
                )
            if self.quiz_pass_percentage is None:
                raise ValueError(
                    f"quiz_pass_percentage is required when strategy is QUIZ (in {self.file_path})"
                )
        else:
            # If not QUIZ strategy, these fields should not be set
            if self.quiz_show_incorrect is not None:
                raise ValueError(
                    f"quiz_show_incorrect should only be set when strategy is QUIZ (in {self.file_path})"
                )
            if self.quiz_pass_percentage is not None:
                raise ValueError(
                    f"quiz_pass_percentage should only be set when strategy is QUIZ (in {self.file_path})"
                )
        return self


class FormPage(BaseContentModel, content_type=ContentType.FORM_PAGE):
    """A page within a form."""

    def derive_content_type(self, data):
        if "content" in data:
            return ContentType.FORM_CONTENT
        if "question" in data:
            return ContentType.FORM_QUESTION


class QuestionOption(BaseModel):
    """A single option for a form question."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Display text for the option")
    value: int | str = Field(..., description="Value associated with this option")
    uuid: str | None = Field(None, description="Unique identifier for the option")

    correct: bool | None = Field(
        None, description="Used in Quizzes: Is this the correct answer?"
    )


class FormContent(BaseBaseContentModel, content_type=ContentType.FORM_CONTENT):
    content: str = Field(..., description="Text")


class FormQuestion(BaseBaseContentModel, content_type=ContentType.FORM_QUESTION):
    """
    A question in a form page.

    example:
    ```
    question: Can your child tolerate looking at and being near a variety of foods?
    type: multiple_choice
    required: True
    category: SEE - Visual Tolerance
    options:
        - text: Refuses to look at or be near unfamiliar foods
          value: 1
        - text: Will look at but shows distress with unfamiliar foods nearby
          value: 2
        - text: Tolerates looking at various foods but won't interact
          value: 3
        - text: Comfortable with various foods visually, some interaction
          value: 4
        - text: No visual food aversions; curious about all foods
          value: 5
    ```
    """

    question: str = Field(..., description="The question text")
    type: QuestionType = Field(
        ...,
        description="Question type (multiple_choice, checkboxes, short_text, long_text)",
    )
    required: bool = Field(True, description="Whether the question is required")
    category: str | None = Field(None, description="Question category")
    options: list[QuestionOption] | None = Field(
        None, description="Options for multiple choice questions"
    )


# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry
