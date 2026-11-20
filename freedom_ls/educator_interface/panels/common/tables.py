"""The table columns shared by the educator tables."""

from __future__ import annotations

from dataclasses import replace
from operator import attrgetter
from typing import Literal

from freedom_ls.educator_interface.panels.common.badges import active_status_badge
from freedom_ls.panel_framework.tables import BadgeColumn, Column, RelatedListColumn

__all__ = [
    "_active_status_column",
    "_cohort_links_column",
    "_course_title_column",
    "_interface_link",
    "_learner_column",
    "_registration_columns",
]


def _interface_link(
    header: str,
    text_attr: str,
    path_template: str,
    *,
    sortable: bool = False,
    card: Literal["primary", "secondary", "md_only"] = "secondary",
    quick_view: bool = False,
    fallback_text_attr: str = "",
) -> Column:
    """A link column into the educator interface, the shape every table's
    name/title column shares. The link always navigates to the row's page;
    quick_view adds a trigger beside it that opens the row in the quick-view
    drawer instead."""
    return Column(
        header=header,
        template_name="cotton/data-table-cells/link.html",
        text_attr=text_attr,
        fallback_text_attr=fallback_text_attr,
        url_name="educator_interface:interface",
        url_path_template=path_template,
        htmx_nav=True,
        quick_view=quick_view,
        sortable=sortable,
        card=card,
    )


def _learner_column(attr: str = "") -> Column:
    """The shared learner cell. `attr` names the row's learner; empty means
    the row is the learner."""
    prefix = f"{attr}__" if attr else ""
    return Column(
        header="Learner",
        template_name="educator_interface/data-table-cells/learner.html",
        attr=attr,
        sortable=True,
        sort_field=f"{prefix}user__first_name",
        card="primary",
    )


def _active_status_column(header: str, attr: str) -> BadgeColumn:
    """An Active/Inactive badge column for the `is_active` flag at `attr`."""
    return BadgeColumn(
        header=header,
        template_name="cotton/data-table-cells/badge.html",
        badge=lambda row: active_status_badge(bool(attrgetter(attr)(row))),
    )


def _registration_columns() -> list[Column]:
    """The Status/Registered columns the three registration tables share."""
    return [
        _active_status_column("Status", "is_active"),
        Column(
            header="Registered",
            template_name="cotton/data-table-cells/datetime.html",
            attr="registered_at",
            card="md_only",
        ),
    ]


def _course_title_column(
    header: str, text_attr: str, path_template: str, *, attr: str = ""
) -> Column:
    """The course title link with the owner of a shared course under it.
    `attr` names the row's course; empty means the row is the course."""
    return replace(
        _interface_link(header, text_attr, path_template, card="primary"),
        template_name="educator_interface/data-table-cells/course_title.html",
        attr=attr,
    )


def _cohort_links_column(relation_set: str) -> RelatedListColumn:
    """The Cohorts column: each related cohort, linked to its page."""
    return RelatedListColumn(
        header="Cohorts",
        template_name="cotton/data-table-cells/related_list.html",
        relation_set=relation_set,
        link_object_attr="cohort",
        item_text_attr="cohort.name",
        url_name="educator_interface:interface",
        url_path_template="cohorts/{pk}",
        htmx_nav=True,
        layout="inline",
    )
