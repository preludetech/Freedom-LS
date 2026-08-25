from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.content_base.models import MarkdownContent, TitledContent
from freedom_ls.content_base.schema import ContentType as SchemaContentTypes
from freedom_ls.site_aware_models.models import SiteAwareModel

from ..course_accent import PALETTE


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

    def collection_items(self) -> list["ContentCollectionItem"]:
        """The ordered rows placing this course's children.

        Memoized per instance for the same reason children() is -- see its
        docstring for the request-scoped staleness contract. children() derives
        from this, so the two can never disagree about order.
        """
        if not hasattr(self, "_collection_items_cache"):
            self._collection_items_cache = list(self.items.prefetch_related("child"))
        return self._collection_items_cache

    def collection_items_flat(self) -> list["ContentCollectionItem"]:
        """Get a flattened list of all collection items in the course.

        Includes CourseParts' own rows and their nested rows in order.
        """
        flattened = []
        for item in self.collection_items():
            flattened.append(item)
            if isinstance(item.child, CoursePart):
                flattened.extend(item.child.collection_items())
        return flattened

    def viewable_collection_items(self) -> list["ContentCollectionItem"]:
        """Return ordered list of all viewable collection items (no CoursePart sentinels)."""
        return [
            item
            for item in self.collection_items_flat()
            if not isinstance(item.child, CoursePart)
        ]

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
            self._children_cache = [item.child for item in self.collection_items()]
        return self._children_cache

    def children_flat(self) -> list:
        """Get a flattened list of all content items in the course.

        Includes CourseParts and their nested children in order.
        """
        return [item.child for item in self.collection_items_flat()]

    def viewable_items(self) -> list:
        """Return ordered list of all viewable child content items (no CoursePart sentinels)."""
        return [item.child for item in self.viewable_collection_items()]

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

    def collection_items(self) -> list["ContentCollectionItem"]:
        """The ordered rows placing this part's children.

        Memoized per instance for the same reason children() is -- see its
        docstring for the request-scoped staleness contract. children() derives
        from this, so the two can never disagree about order.
        """
        if not hasattr(self, "_collection_items_cache"):
            self._collection_items_cache = list(self.items.prefetch_related("child"))
        return self._collection_items_cache

    def children(self):
        """Return ordered list of child content items.

        Memoized per instance, like Course.children: the player chrome walks
        each part's children several times per request on the same instance, so
        caching keeps it to one items query plus one query per child content
        type. See Course.children for the request-scoped staleness contract.
        """
        if not hasattr(self, "_children_cache"):
            self._children_cache = [item.child for item in self.collection_items()]
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
