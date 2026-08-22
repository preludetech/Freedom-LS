import pytest
from playwright.sync_api import Page, expect

from ..conftest import (
    course_with_single_question_form,
    register_user_for_course,
    reverse_url,
)

# Dispatches a cancelable beforeunload and reports whether the runner's guard
# called preventDefault on it (i.e. whether the browser would show the native
# "Leave site?" prompt).
_BEFOREUNLOAD_PREVENTED = """() => {
    const e = new Event('beforeunload', {cancelable: true});
    window.dispatchEvent(e);
    return e.defaultPrevented;
}"""


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_submit_disarms_the_beforeunload_leave_prompt(
    live_server,
    logged_in_page: Page,
    logged_in_user,
):
    """Clicking Submit must not leave a "Leave site?" beforeunload prompt armed.

    Regression: the runner armed a window ``beforeunload`` guard that called
    ``preventDefault`` on every unload. Clicking Submit ran ``form.submit()``,
    which triggered that prompt; if the student then pressed Cancel on it the
    navigation aborted but the Submit button stayed latched disabled forever,
    with no way out but a reload. Deliberate navigation (Submit) must disarm the
    guard so no prompt — and therefore no trap — can occur.
    """
    course = course_with_single_question_form(
        "Submit Guard Course", "submit-guard-course"
    )
    register_user_for_course(course, logged_in_user)
    start_url = reverse_url(
        live_server,
        "learner_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    # Stub native form submission so the deliberate Submit does not navigate the
    # test page away — we only care that the click disarms the guard.
    logged_in_page.evaluate(
        """() => {
            window.__submitted = false;
            HTMLFormElement.prototype.submit = function () {
                window.__submitted = true;
            };
        }"""
    )

    # Answer the required question first — the final-page Next validates required
    # answers before opening the submit dialog (parity with intermediate pages).
    logged_in_page.get_by_text("Alpha", exact=True).click()

    # Answering is what arms the guard, and it is armed before the submit runs.
    assert logged_in_page.evaluate(_BEFOREUNLOAD_PREVENTED) is True

    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_role("button", name="Submit", exact=True).click()

    # The deliberate submit ran...
    assert logged_in_page.evaluate("() => window.__submitted") is True
    # ...and disarmed the beforeunload guard, so no "Leave site?" prompt fires.
    assert logged_in_page.evaluate(_BEFOREUNLOAD_PREVENTED) is False


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_untouched_runner_page_leaves_the_leave_prompt_disarmed(
    live_server,
    logged_in_page: Page,
    logged_in_user,
):
    """Opening a quiz and changing your mind must not earn a browser warning.

    The guard exists to protect unsaved answers. On a freshly loaded page there
    are none, so warning about them is a prompt the learner has not earned.
    """
    course = course_with_single_question_form(
        "Untouched Guard Course", "untouched-guard-course"
    )
    register_user_for_course(course, logged_in_user)
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    assert logged_in_page.evaluate(_BEFOREUNLOAD_PREVENTED) is False


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_answering_a_question_arms_the_leave_prompt(
    live_server,
    logged_in_page: Page,
    logged_in_user,
):
    """Once there is an unsaved answer on the page, leaving should still warn."""
    course = course_with_single_question_form(
        "Dirty Guard Course", "dirty-guard-course"
    )
    register_user_for_course(course, logged_in_user)
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    logged_in_page.get_by_text("Alpha", exact=True).click()

    assert logged_in_page.evaluate(_BEFOREUNLOAD_PREVENTED) is True


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_submit_navigates_to_form_completion(
    live_server,
    logged_in_page: Page,
    logged_in_user,
):
    """A deliberate Submit reaches the form-complete page (end-to-end smoke)."""
    # Accept any beforeunload that may still surface so navigation proceeds.
    logged_in_page.on("dialog", lambda dialog: dialog.accept())

    course = course_with_single_question_form(
        "Submit Flow Course", "submit-flow-course"
    )
    register_user_for_course(course, logged_in_user)
    start_url = reverse_url(
        live_server,
        "learner_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    logged_in_page.get_by_text("Alpha", exact=True).click()
    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_role("button", name="Submit", exact=True).click()

    complete_url = reverse_url(
        live_server,
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    expect(logged_in_page).to_have_url(complete_url)
