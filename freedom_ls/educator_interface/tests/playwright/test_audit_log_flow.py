"""The audit log's "What" filter: a grouped checklist applied once, in the
desktop toolbar and in the phone sheet."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def _seed(educator_user: AbstractBaseUser):
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    AuditLogEntryFactory(target=organisation, actor=grantor, action="cohort.created")
    AuditLogEntryFactory(target=organisation, actor=grantor, action="cohort.renamed")
    return organisation


def test_ticking_an_action_in_the_toolbar_checklist_narrows_the_log(
    live_server, educator_logged_in_page: Page, educator_user: AbstractBaseUser
) -> None:
    page = educator_logged_in_page
    organisation = _seed(educator_user)
    page.goto(interface_url(live_server, organisation.slug, "audit-log"))
    main = page.locator("#main-content")
    # Header row, the two seeded entries and the role assignment that gave
    # the educator access.
    expect(main.get_by_role("row")).to_have_count(4)

    main.get_by_text("Add filter", exact=True).click()
    main.locator("summary", has_text="What").click()
    popover = main.locator("form.surface")
    popover.get_by_label("Cohort created", exact=True).check()
    popover.get_by_role("button", name="Apply", exact=True).click()

    expect(page).to_have_url(re.compile(r"audit_log-what=cohort\.created"))
    expect(main.get_by_role("row")).to_have_count(2)


def test_the_phone_sheet_lists_the_actions_under_collapsed_groups(
    live_server, educator_logged_in_page: Page, educator_user: AbstractBaseUser
) -> None:
    page = educator_logged_in_page
    organisation = _seed(educator_user)
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(interface_url(live_server, organisation.slug, "audit-log"))

    page.get_by_role("button", name="Filter", exact=True).click()
    sheet = page.get_by_role("dialog", name="Filter")
    expect(sheet).to_be_visible()
    sheet.get_by_text("Cohorts", exact=True).click()
    sheet.get_by_label("Cohort created", exact=True).check()
    sheet.get_by_role("button", name="Show results", exact=True).click()

    expect(page).to_have_url(re.compile(r"audit_log-what=cohort\.created"))
    expect(page.locator("#main-content").get_by_role("listitem")).to_have_count(1)
