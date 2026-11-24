"""The course page's tab set: educator_interface/panels/course/instance_view.py."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import lxml.html
import pytest

from django.test import Client

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.tests.helpers import _get_document, _interface_url
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.retire import retire


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


@pytest.mark.django_db
def test_a_retired_course_page_has_a_retired_header_badge_and_a_retired_on_row(
    staff_client: Client,
) -> None:
    course = retire(cast(Course, CourseFactory()), at=datetime(2026, 3, 5, tzinfo=UTC))

    document = _get_document(
        staff_client,
        _interface_url(OrganisationFactory().slug, f"courses/{course.pk}"),
    )

    (badge,) = document.cssselect("[data-tone]")
    (details,) = document.cssselect("section[data-panel='details']")
    assert badge.text_content().strip() == "Retired"
    assert "Retired on 5 Mar 2026" in " ".join(details.text_content().split())


@pytest.mark.django_db
def test_a_live_course_page_has_no_retired_badge_and_no_retired_on_row(
    staff_client: Client,
) -> None:
    course = CourseFactory()

    document = _get_document(
        staff_client,
        _interface_url(OrganisationFactory().slug, f"courses/{course.pk}"),
    )

    assert "Retired" not in document.text_content()
