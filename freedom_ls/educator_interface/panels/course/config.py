"""The course section's configuration."""

from __future__ import annotations

from typing import cast

from panel_framework.views import ListViewConfig

from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.panels.course.data_tables import CourseDataTable
from freedom_ls.educator_interface.panels.course.instance_view import (
    CourseInstanceView,
)
from freedom_ls.learner_management.queries import courses_visible_to

__all__ = ["CourseConfig"]


class CourseConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"
    icon = "course"
    model = Course
    list_view = CourseDataTable
    table_key = "courses"
    instance_view = CourseInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not courses_visible_to(request.user, organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied
