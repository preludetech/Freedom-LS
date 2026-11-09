"""E2E Playwright flow for the Staff section of a cohort's Settings tab as a
cohort admin sees it: change a viewer to a cohort admin, remove them from the
cohort. A cohort admin holds no audit-log capability, so the History tab is
not theirs to open and the audit entries are read from the database. Refusals, headers and audit
entries are covered by test_actions.py; what only a browser shows is the
dialog steps replacing one another inside the open modal, the list behind it
refreshing, and the tab's layout at each viewport.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_a_cohort_admin_changes_then_removes_a_viewer_and_reads_it_in_history(
    live_server,
    cohort_admin_logged_in_page: Page,
    cohort_admin_user: AbstractBaseUser,
) -> None:
    page = cohort_admin_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, cohort_admin_user, "cohort_admin", cohort)
    viewer = UserFactory(first_name="Vera", last_name="Viewer")
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    settings_path = f"cohorts/{cohort.pk}/__tabs/settings"
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    page.goto(interface_url(live_server, organisation.slug, settings_path))
    expect(main.get_by_role("heading", name="Staff", exact=True)).to_be_visible()
    expect(main.get_by_text("Deactivating stops")).to_have_count(0)
    row = main.get_by_role("listitem").filter(has_text="Vera Viewer")
    expect(row.get_by_text("Cohort viewer")).to_be_visible()

    row.get_by_role("button", name="Change role for Vera Viewer", exact=True).click()
    modal.get_by_text("Cohort admin", exact=True).click()
    modal.get_by_role("button", name="Change role", exact=True).click()
    expect(
        modal.get_by_text("Vera Viewer will become Cohort admin on Alpha Cohort only.")
    ).to_be_visible()
    modal.get_by_role("button", name="Change role", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("Cohort admin")).to_be_visible()
    expect(row.get_by_text("Cohort viewer")).to_have_count(0)

    row.get_by_role("button", name="Remove Vera Viewer from cohort", exact=True).click()
    modal.get_by_role("button", name="Remove from cohort", exact=True).click()
    expect(modal).to_be_hidden()
    expect(main.get_by_text("Vera Viewer")).to_have_count(0)

    actions = list(
        AuditLogEntry.unscoped.filter(
            actor=cohort_admin_user, subjects__contains=[subject_key(viewer)]
        )
        .order_by("created_at", "pk")
        .values_list("action", flat=True)
    )
    assert actions == ["role.deactivated", "role.assigned", "role.deactivated"]

    page.goto(interface_url(live_server, organisation.slug, settings_path))
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
