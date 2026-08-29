from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    image: str | None = Field(None, description="Optional category for this activity")


class MarkdownContentModel(BaseModel):
    content: str | None = Field(None, description="Markdown content body")


# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry
