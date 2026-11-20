"""The course outline table and the educator's content previews."""

from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Literal, cast
from uuid import UUID

from django.core.paginator import Page, Paginator
from django.db.models import QuerySet, prefetch_related_objects
from django.http import Http404, HttpRequest, HttpResponse
from django.utils.html import strip_tags

from freedom_ls.content_engine.course_details import course_details_context
from freedom_ls.content_engine.models import ContentCollectionItem, Course, CoursePart
from freedom_ls.educator_interface.panels.common.ids import uuid_or_404
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.form_engine.conditions import full_path
from freedom_ls.form_engine.models import Form, FormPage
from freedom_ls.learner_management.queries import is_course_available_to_organisation
from freedom_ls.panel_framework.actions import PanelAction, count_phrase
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import DataTablePanel
from freedom_ls.panel_framework.tables import Column, DataTable, TableQuery

__all__ = [
    "CourseContentPanel",
    "CourseOutlineTable",
    "OutlineRow",
    "PreviewContentAction",
    "PreviewCourseDetailsAction",
    "_all_collection_items",
    "_condition_question_text",
    "_form_page_rows",
    "_form_preview_context",
    "_outline_content_count",
    "_outline_item_rows",
    "_preview_available",
    "outline_rows",
]


@dataclass(frozen=True)
class OutlineRow:
    """One row of the course outline table: the course details, a part, a
    topic, a form or one page of a multi-page form. A group row (a part, a
    multi-page form) holds its rows in `children`. `preview_query` is the
    Preview trigger's query string, empty for a part, which has nothing to
    show. A `note` row carries only that text."""

    number: str
    title: str
    kind: Literal["course", "part", "topic", "form", "page"]
    preview_query: str = ""
    children: tuple[OutlineRow, ...] = ()
    note: str = ""
    # The form a page row belongs to, so its Preview names both.
    form_title: str = ""

    @property
    def kind_label(self) -> str:
        return {
            "course": "Course",
            "part": "Part",
            "topic": "Topic",
            "form": "Form",
            "page": "Page",
        }[self.kind]

    @property
    def icon(self) -> str:
        return {"part": "folder", "form": "form", "page": "form"}.get(
            self.kind, "topic"
        )


def _form_page_rows(
    item: ContentCollectionItem, form: Form, number: str
) -> tuple[OutlineRow, ...]:
    """One row per page of a form, each previewing that page alone."""
    return tuple(
        OutlineRow(
            number=f"{number}.{position}",
            title=page.title or f"Page {position}",
            kind="page",
            preview_query=f"item={item.pk}&page={page.pk}",
            form_title=form.title,
        )
        for position, page in enumerate(form.pages.all(), start=1)
    )


def _outline_item_rows(
    item: ContentCollectionItem, number: str, *, nested: bool
) -> OutlineRow:
    """The row for one collection item, with its children set. A part holds
    its items (or a note when it has none) and a form with more than one page
    holds its pages; a form with one page is a single row that previews intro
    and page together."""
    child = item.child
    label = number if nested else f"{number}."
    if isinstance(child, CoursePart):
        part_children = tuple(
            _outline_item_rows(part_item, f"{number}.{position}", nested=True)
            for position, part_item in enumerate(child.collection_items(), start=1)
        )
        return OutlineRow(
            number=label,
            title=child.title,
            kind="part",
            children=part_children
            or (
                OutlineRow(
                    number="",
                    title="",
                    kind="part",
                    note="No items in this part.",
                ),
            ),
        )
    if isinstance(child, Form):
        pages = _form_page_rows(item, child, number)
        if len(pages) > 1:
            return OutlineRow(
                number=label,
                title=child.title,
                kind="form",
                preview_query=f"item={item.pk}",
                children=pages,
            )
        kind: Literal["form", "topic"] = "form"
    else:
        kind = "topic"
    return OutlineRow(
        number=label,
        title=str(getattr(child, "title", "")),
        kind=kind,
        preview_query=f"item={item.pk}",
    )


def _all_collection_items(
    items: list[ContentCollectionItem],
) -> list[ContentCollectionItem]:
    """The items and everything inside their parts, at any depth, in order."""
    flattened: list[ContentCollectionItem] = []
    for item in items:
        flattened.append(item)
        if isinstance(item.child, CoursePart):
            flattened.extend(_all_collection_items(item.child.collection_items()))
    return flattened


def outline_rows(course: Course) -> list[OutlineRow]:
    """The top-level rows of the course outline: the course details first,
    then every collection item in order, numbered as the learner outline
    numbers them, each holding its own child rows. One pages query covers
    every form, so the count stays flat as forms grow."""
    forms = [
        item.child
        for item in _all_collection_items(course.collection_items())
        if isinstance(item.child, Form)
    ]
    prefetch_related_objects(forms, "pages")
    rows = [OutlineRow(number="", title="Course details", kind="course")]
    items = course.collection_items()
    rows.extend(
        _outline_item_rows(item, str(position), nested=False)
        for position, item in enumerate(items, start=1)
    )
    if not items:
        rows.append(
            OutlineRow(
                number="",
                title="",
                kind="course",
                note="No content in this course yet.",
            )
        )
    return rows


def _preview_available(request: HttpRequest, course: Course) -> bool:
    """Content previews are for courses available to the organisation in
    view; a course listed only because the organisation holds a
    registration on it shows its details but not its content."""
    organisation = cast(OrganisationScopedRequest, request).organisation
    return is_course_available_to_organisation(course, organisation)


def _outline_content_count(rows: Sequence[OutlineRow]) -> int:
    """The outline's items at every depth: neither the course details row
    nor a note is one."""
    return sum(
        (0 if row.kind == "course" or row.note else 1)
        + _outline_content_count(row.children)
        for row in rows
    )


class CourseOutlineTable(DataTable):
    has_child_rows = True
    compact = True
    noun = "course outline items"
    noun_singular = "course outline item"
    card_template_name = "educator_interface/partials/course_outline_card.html"

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="#",
                template_name="educator_interface/partials/course_outline_number.html",
                header_class="w-0",
                cell_class="w-0 text-muted tabular-nums",
            ),
            Column(
                header="Title",
                template_name="educator_interface/partials/course_outline_title.html",
                card="primary",
            ),
            Column(
                header="Type",
                template_name="educator_interface/partials/course_outline_type.html",
                cell_class="text-muted",
                card="md_only",
            ),
            Column(
                header="Actions",
                template_name="educator_interface/partials/course_outline_actions.html",
                header_class="w-0 sr-only",
                cell_class="w-0",
            ),
        ]

    @classmethod
    def get_rows(
        cls,
        request: HttpRequest,
        queryset: QuerySet | Sequence[object],
        query: TableQuery,
    ) -> Page:
        """Every row on one page. Paging counts top-level rows only, so a
        page of them could hold any number of nested rows."""
        return Paginator(queryset, max(len(queryset), 1)).get_page(1)

    @staticmethod
    def get_child_rows(row: object) -> Sequence[object]:
        return cast(OutlineRow, row).children

    @staticmethod
    def get_row_label(row: object) -> str:
        return cast(OutlineRow, row).title

    @staticmethod
    def get_row_template_name(row: object) -> str | None:
        if cast(OutlineRow, row).note:
            return "educator_interface/partials/course_outline_note.html"
        return None


class CourseContentPanel(DataTablePanel):
    model = Course
    title = "Course content"
    template_name = "educator_interface/panels/course_content.html"
    data_table = CourseOutlineTable
    table_key = "outline"

    @cached_property
    def outline(self) -> list[OutlineRow]:
        if not self.preview_available:
            return []
        return outline_rows(cast(Course, self.instance))

    def get_row_sequence(self, request: HttpRequest) -> Sequence[object]:
        return self.outline

    def entry_count(self, request: HttpRequest, page_obj: Page) -> str:
        count = _outline_content_count(self.outline)
        if count == 0:
            return ""
        return count_phrase(count, self.noun_singular(request), self.noun(request))

    @cached_property
    def preview_available(self) -> bool:
        return _preview_available(self.request, cast(Course, self.instance))

    def get_context_data(self) -> dict[str, object]:
        return {
            **super().get_context_data(),
            "course": cast(Course, self.instance),
            "preview_available": self.preview_available,
        }

    def get_actions(self) -> list[PanelAction]:
        # Actions resolve only from this list, so withholding them is what
        # makes a preview URL 404 for a course not available here.
        if not self.preview_available:
            return []
        return [PreviewContentAction(), PreviewCourseDetailsAction()]


