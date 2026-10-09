"""Tests for the <c-dropdown-menu /> cotton component."""

import re

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _render(template_string: str) -> str:
    processed = _cotton_compiler.process(template_string)
    t = Template(processed)
    return t.render(Context())


def _element_with_attribute(html: str, attribute: str) -> str:
    """The opening tag of the first element carrying ``attribute``."""
    match = re.search(r"<[a-zA-Z]+[^>]*" + re.escape(attribute) + r"[^>]*>", html)
    assert match is not None, f"No element carrying {attribute} in:\n{html}"
    return match.group(0)


class TestDropdownMenuComponent:
    """Rendering behaviour of <c-dropdown-menu />."""

    def test_panel_exposes_a_menu_role(self) -> None:
        """The menu items need an owning container with role="menu"."""
        result = _render(
            "<c-dropdown-menu><c-button dropdown='true'>Item</c-button></c-dropdown-menu>"
        )
        assert 'role="menu"' in result

    def test_menu_takes_its_accessible_name_from_the_trigger_label(self) -> None:
        result = _render(
            '<c-dropdown-menu aria_label="Switch organisation">'
            "<c-button dropdown='true'>Item</c-button>"
            "</c-dropdown-menu>"
        )
        menu = _element_with_attribute(result, 'role="menu"')
        assert 'aria-label="Switch organisation"' in menu

    def test_menu_label_overrides_the_trigger_label(self) -> None:
        result = _render(
            '<c-dropdown-menu aria_label="Open user menu for Ada" '
            'menu_label="User menu">'
            "<c-button dropdown='true'>Item</c-button>"
            "</c-dropdown-menu>"
        )
        menu = _element_with_attribute(result, 'role="menu"')
        assert 'aria-label="User menu"' in menu


class TestDropdownButtonRole:
    """<c-button dropdown="true" /> is a menu item; a plain button is not."""

    @pytest.mark.parametrize(
        "markup",
        [
            "<c-button dropdown='true'>Sign Out</c-button>",
            "<c-button dropdown='true' href='/profile/'>Profile</c-button>",
        ],
        ids=["button", "link"],
    )
    def test_dropdown_button_carries_the_menuitem_role(self, markup: str) -> None:
        assert 'role="menuitem"' in _render(markup)

    def test_plain_button_carries_no_menuitem_role(self) -> None:
        result = _render("<c-button>Save</c-button>")
        assert "menuitem" not in result
