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
    FORM = "FORM"
    COLLECTION = "COLLECTION"
    FORM_PAGE = "FORM_PAGE"
    FORM_QUESTION = "FORM_QUESTION"
    FORM_TEXT = "FORM_TEXT"


class QuestionType(str, Enum):
    """Question type enumeration."""
    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"


class FormStrategy(str, Enum):
    """Form strategy enumeration."""
    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM"
    





class BaseBaseContentModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    meta: Optional[dict[str, Any]] = Field(None, description="Optional metadata as key-value pairs")
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


class Topic(BaseContentModel, content_type=ContentType.TOPIC):
    """Schema for content items.
    title: Required
    subtitle: Optional
    meta: Optional. This is a collection of key value pairs where the values can have any type

    eg:
    ```
    title: Understanding Texture Tolerance in Children with Autism
    subtitle: Why Texture Matters and How It Affects Eating
    meta:
        id: SA1
    tags: optional list of strings
    content_type: enum. Can be TOPIC or FORM
    ```
    """
    pass
    


class ContentCollection(BaseContentModel, content_type=ContentType.COLLECTION):
    """
    You can think of this as a folder. It contains an ordered list of child content.

    the children element is either a single string, (a directory path) or a list of strings (a list of paths)

    """
    children: Union[str, list[str]] = Field(..., description="Single directory path or list of content paths") 





class Form(BaseContentModel, content_type=ContentType.FORM):
    """
    A form file will be in a directory containing all the different form pages. Ensure that there are form pages in the directory.

    A form page is a yaml file, the first object defined will have the FORM_PAGE content type
    """
    strategy: FormStrategy = Field(..., description="Strategy for form scoring")
    

class FormPage(BaseContentModel, content_type=ContentType.FORM_PAGE):
    """
    """
    def derive_content_type(self,data):
        if "text" in data: 
            return ContentType.FORM_TEXT 
        if "question" in data:
            return ContentType.FORM_QUESTION
    
class QuestionOption(BaseModel):
    """A single option for a form question."""
    model_config = ConfigDict(extra='forbid')

    text: str = Field(..., description="Display text for the option")
    value: Union[int, str] = Field(..., description="Value associated with this option")


class FormText(BaseBaseContentModel, content_type=ContentType.FORM_TEXT):
    text: str = Field(..., description="Text")
    
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
    type: QuestionType = Field(..., description="Question type (multiple_choice, checkboxes, short_text, long_text)")
    required: bool = Field(True, description="Whether the question is required")
    category: Optional[str] = Field(None, description="Question category")
    options: Optional[list[QuestionOption]] = Field(None, description="Options for multiple choice questions")

# SCHEMAS is automatically built via __init_subclass__
SCHEMAS = BaseContentModel._registry