"""Tests for the <c-dropdown-menu /> cotton component."""

import re

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _element_with_attribute(html: str, attribute: str) -> str:
    """The opening tag of the first element carrying ``attribute``."""
    match = re.search(r"<[a-zA-Z]+[^>]*" + re.escape(attribute) + r"[^>]*>", html)
    assert match is not None, f"No element carrying {attribute} in:\n{html}"
    return match.group(0)


class TestDropdownMenuComponent:
    """Rendering behaviour of <c-dropdown-menu />."""

    def _render(self, template_string: str) -> str:
        processed = _cotton_compiler.process(template_string)
        t = Template(processed)
        return t.render(Context())

    def test_authoring_comments_do_not_leak_into_output(self) -> None:
        """Internal authoring comments must not reach the rendered HTML."""
        result = self._render(
            "<c-dropdown-menu><c-button dropdown='true'>Item</c-button></c-dropdown-menu>"
        )
        assert "3-dots menu button" not in result
        assert "Dropdown menu" not in result
        assert "<!--" not in result

    def test_panel_exposes_a_menu_role(self) -> None:
        """The menu items need an owning container with role="menu"."""
        result = self._render(
            "<c-dropdown-menu><c-button dropdown='true'>Item</c-button></c-dropdown-menu>"
        )
        assert 'role="menu"' in result

    def test_menu_takes_its_accessible_name_from_the_trigger_label(self) -> None:
        result = self._render(
            '<c-dropdown-menu aria_label="Switch organisation">'
            "<c-button dropdown='true'>Item</c-button>"
            "</c-dropdown-menu>"
        )
        menu = _element_with_attribute(result, 'role="menu"')
        assert 'aria-label="Switch organisation"' in menu

    def test_menu_label_overrides_the_trigger_label(self) -> None:
        result = self._render(
            '<c-dropdown-menu aria_label="Open user menu for Ada" '
            'menu_label="User menu">'
            "<c-button dropdown='true'>Item</c-button>"
            "</c-dropdown-menu>"
        )
        menu = _element_with_attribute(result, 'role="menu"')
        assert 'aria-label="User menu"' in menu


class TestDropdownButtonRole:
    """<c-button dropdown="true" /> is a menu item; a plain button is not."""

    def _render(self, template_string: str) -> str:
        processed = _cotton_compiler.process(template_string)
        t = Template(processed)
        return t.render(Context())

    def test_dropdown_button_carries_the_menuitem_role(self) -> None:
        result = self._render("<c-button dropdown='true'>Sign Out</c-button>")
        assert 'role="menuitem"' in result

    def test_dropdown_link_carries_the_menuitem_role(self) -> None:
        result = self._render(
            "<c-button dropdown='true' href='/profile/'>Profile</c-button>"
        )
        assert 'role="menuitem"' in result

    def test_plain_button_carries_no_menuitem_role(self) -> None:
        result = self._render("<c-button>Save</c-button>")
        assert "menuitem" not in result
