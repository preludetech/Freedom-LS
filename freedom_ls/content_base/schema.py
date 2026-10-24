import re
from datetime import date, time
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContentType(StrEnum):
    """Content type enumeration."""

    TOPIC = "TOPIC"
    ACTIVITY = "ACTIVITY"
    ARTICLE = "ARTICLE"
    FORM = "FORM"
    COURSE = "COURSE"
    COURSE_PART = "COURSE_PART"
    COURSE_CATEGORIES = "COURSE_CATEGORIES"
    FORM_PAGE = "FORM_PAGE"
    FORM_QUESTION = "FORM_QUESTION"
    FORM_CONTENT = "FORM_CONTENT"


class BaseBaseContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] | None = Field(
        None, description="Optional metadata as key-value pairs"
    )
    tags: list[str] = Field(default_factory=list, description="Optional list of tags")
    content_type: ContentType = Field(..., description="Type of content")
    file_path: Path = Field(..., description="Path to the content file")
    uuid: str | None = Field(None, description="Optional unique identifier")

    _registry: ClassVar[dict[ContentType, type["BaseBaseContentModel"]]] = {}

    @field_validator("tags", mode="before")
    @classmethod
    def _null_tags_mean_no_tags(cls, value: list[str] | None) -> list[str]:
        """A bare `tags:` key in front matter parses as None, not a list."""
        return [] if value is None else value

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
    image: str | None = Field(
        None, description="Path to the image, relative to this file"
    )


class MarkdownContentModel(BaseModel):
    content: str | None = Field(None, description="Markdown content body")


_DUE_TIME = re.compile(r"\d{2}:\d{2}")


class DueDateFields(BaseModel):
    """The deadline a child file carries: a fixed date, or days after the learner's registration
    date, either with an optional time of day. Pure pydantic so the offline validator shares it."""

    due_date: date | None = Field(None, description="Fixed due date (YAML date)")
    due_time: time | None = Field(None, description='Time of day, 24-hour "HH:MM"')
    due_days_after_registration: int | None = Field(
        None, ge=0, strict=True, description="Days after the registration date"
    )

    @field_validator("due_date", mode="before")
    @classmethod
    def _due_date_is_a_date(cls, value: object) -> object:
        # PyYAML parses `2026-03-14 00:00:00` as a datetime and pydantic's lax date would
        # accept it; a due date never carries a time of its own, that is what due_time is for.
        if value is not None and type(value) is not date:
            raise ValueError(
                "due_date must be a date such as 2026-03-14, without a time"
            )
        return value

    @field_validator("due_time", mode="before")
    @classmethod
    def _due_time_is_quoted(cls, value: object) -> object:
        # An unquoted 17:00 is a YAML sexagesimal integer (1020), which pydantic would read
        # as seconds after midnight. Only the quoted string says what the author meant.
        if value is not None and not (
            isinstance(value, str) and _DUE_TIME.fullmatch(value)
        ):
            raise ValueError('due_time must be a quoted 24-hour time such as "17:00"')
        return value

    @model_validator(mode="after")
    def _one_kind_of_due_date(self) -> "DueDateFields":
        file_path = getattr(self, "file_path", None)
        if self.due_date is not None and self.due_days_after_registration is not None:
            raise ValueError(
                f"{file_path}: set due_date or due_days_after_registration, not both"
            )
        if (
            self.due_time is not None
            and self.due_date is None
            and self.due_days_after_registration is None
        ):
            raise ValueError(
                f"{file_path}: due_time needs due_date or due_days_after_registration"
            )
        return self


DUE_DATE_FIELD_NAMES = frozenset(DueDateFields.model_fields)


# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry
