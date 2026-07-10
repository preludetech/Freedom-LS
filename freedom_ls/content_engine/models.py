from pathlib import Path

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.site_aware_models.models import SiteAwareModel

from .course_accent import PALETTE
from .schema import ContentType as SchemaContentTypes


class QuestionType(models.TextChoices):
    """Question type enumeration."""

    MULTIPLE_CHOICE = "multiple_choice", _("Multiple Choice")
    CHECKBOXES = "checkboxes", _("Checkboxes")
    SHORT_TEXT = "short_text", _("Short Text")
    LONG_TEXT = "long_text", _("Long Text")


class FormStrategy(models.TextChoices):
    """Form strategy enumeration."""

    CATEGORY_VALUE_SUM = "CATEGORY_VALUE_SUM", _("Category Value Sum")
    QUIZ = "QUIZ", _("Quiz")


class DifficultyLevel(models.TextChoices):
    """Course difficulty level enumeration."""

    BEGINNER = "beginner", _("Beginner")
    INTERMEDIATE = "intermediate", _("Intermediate")
    ADVANCED = "advanced", _("Advanced")
    ALL_LEVELS = "all_levels", _("All levels")


class CourseVisibility(models.TextChoices):
    """Course visibility lifecycle state."""

    PUBLISHED = "published", _("Published")
    COMING_SOON = "coming_soon", _("Coming soon")
    HIDDEN = "hidden", _("Hidden")


class BaseContent(SiteAwareModel):
    """Base model for all content types."""

    CONTENT_TYPE: str  # Defined on subclasses

    file_path = models.CharField(
        max_length=500,
        help_text=_("Relative path to the source file"),
    )
    meta = models.JSONField(
        null=True, blank=True, help_text=_("Optional metadata as key-value pairs")
    )
    tags = models.JSONField(null=True, blank=True, help_text=_("Optional list of tags"))

    class Meta:
        abstract = True

    @property
    def content_type(self):
        """Instance property that returns the class-level CONTENT_TYPE."""
        return self.CONTENT_TYPE

    def calculate_path_from_root(self, other_relative_path):
        """
        When we load content, the file_paths are relative to the content directory root

        Given a path that is relative to self.file_path, return the path relative to the content root

        For example:
        self.path = tutorial/02-understanding-the-graph-commits-and-checkout.md
        other_relative_path = images/graph1.drawio.svg
        return "tutorial/images/graph1.drawio.svg"

        tutorial/
            images/
                graph1.drawio.svg
            02-understanding-the-graph-commits-and-checkout.md
        """
        parent_dir = Path(self.file_path).parent
        other_relative_path = Path(other_relative_path)

        result = parent_dir

        for part in other_relative_path.parts:
            result = result.parent if part == ".." else result / part

        return result.as_posix()


class TitledContent(BaseContent):
    """Base content model with title and subtitle."""

    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(
        blank=True, default="", help_text=_("Optional description")
    )
    slug = models.SlugField(
        max_length=500,
        help_text=_("URL-friendly identifier"),
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class MarkdownContent(BaseContent):
    """Base content model with markdown content."""

    content = models.TextField(blank=True, default="", help_text=_("Markdown content"))

    def rendered_content(self):
        from threading import local

        if not self.content:
            return ""

        _thread_locals = local()
        request = getattr(_thread_locals, "request", None)
        return render_markdown(
            self.content, request, context={"content_instance": self}
        )

    class Meta:
        abstract = True


class Topic(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.TOPIC

    category = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = ["site", "slug"]

    def preview_url(self):
        return reverse("content_engine:topic_detail", kwargs={"topic_slug": self.slug})


class Activity(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.ACTIVITY

    category = models.CharField(max_length=200, blank=True, default="")
    level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ["site", "slug"]
        verbose_name_plural = "Activities"


class Course(MarkdownContent, TitledContent):
    """Course - contains an ordered list of child content."""

    CONTENT_TYPE = SchemaContentTypes.COURSE

    category = models.CharField(max_length=200, blank=True, default="")
    # BACKEND-PRIVATE: no view, template, or utility may read or branch on access_config
    # directly. All access decisions are made exclusively by the active course-access backend
    # (settings.COURSE_ACCESS_BACKEND). Callers use the backend's CourseAccessDecision fields
    # (can_self_register, can_access_content, cta_label, cta_url) — never this raw config.
    access_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Opaque per-course access configuration. Interpreted ONLY by the active "
            "course-access backend (settings.COURSE_ACCESS_BACKEND); core never reads or "
            "branches on its contents. The default backend stores {'access_type': ...}."
        ),
    )
    icon = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_(
            "Semantic icon name (e.g. 'notes') or a literal glyph name "
            "(e.g. 'drone'). Empty means render the default 'course' icon."
        ),
    )
    icon_fallback = models.CharField(
        max_length=80,
        blank=True,
        default="",
        help_text=_(
            "Optional '<iconset>:<glyph>' reference, used only when 'icon' "
            "is a literal glyph that does not resolve in the active icon set."
        ),
    )
    accent_slot = models.PositiveSmallIntegerField(default=0, editable=False)
    learning_outcomes = ArrayField(
        models.CharField(max_length=255),
        blank=True,
        default=list,
        help_text=_(
            "Ordered list of 'what you'll learn' outcomes. Empty hides the section."
        ),
    )
    difficulty = models.CharField(
        max_length=20,
        blank=True,
        default="",
        choices=DifficultyLevel.choices,
    )
    visibility = models.CharField(
        max_length=20,
        choices=CourseVisibility.choices,
        default=CourseVisibility.PUBLISHED,
        db_index=True,
    )
    table_of_contents_in_development = models.BooleanField(default=False)
    estimated_duration = models.DurationField(null=True, blank=True)
    items = GenericRelation(
        "ContentCollectionItem",
        content_type_field="collection_type",
        object_id_field="collection_id",
        related_query_name="course",
    )

    class Meta:
        unique_together = ["site", "slug"]

    @property
    def accent_slot_key(self) -> str:
        """Palette slot key (e.g. ``"1"``) for this course's accent.

        Used as the suffix in the ``course-accent-<key>`` /
        ``course-progress-<key>`` component classes. It is a slot key, not a
        semantic UI role — see :mod:`freedom_ls.content_engine.course_accent`.
        """
        return PALETTE[self.accent_slot]

    def display_estimated_duration(self) -> str:
        """Human, coarse duration like '~2 hours' / '~45 min' / '~1 hour 30 min'. '' when unset."""
        # Treat both None and a zero timedelta as "unset" (a zero timedelta is
        # falsy, but be explicit so a stored 0 doesn't render a bare "~").
        if not self.estimated_duration or not self.estimated_duration.total_seconds():
            return ""
        total_minutes = round(self.estimated_duration.total_seconds() / 60)
        hours, minutes = divmod(total_minutes, 60)
        parts: list[str] = []
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} min")
        return "~" + " ".join(parts) if parts else ""

    def iso_estimated_duration(self) -> str:
        """ISO-8601 duration string (e.g. 'PT1H30M'). Returns '' when unset, zero,
        or under half a minute (which would otherwise round to a bare, invalid 'PT')."""
        # Round to whole minutes the same way display_estimated_duration does, so
        # the human label and the machine-readable duration never disagree.
        if not self.estimated_duration:
            return ""
        total_minutes = round(self.estimated_duration.total_seconds() / 60)
        if total_minutes == 0:
            return ""
        hours, minutes = divmod(total_minutes, 60)
        parts: list[str] = ["PT"]
        if hours:
            parts.append(f"{hours}H")
        if minutes:
            parts.append(f"{minutes}M")
        return "".join(parts)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self._set_site_from_request()
            self.accent_slot = Course.objects.filter(
                site_id=self.site_id
            ).count() % len(PALETTE)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # Local import to avoid circular imports during app loading.
        from freedom_ls.content_engine.icon_validation import (
            validate_course_icon_fields,
        )

        validate_course_icon_fields(self.icon, self.icon_fallback)

    def children(self):
        """Return ordered list of child content items.

        Memoized per instance: the player chrome walks this tree several times
        per request (viewable_items, course index, breadcrumb part lookup,
        status), all on the same Course instance from get_object_or_404, so
        caching keeps it to one items query plus one query per child content
        type for the whole request. The cache lives on the instance, so a new
        request (new instance) re-fetches. prefetch_related batches the
        generic-FK ``child`` resolution into one query per content type instead
        of one per item.

        Request-scoped contract: mutating ``items`` after ``children()`` has
        been called and re-reading on the same instance returns stale data; no
        current path does this.
        """
        if not hasattr(self, "_children_cache"):
            self._children_cache = [
                item.child for item in self.items.prefetch_related("child")
            ]
        return self._children_cache

    def children_flat(self) -> list:
        """Get a flattened list of all content items in the course.

        Includes CourseParts and their nested children in order.
        """
        flattened = []
        for child in self.children():
            flattened.append(child)
            if isinstance(child, CoursePart):
                for part_child in child.children():
                    flattened.append(part_child)
        return flattened

    def viewable_items(self) -> list:
        """Return ordered list of all viewable child content items (no CoursePart sentinels)."""
        return [
            item for item in self.children_flat() if not isinstance(item, CoursePart)
        ]

    def __str__(self):
        return self.title


class CoursePart(TitledContent):
    """CoursePart - a chapter or section within a course, contains an ordered list of child content."""

    CONTENT_TYPE = SchemaContentTypes.COURSE_PART

    category = models.CharField(max_length=200, blank=True, default="")
    items = GenericRelation(
        "ContentCollectionItem",
        content_type_field="collection_type",
        object_id_field="collection_id",
        related_query_name="course_part",
    )

    class Meta:
        unique_together = ["site", "slug"]

    def children(self):
        """Return ordered list of child content items.

        Memoized per instance, like Course.children: the player chrome walks
        each part's children several times per request on the same instance, so
        caching keeps it to one items query plus one query per child content
        type. See Course.children for the request-scoped staleness contract.
        """
        if not hasattr(self, "_children_cache"):
            self._children_cache = [
                item.child for item in self.items.prefetch_related("child")
            ]
        return self._children_cache

    def __str__(self):
        return self.title


class ContentCollectionItem(SiteAwareModel):
    """Through model for Course/CoursePart children with order and overrides."""

    # Generic foreign key to Course or CoursePart
    collection_type = models.ForeignKey(
        DjangoContentType,
        on_delete=models.CASCADE,
        related_name="items",
        # null=True,
        # blank=True,
    )
    collection_id = models.UUIDField()
    collection = GenericForeignKey("collection_type", "collection_id")

    # collection_old = models.ForeignKey(
    #     Course, on_delete=models.CASCADE, related_name="items"
    # )

    # Generic foreign key to any content type
    child_type = models.ForeignKey(
        DjangoContentType, on_delete=models.CASCADE, related_name="child_items"
    )
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

    def __str__(self):
        collection_title = self.collection.title if self.collection else "Unknown"
        return f"{collection_title} - {self.child} (order={self.order})"


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


def file_upload_handler(instance, filepath):
    filepath = Path(filepath)
    ext = filepath.suffix
    stem = filepath.stem
    pk = instance.pk
    if not pk:
        raise ValueError("Instance must be saved before uploading files")
    return f"content_engine/{stem}{pk}{ext}"


class File(SiteAwareModel):
    """Stores files (images, documents, etc.) referenced in content."""

    class FileType(models.TextChoices):
        IMAGE = "IMAGE", _("Image")
        DOCUMENT = "DOCUMENT", _("Document")
        VIDEO = "VIDEO", _("Video")
        AUDIO = "AUDIO", _("Audio")
        OTHER = "OTHER", _("Other")

    file = models.FileField(upload_to=file_upload_handler)
    file_type = models.CharField(
        max_length=20, choices=FileType.choices, default=FileType.OTHER
    )
    file_path = models.CharField(
        max_length=500,
        help_text=_("Relative path to the source file"),
    )
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ["site", "file_path"]

    def __str__(self):
        return f"{self.original_filename} ({self.get_file_type_display()})"
