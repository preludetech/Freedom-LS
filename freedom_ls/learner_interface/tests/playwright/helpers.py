"""Steps a learner takes through a form, shared by the learner Playwright flows."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.models import Course

# Dispatches a cancelable beforeunload and reports whether the runner's guard
# called preventDefault on it, i.e. whether the browser would show its native
# "Leave site?" prompt.
BEFOREUNLOAD_PREVENTED = """() => {
    const e = new Event('beforeunload', {cancelable: true});
    window.dispatchEvent(e);
    return e.defaultPrevented;
}"""

# Whether the document's active element is inside the submit dialog panel.
FOCUS_IN_SUBMIT_DIALOG = """() => {
    const panel = document.querySelector('[aria-labelledby="submit-dialog-title"]');
    return panel.contains(document.activeElement);
}"""


def form_item_url(
    live_server: object, course: Course, view_name: str, **kwargs: int
) -> str:
    """The absolute URL of a learner_interface form view for the course's first item."""
    return str(
        reverse_url(
            live_server,
            f"learner_interface:{view_name}",
            kwargs={"course_slug": course.slug, "index": 1, **kwargs},
        )
    )


def navigate_to_form(page: Page, live_server: object, course: Course) -> str:
    """Open the form's landing page and return its URL."""
    url = form_item_url(live_server, course, "view_course_item")
    page.goto(url)
    return url


def start_form(page: Page) -> None:
    """Follow the landing page's Start (or Continue) button to the first runner page."""
    page.get_by_role("link", name=re.compile(r"^(Start|Continue) Form$")).click()
    expect(page).to_have_url(re.compile(r"/fill_form/1$"))


def answer_multiple_choice_question(page: Page, option_text: str) -> None:
    """Select the option with this exact text by clicking its visible label."""
    page.get_by_text(option_text, exact=True).click()


def click_next(page: Page) -> None:
    """Press the runner's Next button."""
    page.get_by_role("button", name="Next").click()


def submit_form(page: Page) -> None:
    """Open the final page's submit dialog and confirm it."""
    click_next(page)
    dialog = page.get_by_role("dialog", name="Ready to submit?")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Submit", exact=True).click()
