from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from freedom_ls.content_base.schema import (
    BaseBaseContentModel,
    BaseContentModel,
    ContentType,
    MarkdownContentModel,
)


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
