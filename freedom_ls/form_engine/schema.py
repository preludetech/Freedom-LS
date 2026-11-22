from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from freedom_ls.content_base.schema import (
    BaseBaseContentModel,
    BaseContentModel,
    ContentType,
    DueDateFields,
    MarkdownContentModel,
)
from freedom_ls.form_engine.typed_answers import question_bounds_error


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


SECTIONS_DESCRIPTION = (
    "Paths to the part.yaml or topic markdown files this tests, "
    "relative to this file's directory"
)


def _reject_bare_sections(value: object) -> object:
    """A `sections:` key with no value, such as one whose every entry is
    commented out, would otherwise clear the list without saying so."""
    if value is None:
        raise ValueError(
            "sections: has no entries. Write `sections: []` for none; on a "
            "question, remove the key to use the form's list."
        )
    return value


def _check_group(value: str | None) -> str | None:
    """A blank or padded group name is almost always a typo, and two
    spellings of one name would split a keep-together group silently."""
    if value is None:
        return None
    if not value.strip():
        raise ValueError("group is empty. Give it a name, or remove the key.")
    if value != value.strip():
        raise ValueError(
            f'group "{value}" has leading or trailing spaces. Remove them.'
        )
    return value


GROUP_DESCRIPTION = (
    "Keep-together group: children of one page sharing this name stay "
    "together, in authored order, when the page's questions shuffle. QUIZ forms only"
)


class Form(
    BaseContentModel,
    MarkdownContentModel,
    DueDateFields,
    content_type=ContentType.FORM,
):
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

    sections: list[Path] | None = Field(None, description=SECTIONS_DESCRIPTION)
    _sections_not_bare = field_validator("sections", mode="before")(
        _reject_bare_sections
    )

    submit_on_exit: bool = Field(
        False,
        description="If True, leaving the test mid-attempt finalises and scores it. Default False.",
    )
    shuffle_pages: bool = Field(
        False,
        description="QUIZ only. If True, each sitting serves the pages in a random order. Default False.",
    )
    shuffle_questions: bool = Field(
        False,
        description="QUIZ only. If True, each sitting serves each page's questions in a random order. Default False.",
    )
    shuffle_options: bool = Field(
        False,
        description="QUIZ only. If True, each sitting serves each question's options in a random order. Default False.",
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
            knobs = {
                "shuffle_pages": self.shuffle_pages,
                "shuffle_questions": self.shuffle_questions,
                "shuffle_options": self.shuffle_options,
            }
            for name, is_on in knobs.items():
                if is_on:
                    raise ValueError(
                        f"{name} should only be set when strategy is QUIZ (in {self.file_path})"
                    )
        return self


class Condition(BaseModel):
    """`when:` on a page, question or content block."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ...,
        description="The slug of the source question, on an earlier page of this form",
    )
    equals: str | None = Field(
        None,
        description="For a multiple_choice or dropdown source: the option value that must be selected",
    )
    includes: str | None = Field(
        None,
        description="For a checkboxes source: an option value that must be among those selected",
    )

    @field_validator("equals", "includes", mode="before")
    @classmethod
    def _literal_as_str(cls, value: object) -> str | None:
        # yaml.safe_load reads an unquoted yes/no/on/off as a bool, so a bool here
        # is almost always an author who meant the word. The option values it is
        # compared against are strings (QuestionOption.value), so an int is one too.
        if isinstance(value, bool):
            raise ValueError(
                "Unquoted yes/no/on/off/true/false are read as booleans. Quote the "
                'value exactly as you wrote it, e.g. equals: "yes", so it is '
                "compared as text."
            )
        if value is None:
            return None
        return str(value)

    @model_validator(mode="after")
    def _exactly_one_test(self) -> "Condition":
        if (self.equals is None) == (self.includes is None):
            raise ValueError("when needs exactly one of equals or includes.")
        return self

    @property
    def literal(self) -> str:
        """The option value the condition tests, whichever key carried it."""
        return self.equals if self.equals is not None else str(self.includes)


WHEN_DESCRIPTION = (
    "Show this only when an earlier answer matches: question (a slug) plus "
    "exactly one of equals or includes"
)


class FormPage(BaseContentModel, content_type=ContentType.FORM_PAGE):
    """A page within a form."""

    when: Condition | None = Field(None, description=WHEN_DESCRIPTION)
    draw: int | None = Field(
        None,
        ge=1,
        description=(
            "Serve this many of the page's questions or groups to each attempt, drawn at "
            "random. QUIZ forms only. Leave out to serve every one."
        ),
    )

    @field_validator("draw", mode="before")
    @classmethod
    def _draw_is_a_whole_number(cls, value: object) -> object:
        # Runs only when the key is present, so None here is a bare `draw:`,
        # which would otherwise switch the draw off without saying so. YAML reads
        # `true` as a bool and `2.0` as a float, and lax int parsing accepts both.
        if value is None:
            raise ValueError(
                "draw: has no value. Write the number of questions or groups to draw, "
                "or remove the key to serve them all."
            )
        if isinstance(value, bool | float):
            raise ValueError(
                "draw must be a whole number of questions or groups, such as draw: 5."
            )
        return value

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
    locked: bool = Field(
        False,
        description="Used in shuffled quizzes: keep this option at its authored position",
    )


class FormContent(BaseBaseContentModel, content_type=ContentType.FORM_CONTENT):
    content: str = Field(..., description="Text")
    when: Condition | None = Field(None, description=WHEN_DESCRIPTION)
    group: str | None = Field(None, max_length=100, description=GROUP_DESCRIPTION)
    _group_is_clean = field_validator("group")(_check_group)


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
    slug: str | None = Field(
        None,
        pattern=r"^[a-z0-9_]+$",
        max_length=100,
        description=(
            "Reference name other pages' `when` uses to name this question. "
            "Lowercase letters, digits and underscores; unique within the form"
        ),
    )
    when: Condition | None = Field(None, description=WHEN_DESCRIPTION)
    group: str | None = Field(None, max_length=100, description=GROUP_DESCRIPTION)
    _group_is_clean = field_validator("group")(_check_group)
    sections: list[Path] | None = Field(None, description=SECTIONS_DESCRIPTION)
    _sections_not_bare = field_validator("sections", mode="before")(
        _reject_bare_sections
    )
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
