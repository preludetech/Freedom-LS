from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.site_aware_models.models import SiteAwareModel

from ..schema import ContentType as SchemaContentTypes
from .base import BaseContent, MarkdownContent, TitledContent


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


class Form(TitledContent, MarkdownContent):
    """Form content with scoring strategy."""

    CONTENT_TYPE = SchemaContentTypes.FORM

    strategy = models.CharField(
        max_length=50,
        choices=FormStrategy.choices,
    )

    quiz_show_incorrect = models.BooleanField(
        blank=True, null=True
    )  # Should we show the answers after the user finishes the form?

    quiz_pass_percentage = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text=_("Percentage (0-100) required to pass the quiz"),
    )

    submit_on_exit = models.BooleanField(
        default=False,
        help_text=_(
            "If True, leaving the test mid-attempt finalises and scores it. "
            "If False (default), the attempt is saved and can be resumed."
        ),
    )

    class Meta:
        unique_together = ["site", "slug"]

    def __str__(self):
        return self.title


class FormPage(TitledContent):
    """A page within a form."""

    CONTENT_TYPE = SchemaContentTypes.FORM_PAGE

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="pages")
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=200, blank=True, default="")

    def children(self):
        """
        return an ordered list of FormContent and FormQuestion instances
        """
        text_items = list(self.text_items.all())
        questions = list(self.questions.all())

        # Combine and sort by order field
        all_children = text_items + questions
        all_children.sort(key=lambda item: item.order)

        return all_children

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.form.title} - {self.title}"


class FormContent(MarkdownContent):
    """Text content within a form page."""

    CONTENT_TYPE = SchemaContentTypes.FORM_CONTENT

    content = models.TextField()
    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="text_items"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.content[:50]


class FormQuestion(BaseContent):
    """A question within a form page."""

    CONTENT_TYPE = SchemaContentTypes.FORM_QUESTION

    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=200, blank=True, default="")

    question = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    required = models.BooleanField(default=True)

    def rendered_question(self):
        from threading import local

        _thread_locals = local()
        request = getattr(_thread_locals, "request", None)
        return render_markdown(self.question, request)

    def question_number(self):
        """
        Return 1 for the first question in the Form, 2 for the second etc. Note that this might not be the same as the order attribute because form pages contain more than just questions
        """
        form = self.form_page.form
        question_count = 0

        # Iterate through all pages in order
        for page in form.pages.all():
            # Get all questions on this page in order
            for question in page.questions.all():
                question_count += 1
                if question.pk == self.pk:
                    return question_count

        return None

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.question[:50]


class QuestionOption(SiteAwareModel):
    """An option for a form question."""

    question = models.ForeignKey(
        FormQuestion, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=500)
    value = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    correct = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text
