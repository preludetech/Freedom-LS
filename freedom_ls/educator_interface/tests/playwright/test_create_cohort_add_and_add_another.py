"""The Create cohort dialog, in one flow.

Proves: at 375px the footer wraps and its actions sit at the right edge; on
desktop "Add and add another" keeps the dialog open with an empty field, and
"Add" opens the last cohort's page while the first cohort exists."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_create_cohort_dialog_flow(
    live_server: LiveServer,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory()
    educator_user.is_superuser = True
    educator_user.save()
    cohorts_url = interface_url(live_server, organisation.slug, "cohorts")

    # On a phone the footer wraps. The actions wrapper was only as wide as its
    # content, so its right alignment did nothing once it dropped onto its own
    # row below Cancel.
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(cohorts_url)
    page.get_by_role("button", name="Create cohort").first.click()
    footer = page.locator("#app-modal [data-modal-footer]:visible")
    expect(footer, "dialog footer not visible at 375px").to_be_visible()
    add = footer.get_by_role("button", name="Add", exact=True)
    cancel = footer.get_by_role("button", name="Cancel")
    add_box = add.bounding_box()
    cancel_box = cancel.bounding_box()
    footer_box = footer.bounding_box()
    assert add_box is not None, "Add button has no box at 375px"
    assert cancel_box is not None, "Cancel button has no box at 375px"
    assert footer_box is not None, "dialog footer has no box at 375px"
    assert add_box["y"] > cancel_box["y"], "the footer should wrap at 375px"
    # The footer's right padding is px-6 (24px).
    content_right = footer_box["x"] + footer_box["width"] - 24
    assert abs(add_box["x"] + add_box["width"] - content_right) <= 1, (
        "Add button not at the footer's right edge at 375px"
    )
    cancel.click()
    expect(
        page.locator("#app-modal"), "dialog still open after Cancel"
    ).not_to_be_visible()

    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(cohorts_url)
    page.get_by_role("button", name="Create cohort").first.click()
    dialog = page.locator("#app-modal")
    dialog.get_by_label("Name").fill("First Cohort")
    dialog.get_by_role("button", name="Add and add another").click()

    expect(dialog, "dialog closed after Add and add another").to_be_visible()
    expect(
        dialog.get_by_label("Name"), "Name field not cleared after Add and add another"
    ).to_have_value("")

    dialog.get_by_label("Name").fill("Second Cohort")
    dialog.get_by_role("button", name="Add", exact=True).click()

    expect(page.locator("#instance-title")).to_have_text("Second Cohort")
    second = Cohort.objects.get(organisation=organisation, name="Second Cohort")
    expect(page).to_have_url(re.compile(rf"/cohorts/{second.pk}$"))
    assert Cohort.objects.filter(
        organisation=organisation, name="First Cohort"
    ).exists(), "first cohort was not created"
