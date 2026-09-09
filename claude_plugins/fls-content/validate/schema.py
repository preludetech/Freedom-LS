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

import re
from collections import Counter, defaultdict
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ContentType(StrEnum):
    """Content type enumeration."""

    TOPIC = "TOPIC"
    ACTIVITY = "ACTIVITY"
    FORM = "FORM"
    COURSE = "COURSE"
    COURSE_PART = "COURSE_PART"
    COURSE_CATEGORIES = "COURSE_CATEGORIES"
    FORM_PAGE = "FORM_PAGE"
    FORM_QUESTION = "FORM_QUESTION"
    FORM_CONTENT = "FORM_CONTENT"


# The section slugs the dashboard reserves for its built-in sections. A
# CourseCategory may not take one of these, because the slug names the
# section's query parameter and its wrapper id.
RESERVED_SECTION_SLUGS = frozenset(
    {"in-progress", "recommended", "available", "coming-soon", "history"}
)

# The character set Django's `validate_slug` accepts. Defined here rather
# than imported from Django so this module still imports with no Django
# installed. Always applied with `.fullmatch()`: `.match()`/`.search()`
# don't anchor the end, and would let something like "bad slug!" through.
SLUG_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


class QuestionType(StrEnum):
    """Question type enumeration."""

    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    FILE_UPLOAD = "file_upload"


class FormStrategy(StrEnum):
    """Form strategy enumeration."""

    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM"
    QUIZ = "QUIZ"
    UNSCORED = "UNSCORED"


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
    def _validate_access_config(self) -> "Course":
        """Patch 2: catch access_config mistakes offline.

        The real schema leaves access_config interpretation to the active
        COURSE_ACCESS_BACKEND. The standalone validator has no backend, so this
        catches author-time mistakes offline.

        Structural rule (always enforced): absent/empty config defaults to "free";
        only the `access_type` and `application_form` keys are permitted, and
        `application_form` must be a non-empty path string.

        Value rule (enforced only when the deployment vocabulary has been injected):
        `access_type` must be one of ALLOWED_ACCESS_TYPES. That set is owned by the
        repo's .fls-content.yaml `access_types` and injected by validate.py — it is
        never hard-coded here. While it is None (e.g. schema imported without
        validate.py), the value is not checked.

        Which access_type an application_form belongs with is deliberately not
        checked: the gating access type is named by the deployment's backend, which
        this validator has no view of. The deployment refuses the mismatch at load.
        """
        raw = self.access_config
        if not raw:
            return self

        allowed_keys = {"access_type", "application_form"}
        extra_keys = set(raw.keys()) - allowed_keys
        if extra_keys:
            raise ValueError(
                f"access_config has unknown key(s) in {self.file_path}: "
                f"{sorted(extra_keys)!r}. Allowed keys: {sorted(allowed_keys)!r}"
            )

        if "application_form" in raw:
            form_path = raw["application_form"]
            if not isinstance(form_path, str) or not form_path.strip():
                raise ValueError(
                    f"access_config has an invalid application_form="
                    f"{form_path!r} in {self.file_path}. Expected a path to a "
                    f"FORM file, relative to course.md."
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
        description=(
            "Question type (multiple_choice, checkboxes, short_text, long_text, "
            "number, file_upload)"
        ),
    )
    required: bool = Field(True, description="Whether the question is required")
    category: str | None = Field(None, description="Question category")
    options: list[QuestionOption] | None = Field(
        None, description="Options for multiple choice questions"
    )


# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry
