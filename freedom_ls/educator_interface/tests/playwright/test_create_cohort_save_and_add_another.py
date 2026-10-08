"""Creating two cohorts in a row from the Create Cohort dialog."""

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


def test_save_and_add_another_keeps_the_dialog_open_and_save_opens_the_last_cohort(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory()
    educator_user.is_superuser = True
    educator_user.save()
    page.goto(interface_url(live_server, organisation.slug, "cohorts"))

    page.get_by_role("button", name="Create Cohort").click()
    dialog = page.locator("#app-modal")
    dialog.get_by_label("Name").fill("First Cohort")
    dialog.get_by_role("button", name="Save and add another").click()

    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Name")).to_have_value("")

    dialog.get_by_label("Name").fill("Second Cohort")
    dialog.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("#instance-title")).to_have_text("Second Cohort")
    second = Cohort.objects.get(organisation=organisation, name="Second Cohort")
    expect(page).to_have_url(re.compile(rf"/cohorts/{second.pk}$"))
    assert Cohort.objects.filter(
        organisation=organisation, name="First Cohort"
    ).exists()
