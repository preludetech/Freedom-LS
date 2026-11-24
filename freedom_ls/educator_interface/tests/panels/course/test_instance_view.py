"""The course page's tab set: educator_interface/panels/course/instance_view.py."""

from __future__ import annotations

import lxml.html
import pytest

from django.test import Client

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.tests.helpers import _get_document, _interface_url
from freedom_ls.organisations.factories import OrganisationFactory


def _panel_keys(document: lxml.html.HtmlElement) -> list[str | None]:
    return [
        section.get("data-panel")
        for section in document.cssselect("section[data-panel]")
    ]


@pytest.mark.django_db
def test_the_course_page_has_overview_then_content_tabs(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    (nav,) = document.cssselect("nav[aria-label='Course sections']")
    links = nav.cssselect("a")
    assert [link.text_content().strip() for link in links] == ["Overview", "Content"]
    assert links[0].get("aria-current") == "page"
    assert links[1].get("aria-current") is None


@pytest.mark.django_db
def test_the_default_course_page_shows_the_overview_panels_and_not_the_outline(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    assert _panel_keys(document) == ["details", "cohorts", "learners"]


@pytest.mark.django_db
def test_the_content_tab_shows_course_content_then_reference(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content"),
    )

    assert _panel_keys(document) == ["content", "reference"]
