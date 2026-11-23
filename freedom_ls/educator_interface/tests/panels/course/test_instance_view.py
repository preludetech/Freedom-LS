"""The course page's panel stack."""

from __future__ import annotations

import pytest

from django.test import Client

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.panels.course.instance_view import (
    CoursePanelStack,
)
from freedom_ls.educator_interface.tests.helpers import _get_document, _interface_url
from freedom_ls.organisations.factories import OrganisationFactory

PANEL_ORDER = ["details", "content", "reference", "cohorts", "learners"]


def test_the_course_panel_stack_orders_reference_after_content() -> None:
    assert list(CoursePanelStack.children) == PANEL_ORDER


@pytest.mark.django_db
def test_the_rendered_course_page_shows_its_panels_in_stack_order(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    keys = [
        section.get("data-panel")
        for section in document.cssselect("section[data-panel]")
    ]
    assert keys == PANEL_ORDER
