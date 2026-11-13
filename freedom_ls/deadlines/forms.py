"""Forms for the course progress pause, resume and extend pages."""

from __future__ import annotations

from typing import cast

from unfold.widgets import (
    INPUT_CLASSES,
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminRadioSelectWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextareaWidget,
)

from django import forms
from django.http import QueryDict

from freedom_ls.audit_log.models import REASON_LENGTH
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.deadlines.models import MAX_EXTENSION_DAYS, ExtensionTarget
from freedom_ls.learner_progress.models import CourseProgress


def _date_widget() -> forms.DateInput:
    """A native date picker styled like Unfold's other admin inputs."""
    return forms.DateInput(attrs={"type": "date", "class": " ".join(INPUT_CLASSES)})


class CollectionItemChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: ContentCollectionItem) -> str:
        child = obj.child
        if child is None:
            return str(obj.pk)
        return f"{child.title} ({child.file_path})"


class ReasonForm(forms.Form):
    reason = forms.CharField(max_length=REASON_LENGTH, widget=UnfoldAdminTextareaWidget)


class PauseCourseForm(ReasonForm):
    planned_resume_on = forms.DateField(
        required=False,
        widget=_date_widget(),
        help_text=(
            "Leave empty to pause until you resume it. Deadlines move by the whole "
            "days paused, rounded up."
        ),
    )


class ResumeCourseForm(ReasonForm):
    pass


class ExtendDeadlineForm(ReasonForm):
    """Picks what to extend and by how much. The service re-checks every rule, so the form
    only keeps a bad combination from reaching it."""

    target_kind = forms.ChoiceField(
        choices=[
            (ExtensionTarget.COLLECTION_ITEM, "One item"),
            (ExtensionTarget.TIME_LIMIT, "Course time limit"),
            (ExtensionTarget.COURSE, "Whole course"),
        ],
        widget=UnfoldAdminRadioSelectWidget,
    )
    collection_item = CollectionItemChoiceField(
        queryset=ContentCollectionItem.objects.none(),
        required=False,
        widget=UnfoldAdminSelectWidget,
        help_text="Only for One item.",
    )
    days = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=MAX_EXTENSION_DAYS,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="Give days or a date, not both.",
    )
    requested_date = forms.DateField(
        required=False,
        widget=_date_widget(),
        help_text="The date the deadline should fall on. Not for Whole course.",
    )
    field_order = [
        "target_kind",
        "collection_item",
        "days",
        "requested_date",
        "reason",
    ]

    def __init__(self, record: CourseProgress, data: QueryDict | None = None) -> None:
        super().__init__(data)
        picker = cast(CollectionItemChoiceField, self.fields["collection_item"])
        picker.queryset = ContentCollectionItem.objects.filter(
            pk__in=[i.pk for i in record.course.viewable_collection_items()]
        ).prefetch_related("child")

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        kind = cleaned.get("target_kind")
        if kind is None:
            return cleaned
        if (cleaned.get("days") is None) == (cleaned.get("requested_date") is None):
            self.add_error(None, "Give either days or a date.")
        if kind == ExtensionTarget.COURSE and cleaned.get("requested_date"):
            self.add_error("requested_date", "Whole course takes days, not a date.")
        has_item = cleaned.get("collection_item") is not None
        if kind == ExtensionTarget.COLLECTION_ITEM and not has_item:
            self.add_error("collection_item", "Pick an item.")
        if kind != ExtensionTarget.COLLECTION_ITEM and has_item:
            self.add_error("collection_item", "Pick an item only for One item.")
        return cleaned
