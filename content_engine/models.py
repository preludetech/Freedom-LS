from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.utils.translation import gettext_lazy as _
from system_base.models import SiteAwareModel
from .markdown_utils import render_markdown


class ContentType(models.TextChoices):
    """Content type enumeration."""

    TOPIC = "TOPIC", _("Topic")
    FORM = "FORM", _("Form")
    COLLECTION = "COLLECTION", _("Collection")
    FORM_PAGE = "FORM_PAGE", _("Form Page")
    FORM_QUESTION = "FORM_QUESTION", _("Form Question")
    FORM_TEXT = "FORM_TEXT", _("Form Text")


class QuestionType(models.TextChoices):
    """Question type enumeration."""

    MULTIPLE_CHOICE = "multiple_choice", _("Multiple Choice")
    CHECKBOXES = "checkboxes", _("Checkboxes")
    SHORT_TEXT = "short_text", _("Short Text")
    LONG_TEXT = "long_text", _("Long Text")


class FormStrategy(models.TextChoices):
    """Form strategy enumeration."""

    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM", _("Category Value Sum")


class BaseContent(SiteAwareModel):
    """Base model for all content types."""

    meta = models.JSONField(
        null=True, blank=True, help_text=_("Optional metadata as key-value pairs")
    )
    tags = models.JSONField(null=True, blank=True, help_text=_("Optional list of tags"))

    class Meta:
        abstract = True


class TitledContent(BaseContent):
    """Base content model with title and subtitle."""

    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class MarkdownContent(BaseContent):
    """Base content model with markdown content."""

    content = models.TextField(null=True, blank=True, help_text=_("Markdown content"))

    def rendered_content(self):
        from threading import local

        _thread_locals = local()
        request = getattr(_thread_locals, "request", None)
        return render_markdown(self.content, request)

    class Meta:
        abstract = True


class Topic(TitledContent, MarkdownContent):
    """Topic content item."""


class ContentCollection(TitledContent):
    """Content collection - contains an ordered list of child content."""

    def children(self):
        """Return ordered list of child content items."""
        return [item.child for item in self.items.all()]


class ContentCollectionItem(SiteAwareModel):
    """Through model for ContentCollection children with order and overrides."""

    collection = models.ForeignKey(
        ContentCollection, on_delete=models.CASCADE, related_name="items"
    )

    # Generic foreign key to any content type
    child_type = models.ForeignKey(DjangoContentType, on_delete=models.CASCADE)
    child_id = models.UUIDField()
    child = GenericForeignKey("child_type", "child_id")

    order = models.PositiveIntegerField(default=0)
    overrides = models.JSONField(
        null=True,
        blank=True,
        help_text=_("Optional overrides as key-value pairs"),
    )

    class Meta:
        ordering = ["order"]
        unique_together = ["collection", "child_type", "child_id"]

    def __str__(self):
        return f"{self.collection.title} - {self.child} (order={self.order})"


class Form(TitledContent, MarkdownContent):
    """Form content with scoring strategy."""

    strategy = models.CharField(
        max_length=50,
        choices=FormStrategy.choices,
    )


class FormPage(TitledContent):
    """A page within a form."""

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="pages")
    order = models.PositiveIntegerField(default=0)

    def children(self):
        """
        return an ordered list of FormText and FormQuestion instances
        """
        text_items = list(self.text_items.all())
        questions = list(self.questions.all())

        # Combine and sort by order field
        all_children = text_items + questions
        all_children.sort(key=lambda item: item.order)

        return all_children

    class Meta:
        ordering = ["order"]


class FormText(BaseContent):
    """Text content within a form page."""

    text = models.TextField()
    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="text_items"
    )
    order = models.PositiveIntegerField(default=0)

    def rendered_text(self):
        from threading import local

        _thread_locals = local()
        request = getattr(_thread_locals, "request", None)
        return render_markdown(self.text, request)

    class Meta:
        ordering = ["order"]

    @property
    def content_type(self):
        return ContentType.FORM_TEXT

    def __str__(self):
        return self.text[:50]


class FormQuestion(BaseContent):
    """A question within a form page."""

    question = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    required = models.BooleanField(default=True)
    category = models.CharField(max_length=200, null=True, blank=True)
    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)

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

    @property
    def content_type(self):
        return ContentType.FORM_QUESTION

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

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text
