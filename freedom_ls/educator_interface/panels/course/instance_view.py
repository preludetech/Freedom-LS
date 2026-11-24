"""The course instance view and its tab set."""

from __future__ import annotations

from typing import cast

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.panels.common.badges import retired_badge
from freedom_ls.educator_interface.panels.course.content_preview import (
    CourseContentPanel,
    CourseReferencePanel,
)
from freedom_ls.educator_interface.panels.course.data_table_panels import (
    CourseCohortRegistrationsPanel,
    CourseLearnerRegistrationsPanel,
)
from freedom_ls.educator_interface.panels.course.panels import CourseDetailsPanel
from freedom_ls.panel_framework.panels import PanelStack, TabSet
from freedom_ls.panel_framework.views import InstanceView, StatusBadge

__all__ = ["CourseInstanceView", "CourseTabSet"]


class CourseOverviewStack(PanelStack):
    title = "Overview"
    children = {
        "details": CourseDetailsPanel,
        "cohorts": CourseCohortRegistrationsPanel,
        "learners": CourseLearnerRegistrationsPanel,
    }


class CourseContentStack(PanelStack):
    title = "Content"
    children = {
        "content": CourseContentPanel,
        "reference": CourseReferencePanel,
    }


class CourseTabSet(TabSet):
    title = "Course sections"
    children = {"overview": CourseOverviewStack, "content": CourseContentStack}


class CourseInstanceView(InstanceView):
    panel = CourseTabSet

    def get_status_badge(self) -> StatusBadge | None:
        return retired_badge(cast(Course, self.instance).retired_at)
