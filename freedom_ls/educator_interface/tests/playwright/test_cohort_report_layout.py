"""The cohort Report tab in a real browser: layout at every viewport and
report generation."""

from __future__ import annotations

import re
import time
from typing import cast

import pytest
from playwright.sync_api import Page, Route, expect

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
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.tests.helpers import quiz_form, requires_tailwind_bundle
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

REPORT_BUILD_TIMEOUT_MS = 30_000

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def _seed_report_tab(
    educator_user: AbstractBaseUser,
) -> tuple[Organisation, Cohort]:
    """A cohort with a course of three quizzes, three named learners who have
    attempted none of them, two ready reports requested by an educator with a
    long email address, and an organisation-admin educator."""
    organisation = cast(Organisation, OrganisationFactory(name="Org A"))
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Year 9 Maths"))
    course = CourseFactory(title="Algebra")
    for order, title in enumerate(
        ("Unit quiz one", "Unit quiz two", "Unit quiz three")
    ):
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz_form(title, 50), order=order
        )
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    for first, last in (
        ("Aaron", "Abercrombie"),
        ("Aaron", "Abrahams"),
        ("Amy", "Achterberg"),
    ):
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(
                organisation=organisation,
                user__first_name=first,
                user__last_name=last,
            ),
        )
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
    return organisation, cohort


def test_cohort_report_layout_flow(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """One cohort Report tab at every viewport proves:

    - screen-reader-only text in an unattempted quiz cell stays inside the
      table's scroll wrapper, so the page never scrolls sideways;
    - the Downloads table fits a phone's card with its Download buttons
      reachable, and the page does not widen;
    - the sticky learner column keeps a readable name, whole names and a
      one-line "Not started" badge;
    - at 375px the Download link sits inside its scroll region and the
      requester line is readable on one line.
    """
    page = educator_logged_in_page
    organisation, cohort = _seed_report_tab(educator_user)
    report_url = interface_url(
        live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/report"
    )

    for viewport in QA_VIEWPORTS:
        width = viewport["width"]
        page.set_viewport_size(viewport)
        page.goto(report_url)
        expect(
            page.get_by_text("Summary of learner progress"),
            f"summary missing at {width}px",
        ).to_be_visible()
        expect(
            page.get_by_text("Not attempted").first,
            f"unattempted cells missing at {width}px",
        ).to_be_attached()
        download = page.get_by_role("link", name=re.compile("^Download")).first
        expect(download, f"Download link hidden at {width}px").to_be_visible()
        assert_no_horizontal_overflow(page)

        names = page.locator("tbody th[scope='row'] span.truncate")
        assert names.count() == 3, f"expected 3 learner names at {width}px"
        for index in range(3):
            assert names.nth(index).evaluate(
                "el => el.scrollWidth <= el.clientWidth"
            ), f"name cut short at {width}px"

        if width != 375:
            continue

        name_cell = page.locator("tbody th[scope='row']").first
        name_box = name_cell.bounding_box()
        assert name_box is not None
        assert name_box["width"] >= 150, (
            "learner name cell narrower than 150px at 375px"
        )
        badge_box = page.get_by_text("Not started").first.bounding_box()
        assert badge_box is not None
        assert badge_box["height"] < 32, "Not started badge wraps at 375px"
        box = download.bounding_box()
        assert box is not None
        downloads = page.get_by_role("table", name="Generated reports")
        # The button is inside the table's own scroll region, not behind it.
        fits = downloads.evaluate(
            "table => table.scrollWidth <= table.parentElement.clientWidth"
        )
        assert fits, "Downloads table wider than its scroll region at 375px"
        region_box = downloads.locator("xpath=..").bounding_box()
        assert region_box is not None
        assert box["x"] + box["width"] <= region_box["x"] + region_box["width"], (
            "Download link past the region edge at 375px"
        )
        first_cell = downloads.locator("tbody td").first
        # On a phone the requester sits under the date, in one readable line.
        by_line = first_cell.locator("[data-report-by]")
        expect(by_line, "requester line hidden at 375px").to_be_visible()
        by_box = by_line.bounding_box()
        assert by_box is not None
        assert by_box["height"] < 32, "requester line wraps at 375px"
        generated_box = first_cell.bounding_box()
        assert generated_box is not None
        assert generated_box["height"] < 100, (
            "Generated cell taller than 100px at 375px"
        )


@pytest.mark.weasyprint
@requires_tailwind_bundle
def test_cohort_report_generate_flow(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Generating a cohort report proves:

    - the Report link and a mouse click on "Generate report" build a PDF and
      show its Download link;
    - Enter on "Generate report" builds another and focus returns to the
      button instead of dropping to <body>;
    - while a held request is in flight focus never sits on <body>, and it
      ends on the button once the report shows.
    """
    page = educator_logged_in_page
    page.set_viewport_size({"width": 1440, "height": 900})
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    downloads = page.get_by_role("link", name=re.compile("^Download"))

    page.goto(interface_url(live_server, organisation.slug, f"cohorts/{cohort.pk}"))
    page.get_by_role("link", name="Report", exact=True).click()
    page.get_by_role("button", name="Generate report").click()
    # The report is built for real; under parallel test runs that takes
    # longer than the default wait.
    expect(downloads, "no Download link after the mouse generate").to_have_count(
        1, timeout=REPORT_BUILD_TIMEOUT_MS
    )

    # Pressing Enter swaps the region under the button. Focus used to drop to
    # <body>, so a keyboard user had to start again from the top of the page.
    generate = page.get_by_role("button", name="Generate report")
    generate.focus()
    page.keyboard.press("Enter")
    expect(downloads, "no new Download link after the keyboard generate").to_have_count(
        2, timeout=REPORT_BUILD_TIMEOUT_MS
    )
    # Focus returns after the request ends, a tick after the swap, so wait
    # for it rather than reading document.activeElement once.
    expect(
        generate, "focus not back on Generate after the keyboard generate"
    ).to_be_focused()

    # Disabling the button for the length of its request dropped focus to
    # <body> until the report finished; focus now stays on the button while
    # the "Generating…" state shows and ends on it.
    def hold_generate_request(route: Route) -> None:
        # Keeps the request in flight long enough to sample focus.
        time.sleep(1.5)
        route.continue_()

    generate_route = re.compile(r"/generate")
    page.route(generate_route, hold_generate_request)
    generate = page.get_by_role("button", name=re.compile("Generate"))
    generate.focus()
    expect(generate).to_be_focused()
    page.evaluate(
        """() => {
            window.__bodySamples = 0;
            window.__inFlightSamples = 0;
            setInterval(() => {
                if (!document.querySelector("form.htmx-request")) return;
                window.__inFlightSamples += 1;
                if (document.activeElement === document.body) window.__bodySamples += 1;
            }, 20);
        }"""
    )

    page.keyboard.press("Enter")

    page.wait_for_function("window.__inFlightSamples > 10")
    expect(downloads, "no new Download link after the held generate").to_have_count(
        3, timeout=REPORT_BUILD_TIMEOUT_MS
    )
    expect(page.locator("form.htmx-request")).to_have_count(0)
    assert page.evaluate("window.__bodySamples") == 0, "focus sat on <body> mid-request"
    expect(
        page.get_by_role("button", name=re.compile("Generate")),
        "focus not on Generate after the held generate",
    ).to_be_focused()
    page.unroute(generate_route, hold_generate_request)
