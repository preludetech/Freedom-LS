"""
Schema for yaml structures like this:
"""

from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ContentType(str, Enum):
    """Content type enumeration."""

    TOPIC = "TOPIC"
    ACTIVITY = "ACTIVITY"
    FORM = "FORM"
    COURSE = "COURSE"
    FORM_PAGE = "FORM_PAGE"
    FORM_QUESTION = "FORM_QUESTION"
    FORM_CONTENT = "FORM_CONTENT"


class QuestionType(str, Enum):
    """Question type enumeration."""

    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"


class FormStrategy(str, Enum):
    """Form strategy enumeration."""

    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM"
    QUIZ = "QUIZ"


class BaseBaseContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata as key-value pairs"
    )
    tags: Optional[list[str]] = Field(None, description="Optional list of tags")
    content_type: ContentType = Field(..., description="Type of content")
    file_path: Path = Field(..., description="Path to the content file")
    uuid: Optional[str] = Field(None, description="Optional unique identifier")

    _registry: ClassVar[dict[ContentType, type["BaseContentModel"]]] = {}

    def __init_subclass__(cls, content_type: Optional[ContentType] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if content_type is not None:
            BaseBaseContentModel._registry[content_type] = cls


class BaseContentModel(BaseBaseContentModel):
    title: str = Field(..., description="Title of the content item")
    subtitle: Optional[str] = Field(None, description="Optional subtitle")
    description: Optional[str] = Field(None, description="Optional description")

    category: Optional[str] = Field(
        None, description="Optional category for this activity"
    )
    image: Optional[str] = Field(
        None, description="Optional category for this activity"
    )


class MarkdownContentModel(BaseModel):
    content: Optional[str] = Field(None, description="Markdown content body")


class Topic(BaseContentModel, MarkdownContentModel, content_type=ContentType.TOPIC):
    pass


class Activity(
    BaseContentModel, MarkdownContentModel, content_type=ContentType.ACTIVITY
):
    level: Optional[int] = Field(
        None, description="level 1 is easiest, 2 is harder, etc"
    )


class Child(BaseModel):
    """A child content reference with optional overrides."""

    model_config = ConfigDict(extra="forbid")

    path: Path = Field(..., description="Path to the child content file")
    overrides: Optional[dict[str, Any]] = Field(
        None, description="Optional overrides as key-value pairs"
    )


class Course(BaseContentModel, content_type=ContentType.COURSE):
    """
    You can think of this as a folder. It contains an ordered list of child content.
    """

    model_config = ConfigDict(extra="forbid")

    children: list[Child] = Field(
        default_factory=list,
        description="List of child content references with optional overrides",
    )

    content: Optional[str] = Field(None, description="Markdown content body")


class Form(BaseContentModel, MarkdownContentModel, content_type=ContentType.FORM):
    """
    A form file will be in a directory containing all the different form pages. Ensure that there are form pages in the directory.

    A form page is a yaml file, the first object defined will have the FORM_PAGE content type
    """

    strategy: FormStrategy = Field(..., description="Strategy for form scoring")


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
    value: Union[int, str] = Field(..., description="Value associated with this option")
    uuid: Optional[str] = Field(None, description="Unique identifier for the option")


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
    category: Optional[str] = Field(None, description="Question category")
    options: Optional[list[QuestionOption]] = Field(
        None, description="Options for multiple choice questions"
    )


# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry
