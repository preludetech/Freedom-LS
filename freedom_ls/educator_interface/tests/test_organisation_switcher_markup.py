"""Markup-level accessibility guarantees of the organisation switcher partial.

Rendered straight from the template so the assertions stay about the markup
the switcher emits, not about which view happened to build the context.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import cast

import pytest

from django.template.loader import render_to_string

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

TEMPLATE = "educator_interface/partials/organisation_switcher.html"

_OPTION_RE = re.compile(r'<button[^>]*role="menuitemradio".*?</button>', re.DOTALL)


def _render(current: Organisation, accessible: list[Organisation]) -> str:
    request = SimpleNamespace(
        organisation=current,
        accessible_organisations=accessible,
        path_string="cohorts",
    )
    return render_to_string(TEMPLATE, {"request": request})


def _options(html: str) -> list[str]:
    return _OPTION_RE.findall(html)


def _checked_option(html: str) -> str:
    return next(o for o in _options(html) if 'aria-checked="true"' in o)


def _unchecked_options(html: str) -> list[str]:
    return [o for o in _options(html) if 'aria-checked="false"' in o]


@pytest.fixture
def two_organisations(mock_site_context) -> tuple[Organisation, Organisation]:
    current = cast(Organisation, OrganisationFactory(name="Northside High School"))
    other = cast(Organisation, OrganisationFactory(name="Southgate Academy"))
    return current, other


@pytest.mark.django_db
class TestCurrentOrganisationIndicator:
    def test_current_organisation_renders_a_visible_check(
        self, two_organisations
    ) -> None:
        current, other = two_organisations

        html = _render(current, [current, other])

        assert "<svg" in _checked_option(html)

    def test_other_organisations_render_no_check(self, two_organisations) -> None:
        current, other = two_organisations

        html = _render(current, [current, other])

        assert "<svg" not in _unchecked_options(html)[0]

    def test_every_option_reserves_the_indicator_space(self, two_organisations) -> None:
        """The indicator slot is on unchecked options too, so labels stay
        aligned with the checked one."""
        current, other = two_organisations

        html = _render(current, [current, other])

        assert all('aria-hidden="true"' in option for option in _options(html))

    def test_the_check_is_hidden_from_assistive_technology(
        self, two_organisations
    ) -> None:
        """aria-checked already conveys the state; the icon must not
        also land in the option's accessible name."""
        current, other = two_organisations

        checked = _checked_option(_render(current, [current, other]))

        assert checked.index('aria-hidden="true"') < checked.index("<svg")


@pytest.mark.django_db
class TestSwitcherMenuStructure:
    def test_options_are_owned_by_a_menu(self, two_organisations) -> None:
        current, other = two_organisations

        html = _render(current, [current, other])

        assert 'role="menu"' in html

    def test_the_menu_is_named_for_switching_organisation(
        self, two_organisations
    ) -> None:
        current, other = two_organisations

        html = _render(current, [current, other])

        assert 'aria-label="Switch organisation"' in html
