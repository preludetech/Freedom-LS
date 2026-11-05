"""Touch-target sizes on the educator interface: 44px below md, compact above."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_helpers import QA_VIEWPORTS

from .helpers import interface_url

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE = QA_VIEWPORTS[0]

_SMALLEST_CONTROL = """() => {
    const controls = document.querySelectorAll(
        "header a, header button, #main-content .btn, #main-content input[type=search], #main-content nav a, dialog[open] a, dialog[open] button, dialog[open] input:not([type=hidden]), dialog[open] select"
    );
    // A visually hidden checkbox or radio is tapped through its label.
    const hitTarget = (el) => (el.classList.contains("sr-only") && el.closest("label")) || el;
    return [...controls]
        .map((el) => ({ el, box: hitTarget(el).getBoundingClientRect() }))
        .filter(({ box }) => box.width > 0 && box.height > 0)
        .filter(({ box }) => Math.round(box.height) < 44 || Math.round(box.width) < 44)
        .map(({ el, box }) => `${el.tagName} ${el.textContent.trim().slice(0, 20)} ${box.width}x${box.height}`);
}"""


def test_header_tabs_search_and_dialog_controls_are_44px_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
    assign_object_role(educator_user, organisation, "organisation_admin")
    page.set_viewport_size(_PHONE)

    page.goto(interface_url(live_server, organisation.slug, "cohorts"))
    assert page.evaluate(_SMALLEST_CONTROL) == []

    page.goto(interface_url(live_server, organisation.slug, f"cohorts/{cohort.pk}"))
    assert page.evaluate(_SMALLEST_CONTROL) == []

    page.goto(interface_url(live_server, organisation.slug, "cohorts"))
    page.get_by_role("button", name="Create cohort", exact=True).click()
    page.get_by_role("dialog", name="Create cohort").wait_for()
    assert page.evaluate(_SMALLEST_CONTROL) == []

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("button", name="Filter", exact=True).click()
    page.get_by_role("dialog", name="Filter").wait_for()
    assert page.evaluate(_SMALLEST_CONTROL) == []
