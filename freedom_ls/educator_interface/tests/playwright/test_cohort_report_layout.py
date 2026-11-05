"""The cohort Report tab's layout in a real browser."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.files.base import ContentFile

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.tests.helpers import quiz_form
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_report_tab_with_unattempted_quiz_cells_does_not_scroll_the_page_sideways(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Screen-reader-only text in a summary table cell used to escape the
    table's scroll wrapper and widen the whole page."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    course = CourseFactory(title="Algebra")
    for order, title in enumerate(
        ("Unit quiz one", "Unit quiz two", "Unit quiz three")
    ):
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz_form(title, 50), order=order
        )
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    for _ in range(3):
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    report_url = interface_url(
        live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/report"
    )

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(report_url)
        expect(page.get_by_text("Summary of learner progress")).to_be_visible()
        expect(page.get_by_text("Not attempted").first).to_be_attached()
        assert_no_horizontal_overflow(page)


def test_generating_a_report_by_keyboard_keeps_focus_inside_the_downloads_card(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Pressing Enter on "Generate report" swaps the region under it. Focus
    used to drop to <body>, so a keyboard user had to start again from the
    top of the page."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/report"
        )
    )

    generate = page.get_by_role("button", name="Generate report")
    generate.focus()
    page.keyboard.press("Enter")

    expect(page.get_by_role("link", name=re.compile("^Download"))).to_be_visible()
    card = page.locator(
        "section[data-panel=downloads]",
        has=page.get_by_role("heading", name="Downloads"),
    )
    assert page.evaluate("document.activeElement === document.body") is False
    assert card.evaluate("(card) => card.contains(document.activeElement)") is True


def test_report_tab_with_generated_reports_does_not_scroll_the_page_sideways(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The Downloads table used to be wider than a phone's card, cutting off
    the Download buttons and widening the whole page."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    educator_user.email = (
        "a.very.long.educator.address.for.the.report@example-school.org"
    )
    educator_user.save()
    for _ in range(2):
        report = GeneratedReportFactory(
            cohort=cohort,
            status=GeneratedReport.STATUS_READY,
            requested_by=educator_user,
        )
        report.file.save("r.pdf", ContentFile(b"%PDF-1.4 bytes"), save=True)
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    report_url = interface_url(
        live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/report"
    )

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(report_url)
        expect(
            page.get_by_role("link", name=re.compile("^Download")).first
        ).to_be_visible()
        assert_no_horizontal_overflow(page)
