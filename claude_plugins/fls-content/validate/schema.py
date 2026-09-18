# Bundled from freedom_ls/content_engine/schema.py — re-sync via /update_claude_plugin_fls_content
# NOTE: the form classes below (QuestionType, FormStrategy, Form, FormPage, QuestionOption,
#   FormContent, FormQuestion) mirror freedom_ls/form_engine/schema.py, NOT content_engine,
#   and the bounds helpers above FormQuestion mirror freedom_ls/form_engine/typed_answers.py.
#   This file bundles FOUR sources: content_base/schema.py, content_engine/schema.py,
#   form_engine/schema.py and form_engine/typed_answers.py. Check every one on re-sync — a
#   form_engine-only change still makes this file stale, and a stale QuestionType or
#   FormQuestion rejects valid content (extra="forbid").
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
#   3. FormQuestion.validate_bounds, and the typed_answers mirror above FormQuestion that it
#      calls. The rule is freedom_ls/form_engine/typed_answers.question_bounds_error: pure
#      stdlib apart from django.utils.dateparse's parse_date/parse_time, which are transcribed
#      here. That transcription has to stay exact — a stricter parser (plain
#      date.fromisoformat) rejects bounds that content_save accepts, e.g. `2010-1-1`. Without
#      this patch the validator PASSES content that content_save rejects. Re-apply on every
#      re-sync, and re-check the transcription when Django's dateparse changes.
#   4. Course.price and its rules. KIND_FIELDS and price_errors are a fifth bundled source --
#      freedom_ls/content_engine/prices.py, not content_engine/schema.py -- copied verbatim
#      apart from importing list_currencies/get_currency_precision from babel.numbers
#      directly instead of through that module. _default_currency() is stubbed to always
#      return "": the standalone validator has no DEFAULT_CURRENCY setting, so an absent
#      `currency:` skips only the decimal-place half of the rule, same as content_engine's own
#      copy when that setting is unset. Re-apply on every re-sync.
"""
Schema for yaml structures like this:
"""

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date, time, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

from babel.numbers import get_currency_precision, list_currencies
from pydantic import (
    BaseModel,
    BeforeValidator,
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
    DATE = "date"
    TIME = "time"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    DROPDOWN = "dropdown"


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


# Patch 4: bundled verbatim from freedom_ls/content_engine/prices.py (kind -> the fields it
# requires, and the fields it may also carry).
KIND_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "fixed": (frozenset({"amount"}), frozenset({"currency", "tax_note"})),
    "range": (
        frozenset({"low_amount", "high_amount"}),
        frozenset({"currency", "tax_note"}),
    ),
    "discounted": (
        frozenset({"amount", "sale_amount"}),
        frozenset({"sale_ends_on", "currency", "tax_note"}),
    ),
    "on_request": (frozenset(), frozenset()),
}

_PRICE_AMOUNT_FIELDS = ("amount", "sale_amount", "low_amount", "high_amount")


def price_errors(
    kind: str,
    *,
    amount: Decimal | None = None,
    sale_amount: Decimal | None = None,
    sale_ends_on: date | None = None,
    low_amount: Decimal | None = None,
    high_amount: Decimal | None = None,
    currency: str = "",
    tax_note: str = "",
) -> dict[str, str]:
    """Patch 4: bundled verbatim from freedom_ls/content_engine/prices.py.

    Every price rule, keyed by the author-facing field name it belongs to.
    Currency is never required here -- each caller resolves a default
    currency before calling, and reports a still-missing currency itself.
    """
    values: dict[str, object] = {
        "amount": amount,
        "sale_amount": sale_amount,
        "sale_ends_on": sale_ends_on,
        "low_amount": low_amount,
        "high_amount": high_amount,
        "currency": currency,
        "tax_note": tax_note,
    }
    required, optional = KIND_FIELDS[kind]
    allowed = required | optional
    errors: dict[str, str] = {}

    for field in required:
        if values[field] is None:
            errors.setdefault(field, f"{field} is required for a {kind} price")

    for field, value in values.items():
        if field in allowed or value in (None, ""):
            continue
        errors.setdefault(field, f"{field} is not used by a {kind} price")

    currency_valid = bool(currency) and currency in list_currencies()
    if currency and not currency_valid:
        errors.setdefault(
            "currency", f"{currency!r} is not a currency code Babel recognises."
        )

    # Collect the amounts that pass finiteness and positivity, so the
    # ordering rules below never compare against a NaN (which raises) or an
    # amount already reported invalid.
    finite_amounts: dict[str, Decimal] = {}
    for field in _PRICE_AMOUNT_FIELDS:
        value = values[field]
        if not isinstance(value, Decimal):
            continue
        if not value.is_finite():
            errors.setdefault(field, f"{field} must be a finite number.")
            continue
        if value <= 0:
            errors.setdefault(field, f"{field} must be greater than zero.")
            continue
        finite_amounts[field] = value
        if currency_valid and decimal_places_used(value) > get_currency_precision(
            currency
        ):
            errors.setdefault(
                field, f"{field} has more decimal places than {currency} allows."
            )

    if (
        "sale_amount" in finite_amounts
        and "amount" in finite_amounts
        and finite_amounts["sale_amount"] >= finite_amounts["amount"]
    ):
        errors.setdefault("sale_amount", "sale_amount must be less than amount.")
    if (
        "low_amount" in finite_amounts
        and "high_amount" in finite_amounts
        and finite_amounts["low_amount"] >= finite_amounts["high_amount"]
    ):
        errors.setdefault("high_amount", "high_amount must be greater than low_amount.")

    return errors


def _require_quoted_amount(value: object) -> object:
    """Refuse a bare YAML number, so a price amount is never read through float."""
    if not isinstance(value, str):
        raise ValueError('write amounts as quoted strings, e.g. "1499.00"')
    return value


Amount = Annotated[Decimal, BeforeValidator(_require_quoted_amount)]


class FixedPrice(BaseModel):
    """A single amount. `kind: "fixed"`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["fixed"]
    amount: Amount
    currency: str | None = None
    tax_note: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def _validate(self) -> "FixedPrice":
        _validate_price(self)
        return self


class RangePrice(BaseModel):
    """A low-high span, with no single amount. `kind: "range"`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["range"]
    low_amount: Amount
    high_amount: Amount
    currency: str | None = None
    tax_note: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def _validate(self) -> "RangePrice":
        _validate_price(self)
        return self


class DiscountedPrice(BaseModel):
    """An original amount and a sale amount, with an optional sale end date.

    `kind: "discounted"`.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["discounted"]
    amount: Amount
    sale_amount: Amount
    sale_ends_on: date | None = None
    currency: str | None = None
    tax_note: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def _validate(self) -> "DiscountedPrice":
        _validate_price(self)
        return self


class OnRequestPrice(BaseModel):
    """No amount is published; a visitor is told to ask. `kind: "on_request"`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["on_request"]


def _default_currency() -> str:
    """Patch 4: stubbed -- the standalone validator has no DEFAULT_CURRENCY setting.

    An absent `currency:` therefore always skips the decimal-place half of
    `price_errors`, the same as content_engine's own copy when that setting
    is unset.
    """
    return ""


