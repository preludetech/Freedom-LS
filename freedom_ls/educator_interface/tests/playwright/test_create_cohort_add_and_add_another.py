"""Creating two cohorts in a row from the Create cohort dialog."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_add_and_add_another_keeps_the_dialog_open_and_add_opens_the_last_cohort(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory()
    educator_user.is_superuser = True
    educator_user.save()
    page.goto(interface_url(live_server, organisation.slug, "cohorts"))

    page.get_by_role("button", name="Create cohort").first.click()
    dialog = page.locator("#app-modal")
    dialog.get_by_label("Name").fill("First Cohort")
    dialog.get_by_role("button", name="Add and add another").click()

    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Name")).to_have_value("")

    dialog.get_by_label("Name").fill("Second Cohort")
    dialog.get_by_role("button", name="Add", exact=True).click()

    expect(page.locator("#instance-title")).to_have_text("Second Cohort")
    second = Cohort.objects.get(organisation=organisation, name="Second Cohort")
    expect(page).to_have_url(re.compile(rf"/cohorts/{second.pk}$"))
    assert Cohort.objects.filter(
        organisation=organisation, name="First Cohort"
    ).exists()


def test_wrapped_dialog_footer_keeps_its_actions_at_the_right_edge(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """On a phone the footer wraps; the actions row used to start at the left.

    The actions wrapper was only as wide as its content, so its right alignment
    did nothing once it dropped onto its own row below Cancel.
    """
    page = educator_logged_in_page
    organisation = OrganisationFactory()
    educator_user.is_superuser = True
    educator_user.save()
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(interface_url(live_server, organisation.slug, "cohorts"))

    page.get_by_role("button", name="Create cohort").first.click()
    footer = page.locator("#app-modal [data-modal-footer]:visible")
    expect(footer).to_be_visible()

    add = footer.get_by_role("button", name="Add", exact=True)
    cancel = footer.get_by_role("button", name="Cancel")
    add_box = add.bounding_box()
    cancel_box = cancel.bounding_box()
    footer_box = footer.bounding_box()
    assert add_box is not None
    assert cancel_box is not None
    assert footer_box is not None
    assert add_box["y"] > cancel_box["y"], "the footer should wrap at 375px"
    # The footer's right padding is px-6 (24px).
    content_right = footer_box["x"] + footer_box["width"] - 24
    assert abs(add_box["x"] + add_box["width"] - content_right) <= 1
