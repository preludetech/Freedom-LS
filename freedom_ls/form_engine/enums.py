"""Form value enumerations, kept free of model imports.

`scoring` and `submissions` need these but must not pull in `models`, or
importing either module before `form_engine.models` raises ImportError.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class QuestionType(models.TextChoices):
    """Question type enumeration."""

    MULTIPLE_CHOICE = "multiple_choice", _("Multiple Choice")
    CHECKBOXES = "checkboxes", _("Checkboxes")
    SHORT_TEXT = "short_text", _("Short Text")
    LONG_TEXT = "long_text", _("Long Text")


# Free-text questions carry no QuestionOption rows, so anything that reasons
# about selected or correct options has to treat them separately.
FREE_TEXT_QUESTION_TYPES = frozenset({QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT})


class FormStrategy(models.TextChoices):
    """Form strategy enumeration."""

    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM", _("Category Value Sum")
    QUIZ = "QUIZ", _("Quiz")
