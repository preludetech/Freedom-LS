"""The audit log page, in one flow.

Proves: at 768px the When cell keeps date and time on one line and the Who
cell stays at least 160px wide beside a long What cell; at 375px the Filter
sheet lists the actions under collapsed groups and filters to the ticked
action; on desktop the toolbar "What" checklist narrows the log and sets the
``audit_log-what`` URL parameter."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

from .helpers import interface_url

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def _seed(educator_user: AbstractBaseUser) -> Organisation:
    organisation: Organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True, user__email="demodev@email.com").user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    AuditLogEntryFactory(target=organisation, actor=grantor, action="cohort.created")
    AuditLogEntryFactory(target=organisation, actor=grantor, action="cohort.renamed")
    AuditLogEntryFactory(
        target=organisation,
        actor=grantor,
        action="cohort.created",
        target_label="Learner registered for course Functionality Demo - Course Parts "
        * 3,
    )
    return organisation


def test_audit_log_flow(
    live_server: LiveServer,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Covers the 768px When and Who cell layout, the 375px Filter sheet and
    the desktop "What" checklist."""
    page = educator_logged_in_page
    organisation = _seed(educator_user)
    audit_log_url = interface_url(live_server, organisation.slug, "audit-log")
    main = page.locator("#main-content")

    # At 768px the When cell wrapped the time under the date, making every
    # audit log row two lines tall.
    page.set_viewport_size({"width": 768, "height": 1024})
    page.goto(audit_log_url)
    spans = main.locator("table tbody tr time").first.locator("span")
    date_box = spans.nth(0).bounding_box()
    time_box = spans.nth(1).bounding_box()
    assert date_box is not None, "When cell date span has no box at 768px"
    assert time_box is not None, "When cell time span has no box at 768px"
    assert time_box["y"] == date_box["y"], (
        "When cell wraps the time under the date at 768px"
    )

    # A long What cell squeezed the Who column to a single character.
    long_label_row = main.locator("table tbody tr").filter(
        has_text="Learner registered for course"
    )
    who_width = (
        long_label_row.locator("td")
        .nth(2)
        .evaluate("el => el.getBoundingClientRect().width")
    )
    assert who_width >= 160, "Who cell narrower than 160px at 768px"

    # The phone sheet lists the actions under collapsed groups. Filtering
    # navigates, so this runs before the desktop checklist reloads the page.
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(audit_log_url)
    page.get_by_role("button", name="Filter", exact=True).click()
    sheet = page.get_by_role("dialog", name="Filter")
    expect(sheet, "Filter sheet not visible at 375px").to_be_visible()
    sheet.get_by_text("Cohorts", exact=True).click()
    sheet.get_by_label("Cohort created", exact=True).check()
    sheet.get_by_role("button", name="Show results", exact=True).click()
    expect(page, "phone sheet did not set the what filter in the URL").to_have_url(
        re.compile(r"audit_log-what=cohort\.created")
    )
    expect(
        main.get_by_role("listitem"), "phone sheet filter should leave two entries"
    ).to_have_count(2)

    # Desktop toolbar checklist, from an unfiltered page.
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(audit_log_url)
    # Header row, the three seeded entries and the role assignment that gave
    # the educator access.
    expect(main.get_by_role("row"), "unfiltered log row count").to_have_count(5)
    main.get_by_text("Add filter", exact=True).click()
    main.locator("summary", has_text="What").click()
    checklist = main.locator("form").filter(
        has=page.get_by_role("button", name="Apply", exact=True)
    )
    checklist.get_by_label("Cohort created", exact=True).check()
    checklist.get_by_role("button", name="Apply", exact=True).click()
    expect(
        page, "toolbar checklist did not set the what filter in the URL"
    ).to_have_url(re.compile(r"audit_log-what=cohort\.created"))
    expect(main.get_by_role("row"), "filtered log row count").to_have_count(3)
