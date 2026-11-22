"""Touch targets on the educator interface: 44px to the touch below md.

A button keeps its desktop look on a phone; an invisible ::after hit area
gives it the 44px height. Only a dialog footer's buttons are 44px to the eye.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page
from pytest_django.live_server_helper import LiveServer

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
    // A button's hit area is the taller of its box and its ::after.
    const hitHeight = (el, box) => {
        const after = getComputedStyle(el, "::after");
        const afterHeight = after.content === "none" ? 0 : parseFloat(after.height) || 0;
        return Math.max(box.height, afterHeight);
    };
    return [...controls]
        .map((el) => ({ el, box: hitTarget(el).getBoundingClientRect() }))
        .filter(({ box }) => box.width > 0 && box.height > 0)
        .filter(({ el, box }) => Math.round(hitHeight(el, box)) < 44 || Math.round(box.width) < 44)
        .map(({ el, box }) => `${el.tagName} ${el.textContent.trim().slice(0, 20)} ${box.width}x${box.height}`);
}"""

_BUTTON_HEIGHT = """(button) => button.getBoundingClientRect().height"""


def test_touch_targets_flow(
    live_server: LiveServer,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """On a phone no header, tab, search or dialog control is under 44px to
    the touch, a small button keeps its desktop look (under 40px tall) and a
    dialog footer's Cancel is 44px tall."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
    assign_object_role(educator_user, organisation, "organisation_admin")
    page.set_viewport_size(_PHONE)

    page.goto(interface_url(live_server, organisation.slug, "cohorts"))
    assert page.evaluate(_SMALLEST_CONTROL) == [], "cohorts page has a small control"

    page.goto(interface_url(live_server, organisation.slug, f"cohorts/{cohort.pk}"))
    assert page.evaluate(_SMALLEST_CONTROL) == [], (
        "cohort detail page has a small control"
    )

    page.goto(interface_url(live_server, organisation.slug, "cohorts"))
    page.get_by_role("button", name="Create cohort", exact=True).first.click()
    dialog = page.get_by_role("dialog", name="Create cohort")
    dialog.wait_for()
    assert page.evaluate(_SMALLEST_CONTROL) == [], "create dialog has a small control"
    cancel = dialog.locator("footer").get_by_role("button", name="Cancel")
    assert round(cancel.evaluate(_BUTTON_HEIGHT)) >= 44, (
        "dialog footer Cancel under 44px tall"
    )

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    filter_button = page.get_by_role("button", name="Filter", exact=True)
    assert filter_button.evaluate(_BUTTON_HEIGHT) < 40, (
        "Filter button taller than its desktop look"
    )
    filter_button.click()
    page.get_by_role("dialog", name="Filter").wait_for()
    assert page.evaluate(_SMALLEST_CONTROL) == [], "filter dialog has a small control"
