from django.db import models
from django.utils.translation import gettext_lazy as _
from system_base.models import SiteAwareModel


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
        null=True,
        blank=True,
        help_text=_("Optional metadata as key-value pairs")
    )
    tags = models.JSONField(
        null=True,
        blank=True,
        help_text=_("Optional list of tags")
    )

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
    content = models.TextField(
        null=True,
        blank=True,
        help_text=_("Markdown content")
    )

    class Meta:
        abstract = True


class Topic(TitledContent, MarkdownContent):
    """Topic content item."""



class ContentCollection(TitledContent):
    """Content collection - contains an ordered list of child content."""
    children = models.JSONField(
        help_text=_("Single directory path or list of content paths")
    )

class Form(TitledContent, MarkdownContent):
    """Form content with scoring strategy."""
    strategy = models.CharField(
        max_length=50,
        choices=FormStrategy.choices,
    )



class FormPage(TitledContent):
    """A page within a form."""
    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name="pages"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']



class FormText(BaseContent):
    """Text content within a form page."""
    text = models.TextField()
    form_page = models.ForeignKey(
        FormPage,
        on_delete=models.CASCADE,
        related_name="text_items"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


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
        FormPage,
        on_delete=models.CASCADE,
        related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


    def __str__(self):
        return self.question[:50]


class QuestionOption(SiteAwareModel):
    """An option for a form question."""
    question = models.ForeignKey(
        FormQuestion,
        on_delete=models.CASCADE,
        related_name="options"
    )
    text = models.CharField(max_length=500)
    value = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text
