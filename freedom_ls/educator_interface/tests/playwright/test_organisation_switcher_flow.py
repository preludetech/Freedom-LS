"""The organisation switcher's popover with more organisations than fit on screen.

Where a fixed popover lands and whether its options can be reached is layout
the Django test client never runs.
"""

from __future__ import annotations

from typing import cast

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_DESKTOP = {"width": 1440, "height": 900}
_ORGANISATION_COUNT = 20


def test_a_long_organisation_list_opens_inside_the_viewport(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """With more organisations than fit below the trigger, the popover used to
    flip above it with no room there either, so its top sat far off the top of
    the screen and most organisations could not be reached."""
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)
    grantor = LearnerFactory(user__superuser=True).user
    organisations = [
        cast(Organisation, OrganisationFactory(name=f"Org {index:02d}"))
        for index in range(_ORGANISATION_COUNT)
    ]
    for organisation in organisations:
        assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisations[0].slug, "learners"))

    page.get_by_role("button", name="Switch organisation").click()
    menu = page.get_by_role("menu", name="Switch organisation")
    expect(menu).to_be_visible()

    panel_box = page.evaluate(
        "() => { const r = document.querySelector('[role=menu][aria-label=\"Switch organisation\"]')"
        ".closest('.dropdown-panel').getBoundingClientRect();"
        " return {top: r.top, bottom: r.bottom}; }"
    )
    assert panel_box["top"] >= 0
    assert panel_box["bottom"] <= _DESKTOP["height"]

    last = page.get_by_role("menuitemradio", name=f"Org {_ORGANISATION_COUNT - 1:02d}")
    last.scroll_into_view_if_needed()
    expect(last).to_be_in_viewport()
