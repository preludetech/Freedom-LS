"""The course details panel."""

from __future__ import annotations

from typing import ClassVar, cast

from panel_framework.panels import InstanceDetailsPanel

from django.utils.html import format_html, format_html_join

from freedom_ls.content_engine.models import Course

__all__ = ["CourseDetailsPanel"]


class CourseDetailsPanel(InstanceDetailsPanel):
    model = Course
    fields = [
        "title",
        "subtitle",
        "dashboard_category",
        "get_visibility_display",
        "get_difficulty_display",
        "display_estimated_duration",
        "display_time_limit",
        "learning_outcomes",
        "lesson_count",
    ]
    # The learner details page's words, so an educator and a learner
    # read the same label for the same fact.
    labels: ClassVar[dict[str, str]] = {
        "dashboard_category": "Category",
        "get_visibility_display": "Visibility",
        "get_difficulty_display": "Level",
        "display_estimated_duration": "Duration",
        "display_time_limit": "Time limit",
        "lesson_count": "Lessons",
    }

    def get_rows(self) -> list[dict[str, object]]:
        course = cast(Course, self._bound_instance())
        rows: list[dict[str, object]] = []
        for name, row in zip(self.fields, super().get_rows(), strict=True):
            if row["value"] in ("", self.empty_value_display):
                continue
            if name == "learning_outcomes":
                # One item per outcome: an outcome can hold a comma.
                row["value"] = format_html(
                    '<ul class="ml-0 list-none space-y-1">{}</ul>',
                    format_html_join(
                        "",
                        '<li class="flex gap-2 py-0"><span aria-hidden="true">•</span>'
                        "<span>{}</span></li>",
                        ((outcome,) for outcome in course.learning_outcomes),
                    ),
                )
            rows.append({**row, "label": self.labels.get(name, row["label"])})
        if course.is_retired:
            rows.append(self.detail_row("Retired on", course.retired_at, "date"))
        return rows
