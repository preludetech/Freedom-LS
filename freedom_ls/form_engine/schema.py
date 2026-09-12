import re
from collections.abc import Callable
from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from freedom_ls.content_base.schema import (
    BaseBaseContentModel,
    BaseContentModel,
    ContentType,
    MarkdownContentModel,
)
from freedom_ls.form_engine.typed_answers import parsed_date, parsed_number, parsed_time

# A time bound has to be written HH:MM. Anything else that `parse_time`
# happens to accept — a bare "1020" from an unquoted YAML time — means a
# different time than the author wrote.
_TIME_BOUND = re.compile(r"\d{1,2}:\d{2}")


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
        """`min`/`max` only mean anything on a type with an order, and only
        when they parse as that type. Reusing `typed_answers`'s own parsers
        is what makes this validator agree with the check a submitted answer
        gets at runtime.

        This is also what catches a time bound an author left unquoted in
        YAML, which needs more than a parse check to spot. YAML 1.1 reads
        `17:00` as the base-60 integer 1020, and `parse_time` accepts the
        resulting "1020" as ten past ten — so an unquoted bound does not fail
        to parse, it parses as a different time than the author wrote. The
        `HH:MM` shape check below is what refuses it, at `content_save` and
        naming the file, instead of quietly enforcing the wrong hour on every
        respondent.
        """
        if not self.min and not self.max:
            return self
        parsers: dict[QuestionType, Callable[[str], date | time | int | None]] = {
            QuestionType.DATE: parsed_date,
            QuestionType.TIME: parsed_time,
            QuestionType.NUMBER: parsed_number,
        }
        parse = parsers.get(self.type)
        if parse is None:
            raise ValueError(
                f"min/max are only valid on date, time or number questions, "
                f"not {self.type} (in {self.file_path})"
            )
        for name, bound in (("min", self.min), ("max", self.max)):
            if not bound:
                continue
            if parse(bound) is None:
                raise ValueError(
                    f'{name} "{bound}" is not a valid {self.type} (in {self.file_path})'
                )
            if self.type == QuestionType.TIME and not _TIME_BOUND.fullmatch(bound):
                raise ValueError(
                    f'{name} "{bound}" is not written as HH:MM — quote it in the '
                    f"YAML, or it is read as a number (in {self.file_path})"
                )
        return self