def _validate_price(price: "FixedPrice | RangePrice | DiscountedPrice") -> None:
    """Run the shared price rules against one submodel's own fields."""
    fields = price.model_dump(exclude_none=True)
    if "currency" not in fields:
        fields["currency"] = _default_currency()
    errors = price_errors(**fields)
    if errors:
        raise ValueError(
            "; ".join(f"{field}: {message}" for field, message in errors.items())
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
        description=(
            "Hide the course's table-of-contents surfaces while it is being "
            "built. Independent of visibility: a published course open for "
            "applications may still be under construction."
        ),
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
    price: FixedPrice | RangePrice | DiscountedPrice | OnRequestPrice | None = Field(
        None, discriminator="kind", description="What the course costs. Display only."
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


# ---------------------------------------------------------------------------
# Hand-ported mirror of freedom_ls/form_engine/typed_answers.py.
#
# Not a bundled copy of a schema module like the rest of this file. The rule below is
# `question_bounds_error`, which lives in typed_answers.py and is shared by the pydantic
# schema and `FormQuestion.clean()`. Without it this validator passes content that
# content_save rejects: decimal_places on a short_text question, an unparseable date
# bound, min/max on a checkboxes question.
#
# `parsed_date` down to `question_bounds_error` are a verbatim copy of typed_answers.py
# — diff them line for line on re-sync. Only `parse_date` and `parse_time` are written
# here; the originals are django.utils.dateparse's, and this file imports no Django.
# ---------------------------------------------------------------------------

# Django 6.0 `dateparse` transcribed, quirks included. `date.fromisoformat` alone would
# reject the non-zero-padded `2010-1-1` that content_save accepts, so this validator
# would fail content that saves cleanly — the exact bug class the bundle exists to
# avoid. The permissive regex fallback is what buys that back. Two behaviours the
# callers below depend on: a malformed string returns None, and a well-formed but
# impossible date like `2025-02-30` raises ValueError. Written out positionally rather
# than Django's `**kw` splat, which mypy rejects; the results are identical.
#
# Both stand-ins delegate to `fromisoformat`, whose accepted grammar widened in Python
# 3.11. This file already requires 3.11+ (StrEnum), so that is not a new constraint —
# but it is now a semantic one rather than a syntactic one.
_DATE_RE = re.compile(r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})$")

_TIME_RE = re.compile(
    r"(?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
    r"(?::(?P<second>\d{1,2})(?:[.,](?P<microsecond>\d{1,6})\d{0,6})?)?$"
)


def parse_date(value: str) -> date | None:
    """Stand-in for `django.utils.dateparse.parse_date`."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        match = _DATE_RE.match(value)
        if match is None:
            return None
        return date(int(match["year"]), int(match["month"]), int(match["day"]))


def parse_time(value: str) -> time | None:
    """Stand-in for `django.utils.dateparse.parse_time`.

    An aware time is never useful here, so any offset `fromisoformat` picked up is
    dropped, exactly as the Django original does.
    """
    try:
        return time.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        match = _TIME_RE.match(value)
        if match is None:
            return None
        microsecond = match["microsecond"]
        return time(
            int(match["hour"]),
            int(match["minute"]),
            int(match["second"] or 0),
            int(microsecond.ljust(6, "0")) if microsecond else 0,
        )


def parsed_date(text: str) -> date | None:
    """`text` as a date, or None when it does not parse.

    `dateparse.parse_date` returns None for a malformed string like "banana"
    but raises `ValueError` for a well-formed, impossible one like
    "2025-02-30". Catching it here means both failures reach the same `None`
    branch in every caller.
    """
    try:
        return parse_date(text)
    except ValueError:
        return None


def parsed_time(text: str) -> time | None:
    """`text` as a time, or None when it does not parse. See `parsed_date`."""
    try:
        return parse_time(text)
    except ValueError:
        return None


# HTML's "valid floating-point number" grammar, so the server accepts exactly
# what `<input type="number">` submits and no more. `int()` takes `1_0` and
# surrounding whitespace; `Decimal()` takes those plus `nan` and `Infinity`.
# None of them can be typed into a number input, so none may reach a stored
# answer either.
_NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")


def parsed_number(text: str) -> Decimal | None:
    """`text` as a number, or None when it does not parse."""
    if not _NUMBER.fullmatch(text):
        return None
    return Decimal(text)


def decimal_places_used(value: Decimal) -> int:
    """How many decimal places `value` is written to.

    Normalised first, so `7.50` counts as one place rather than two -- it is
    the same number as `7.5`, and counting the written zero would reject a
    value the question's own limit allows.
    """
    exponent = value.normalize().as_tuple().exponent
    # A non-integer exponent is NaN or Infinity, which `parsed_number` refuses.
    if not isinstance(exponent, int):
        return 0
    return max(0, -exponent)


# A time bound has to be written HH:MM, with seconds optional. Anything else
# that `parse_time` happens to accept — a bare "1020" from an unquoted YAML
# time — means a different time than the author wrote.
_TIME_BOUND = re.compile(r"\d{1,2}:\d{2}(:\d{2})?")


def question_bounds_error(
    question_type: str, min_text: str, max_text: str, decimal_places: int
) -> str | None:
    """Why this question's `min`, `max` and `decimal_places` do not go together.

    Shared by the pydantic schema, which judges an authored content file, and
    `FormQuestion.clean()`, which judges the admin. A bound set by hand is then
    held to the same rule as one written in YAML, and neither route can leave
    an unparseable bound sitting inert in the page's HTML.
    """
    if decimal_places and question_type != QuestionType.NUMBER:
        return f"decimal_places is only valid on number questions, not {question_type}"

    if not min_text and not max_text:
        return None

    parsers: dict[str, Callable[[str], date | time | Decimal | None]] = {
        QuestionType.DATE: parsed_date,
        QuestionType.TIME: parsed_time,
        QuestionType.NUMBER: parsed_number,
    }
    parse = parsers.get(question_type)
    if parse is None:
        return (
            f"min/max are only valid on date, time or number questions, "
            f"not {question_type}"
        )

    for name, bound in (("min", min_text), ("max", max_text)):
        if not bound:
            continue
        value = parse(bound)
        if value is None:
            return f'{name} "{bound}" is not a valid {question_type}'
        if question_type == QuestionType.TIME and not _TIME_BOUND.fullmatch(bound):
            return (
                f'{name} "{bound}" is not written as HH:MM — quote it in the '
                f"YAML, or it is read as a number"
            )
        if isinstance(value, Decimal) and decimal_places_used(value) > decimal_places:
            return f'{name} "{bound}" has more decimal places than this question allows'
    return None


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
            "number, file_upload, date, time, email, url, phone, dropdown)"
        ),
    )
    required: bool = Field(True, description="Whether the question is required")
    category: str | None = Field(None, description="Question category")
    options: list[QuestionOption] | None = Field(
        None, description="Options for multiple choice questions"
    )

    min: str = Field(
        "",
        description=(
            "Inclusive lower bound for a date, time or number question "
            "(YYYY-MM-DD, HH:MM, or a plain number)"
        ),
    )
    max: str = Field(
        "",
        description=(
            "Inclusive upper bound for a date, time or number question "
            "(YYYY-MM-DD, HH:MM, or a plain number)"
        ),
    )
    decimal_places: int = Field(
        0,
        ge=0,
        description=(
            "How many decimal places a number answer may be written to. "
            "0, the default, is whole numbers only"
        ),
    )

    @field_validator("min", "max", mode="before")
    @classmethod
    def _coerce_bound_to_str(cls, value: object) -> str:
        """`yaml.safe_load` resolves an unquoted `min: 0` to an int and an
        unquoted `min: 1930-01-01` to a `datetime.date`. Both must arrive as
        str: the model field is a `CharField`, and `extra="forbid"` means the
        two sides have to line up exactly.
        """
        if value is None:
            return ""
        return str(value)

    @model_validator(mode="after")
    def validate_bounds(self) -> "FormQuestion":
        """`min`, `max` and `decimal_places` only mean anything on the types
        that have an order, and only when they parse as that type.

        The rule itself lives in `typed_answers.question_bounds_error`, shared
        with `FormQuestion.clean()`, so an authoring mistake is judged the same
        way wherever it is made. What this validator adds is the file name: an
        author finds out at `content_save`, with the file called out, rather
        than leaving a respondent to discover it.
        """
        error = question_bounds_error(
            self.type, self.min, self.max, self.decimal_places
        )
        if error is not None:
            raise ValueError(f"{error} (in {self.file_path})")
        return self


# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry
