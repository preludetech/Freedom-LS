"""The panel template rules, applied to the educator interface's own templates.

The rules are the framework's (`template_rules`); this module feeds them the
educator templates, dialogs and Python files, which spell the components `c-button`,
`c-button-group` and `c-callout`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import freedom_ls.educator_interface as educator_interface
import freedom_ls.panel_framework as panel_framework
from freedom_ls.panel_framework.tests.invariants import template_rules

EDUCATOR_ROOT = Path(educator_interface.__file__).resolve().parent
EDUCATOR_TEMPLATES_DIR = EDUCATOR_ROOT / "templates" / "educator_interface"
EDUCATOR_MODAL_DIR = EDUCATOR_TEMPLATES_DIR / "modal"
# Tests and migrations are not interface code; the rule is about modules that build actions.
_SKIPPED_DIRS = {"tests", "migrations"}
EDUCATOR_PYTHON_FILES = sorted(
    path
    for path in EDUCATOR_ROOT.rglob("*.py")
    if _SKIPPED_DIRS.isdisjoint(path.relative_to(EDUCATOR_ROOT).parts)
)
FRAMEWORK_TEMPLATES_DIR = Path(panel_framework.__file__).resolve().parent / "templates"
FRAMEWORK_MODAL_HOST = (
    FRAMEWORK_TEMPLATES_DIR / "panel_framework" / "partials" / "modal_host.html"
)

DIALOGS = tuple(sorted(EDUCATOR_MODAL_DIR.glob("*.html")))
WIDE_FRAGMENTS = frozenset({"content_preview.html", "course_details_preview.html"})
# Dialogs that do not take the header, body and footer parts, each with its reason.
DIALOG_PART_EXEMPTIONS: dict[str, str] = {
    "conversation_oversight.html": "the thread pane brings its own edge-to-edge layout",
}
# `find` matches the first element only, so a form with several submit buttons
# names all of them through the modal body instead.
MULTI_SUBMIT_DIALOGS = {"move_confirmation.html", "add_staff_member.html"}
FORBIDDEN_IN_DIALOGS = template_rules.forbidden_in_dialogs("button")


def test_no_educator_template_hand_styles_a_control_link() -> None:
    assert template_rules.hand_styled_control_links(EDUCATOR_TEMPLATES_DIR, ()) == []


def test_no_educator_template_hand_writes_a_table() -> None:
    assert template_rules.hand_written_tables(EDUCATOR_TEMPLATES_DIR, ()) == []


def test_no_educator_anchor_with_visible_text_lacks_its_own_classes() -> None:
    assert template_rules.anchors_without_classes(EDUCATOR_TEMPLATES_DIR, ()) == []


def test_no_educator_button_hand_writes_a_touch_height() -> None:
    offenders = template_rules.hand_written_touch_heights(
        EDUCATOR_TEMPLATES_DIR, "button", "btn", "dropdown-menu"
    )

    assert offenders == []


def test_every_educator_expand_chevron_turns_when_its_control_opens() -> None:
    assert template_rules.expand_chevrons_that_do_not_turn(EDUCATOR_TEMPLATES_DIR) == []


def test_only_the_content_previews_declare_the_wide_dialog_size() -> None:
    declaring = template_rules.dialogs_declaring_the_wide_size(
        DIALOGS, FRAMEWORK_MODAL_HOST
    )

    assert declaring == WIDE_FRAGMENTS


def test_every_educator_dialog_ends_in_the_modal_footer_not_a_button_group() -> None:
    assert len(DIALOGS) > 10
    assert template_rules.dialogs_using_a_button_group(DIALOGS, "button-group") == []


def test_every_educator_dialog_is_a_header_a_body_and_a_footer() -> None:
    offenders = template_rules.dialogs_missing_a_part(
        DIALOGS, FRAMEWORK_TEMPLATES_DIR, DIALOG_PART_EXEMPTIONS
    )

    assert offenders == []


def test_no_educator_dialog_footer_sits_inside_the_body() -> None:
    offenders = template_rules.dialogs_with_a_footer_inside_the_body(
        DIALOGS, FRAMEWORK_TEMPLATES_DIR
    )

    assert offenders == []


def test_no_educator_dialog_pads_its_own_body() -> None:
    offenders = template_rules.dialogs_padding_their_own_body(
        DIALOGS, DIALOG_PART_EXEMPTIONS
    )

    assert offenders == []


@pytest.mark.parametrize("path", DIALOGS, ids=lambda path: path.name)
def test_every_educator_dialog_renders_one_modal_footer_outside_its_body(
    path: Path,
) -> None:
    assert template_rules.dialog_footer_problems(path) == []


@pytest.mark.parametrize("rule", sorted(FORBIDDEN_IN_DIALOGS))
def test_no_educator_dialog_hand_writes_what_a_component_owns(rule: str) -> None:
    offenders = template_rules.dialogs_matching(DIALOGS, FORBIDDEN_IN_DIALOGS[rule])

    assert offenders == []


def test_every_educator_dialog_loading_text_ends_in_the_ellipsis_character() -> None:
    assert template_rules.loading_texts_ending_in_three_dots(DIALOGS) == []


def test_every_educator_dialog_disables_only_its_own_submit_buttons() -> None:
    offenders = template_rules.dialogs_disabling_more_than_their_submit_buttons(
        DIALOGS, MULTI_SUBMIT_DIALOGS
    )

    assert offenders == []


def test_no_educator_dialog_form_with_a_find_selector_holds_a_requesting_element() -> (
    None
):
    assert template_rules.requesting_elements_inside_a_find_form(DIALOGS) == []


def test_no_educator_module_sets_the_modal_trigger_template_by_hand() -> None:
    """The framework's modal action classes own the modal trigger, so an app
    extends one of them instead of naming the template."""
    offenders = template_rules.python_files_setting_the_modal_trigger_by_hand(
        EDUCATOR_PYTHON_FILES
    )

    assert offenders == []


def test_educator_python_files_include_the_panel_modules() -> None:
    assert EDUCATOR_ROOT / "panels" / "learner" / "actions.py" in EDUCATOR_PYTHON_FILES