def _condition_question_text(page: FormPage) -> str:
    """The question a page's condition is on, as the learner reads it but
    without its markup, so it can sit inside a sentence."""
    if page.condition_option is None:
        return ""
    rendered = page.condition_option.question.rendered_question()
    return html.unescape(strip_tags(rendered)).strip()


def _form_preview_context(form: Form, page_pk: UUID | None) -> dict[str, object]:
    """One page of the form, on or off any condition, laid out the way the
    form page partial expects, with no sitting behind it. Without a page, a
    one-page form shows its page and a longer form its start page."""
    # A conditional page's heading names the question its condition is on.
    prefetch_related_objects([form], "pages__condition_option__question")
    path = full_path(form)
    preview_page: FormPage | None = None
    if page_pk is not None:
        preview_page = next((page for page in path.pages if page.pk == page_pk), None)
        if preview_page is None:
            raise Http404
    pages = (
        [preview_page]
        if preview_page
        else path.pages[: 1 if path.page_count == 1 else 0]
    )
    position = path.pages.index(preview_page) + 1 if preview_page else None
    return {
        "form": form,
        "preview_page": preview_page,
        "preview_title": (preview_page.title or f"Page {position}")
        if preview_page
        else "",
        "preview_pages": [
            {
                "page": page,
                "page_children": path.children_of(page),
                "condition_question": _condition_question_text(page),
            }
            for page in pages
        ],
        "page_position": position,
        "total_pages": path.page_count,
        "question_count": len(path.question_positions()),
        "question_positions": path.question_positions(),
        "existing_answers": {},
        "rejected_answers": {},
        "read_only": True,
        "show_answer_key": True,
    }


class PreviewContentAction(PanelAction):
    """Shows one child of the course read-only in the app modal. The
    target is found among the authorised course's own collection items,
    so an id from any other course is as missing as a made-up one."""

    action_name = "preview_content"
    capability = None
    renders_in_footer = False
    template_name = "educator_interface/modal/content_preview.html"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        if ctx.request.headers.get("HX-Request") != "true":
            raise Http404
        course = cast(Course, ctx.instance)
        pk = uuid_or_404(ctx.request.GET.get("item"))
        collection_item = next(
            (
                item
                for item in _all_collection_items(course.collection_items())
                if item.pk == pk
            ),
            None,
        )
        if collection_item is None or isinstance(collection_item.child, CoursePart):
            raise Http404
        context: dict[str, object] = {
            "collection_item": collection_item,
            "child": collection_item.child,
        }
        page_param = ctx.request.GET.get("page")
        page_pk = uuid_or_404(page_param) if page_param is not None else None
        if isinstance(collection_item.child, Form):
            context.update(_form_preview_context(collection_item.child, page_pk))
        elif page_pk is not None:
            # Only a form has pages.
            raise Http404
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        # Opening is a read; there is nothing to submit.
        raise Http404


class PreviewCourseDetailsAction(PanelAction):
    """Shows the course's learner-facing details page, without its sign-up
    elements or content outline, in the app modal."""

    action_name = "preview_course_details"
    capability = None
    renders_in_footer = False
    template_name = "educator_interface/modal/course_details_preview.html"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        if ctx.request.headers.get("HX-Request") != "true":
            raise Http404
        course = cast(Course, ctx.instance)
        return {
            **course_details_context(course),
            "course": course,
            "in_modal": True,
            "extra_stats": [],
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        # Opening is a read; there is nothing to submit.
        raise Http404
