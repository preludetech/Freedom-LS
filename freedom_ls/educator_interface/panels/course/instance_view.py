"""The course instance view and its panel stack."""

from __future__ import annotations

from freedom_ls.educator_interface.panels.course.content_preview import (
    CourseContentPanel,
)
from freedom_ls.educator_interface.panels.course.data_table_panels import (
    CourseCohortRegistrationsPanel,
    CourseLearnerRegistrationsPanel,
)
from freedom_ls.educator_interface.panels.course.panels import CourseDetailsPanel
from freedom_ls.panel_framework.panels import PanelStack
from freedom_ls.panel_framework.views import InstanceView

__all__ = ["CourseInstanceView", "CoursePanelStack"]


class CoursePanelStack(PanelStack):
    children = {
        "details": CourseDetailsPanel,
        "content": CourseContentPanel,
        "cohorts": CourseCohortRegistrationsPanel,
        "learners": CourseLearnerRegistrationsPanel,
    }


class CourseInstanceView(InstanceView):
    panel = CoursePanelStack
