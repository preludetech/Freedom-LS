import pytest
from playwright.sync_api import Page, expect

from conftest import course_with_single_question_form, reverse_url

# Returns whether the document's active element is inside the submit dialog
# panel (identified by its aria-labelledby). Used to assert focus is moved into
# the dialog on open and stays trapped there while tabbing.
_FOCUS_IN_SUBMIT_DIALOG = """() => {
    const panel = document.querySelector('[aria-labelledby="submit-dialog-title"]');
    return panel.contains(document.activeElement);
}"""


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_submit_dialog_moves_focus_in_and_traps_tab_within_the_dialog(
    live_server,
    logged_in_page: Page,
):
    """The submit dialog must move focus into the dialog and trap Tab within it.

    Regression (QA report bug 2): ``examRunnerForm`` wraps the whole runner body,
    and the shared focus trap queried focusables on its ``$el`` — so the submit
    dialog's trap spanned every runner control (~19 elements). Focus stayed on
    Next on open, and Shift+Tab from the first dialog control escaped the modal to
    controls behind it. The trap must be scoped to the dialog panel: focus moves
    in on open, and Tab/Shift+Tab cycle only the dialog's own controls.
    """
    course = course_with_single_question_form("Focus Trap Course", "focus-trap-course")
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    # Answer the required question first — the final-page Next validates required
    # answers before opening the submit dialog (parity with intermediate pages).
    logged_in_page.get_by_text("Alpha", exact=True).click()

    # Single page → the first Next opens the submit dialog.
    logged_in_page.get_by_role("button", name="Next").click()

    dialog = logged_in_page.locator('[aria-labelledby="submit-dialog-title"]')
    expect(dialog).to_be_visible()

    # Focus moved into the dialog panel on open (not left on the Next trigger).
    assert logged_in_page.evaluate(_FOCUS_IN_SUBMIT_DIALOG) is True

    # Shift+Tab from the dialog's first control wraps to the last control and
    # stays inside the dialog — it must NOT escape to the runner's Next button.
    logged_in_page.keyboard.press("Shift+Tab")
    assert logged_in_page.evaluate(_FOCUS_IN_SUBMIT_DIALOG) is True
    expect(
        logged_in_page.get_by_role("button", name="Submit", exact=True)
    ).to_be_focused()
