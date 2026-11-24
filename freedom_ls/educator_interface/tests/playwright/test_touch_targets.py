"""Touch targets on the educator interface: 44px to the touch below md.

A button keeps its desktop look on a phone; an invisible ::after hit area
gives it the 44px height. Only a dialog footer's buttons are 44px to the eye.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from playwright.sync_api import Page
from pytest_django.live_server_helper import LiveServer

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.base.tests.tailwind_build import build_fls_css_with_theme
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


# Heights of the First Class theme's buttons before the label alignment rule,
# in px. The alignment rule moves the label, never the button's box.
DEFAULT_BUTTON_HEIGHT = 44
SMALL_BUTTON_HEIGHT = 32
TABLE_BUTTON_HEIGHT = 32
FOOTER_BUTTON_HEIGHT = 44


def _font_base64() -> str:
    return base64.b64encode(_FIXTURE_FONT.read_bytes()).decode()


_VARIANTS = ["primary", "secondary", "ghost", "link", "accent", "success", "error"]
_FIXTURE_FONT = Path(__file__).parents[3] / "base/tests/fonts/DMSans-SemiBold.ttf"


def _button(variant: str, extra: str = "") -> str:
    return (
        f'<button class="btn btn-{variant} {extra}" data-variant="{variant}">'
        f'<span class="label">Save changes</span></button>'
    )


def _fixture_page() -> str:
    default = "".join(_button(v) for v in _VARIANTS)
    small = "".join(_button(v, "btn-sm") for v in _VARIANTS)
    in_table = "".join(_button(v) for v in _VARIANTS)
    in_footer = "".join(_button(v) for v in _VARIANTS)
    return f"""
    <div id="default">{default}</div>
    <div id="small">{small}</div>
    <table class="panel-data-table"><tbody><tr><td id="table">{in_table}</td></tr></tbody></table>
    <div data-modal-footer id="footer">{in_footer}</div>
    """


_MEASURE_LABEL_OFFSETS = """(containerId) => {
    const canvas = document.createElement("canvas").getContext("2d");
    return [...document.querySelectorAll(`#${containerId} .btn`)].map((button) => {
        const label = button.querySelector(".label");
        const probe = document.createElement("span");
        probe.style.cssText = "display: inline-block; height: 0; width: 0";
        label.appendChild(probe);
        const baseline = probe.getBoundingClientRect().bottom;
        probe.remove();
        const style = getComputedStyle(label);
        canvas.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
        const capHeight = canvas.measureText("H").actualBoundingBoxAscent;
        const box = button.getBoundingClientRect();
        return {
            variant: button.dataset.variant,
            height: box.height,
            offset: baseline - capHeight / 2 - (box.top + box.height / 2),
        };
    });
}"""

_CONTAINERS = {
    "default": "DEFAULT_BUTTON_HEIGHT",
    "small": "SMALL_BUTTON_HEIGHT",
    "table": "TABLE_BUTTON_HEIGHT",
    "footer": "FOOTER_BUTTON_HEIGHT",
}


def _label_problems(page: Page, heights: dict[str, int]) -> list[str]:
    problems = []
    for container, name in _CONTAINERS.items():
        for result in page.evaluate(_MEASURE_LABEL_OFFSETS, container):
            where = f"{container}/{result['variant']}"
            if abs(result["offset"]) > 1:
                problems.append(f"{where} label off centre by {result['offset']:.2f}px")
            if round(result["height"]) != heights[name]:
                problems.append(f"{where} height {result['height']}")
    return problems


@pytest.fixture(scope="module")
def first_class_css(tmp_path_factory: pytest.TempPathFactory) -> str:
    build_dir = tmp_path_factory.mktemp("first_class_buttons")
    (build_dir / "built.css").write_text(
        build_fls_css_with_theme(build_dir, "first_class")
    )
    return str(build_dir / "built.css")


@pytest.mark.parametrize(
    "with_dm_sans", [False, True], ids=["fallback-font", "dm-sans"]
)
def test_button_labels_are_centred_in_the_first_class_theme(
    page: Page, first_class_css: str, with_dm_sans: bool
) -> None:
    """A label's cap-height centre sits within 1px of its button's centre, at the
    button's usual height, for every variant and size."""
    page.set_content(_fixture_page())
    page.add_style_tag(path=first_class_css)
    if with_dm_sans:
        page.add_style_tag(
            content='@font-face { font-family: "DM Sans"; font-weight: 100 900; '
            f'src: url("data:font/ttf;base64,{_font_base64()}"); }}'
        )
        page.evaluate('document.fonts.load("600 14px \\"DM Sans\\"")')
    page.evaluate("document.fonts.ready")
    heights = {
        "DEFAULT_BUTTON_HEIGHT": DEFAULT_BUTTON_HEIGHT,
        "SMALL_BUTTON_HEIGHT": SMALL_BUTTON_HEIGHT,
        "TABLE_BUTTON_HEIGHT": TABLE_BUTTON_HEIGHT,
        "FOOTER_BUTTON_HEIGHT": FOOTER_BUTTON_HEIGHT,
    }

    assert _label_problems(page, heights) == []
