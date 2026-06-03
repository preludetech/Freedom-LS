import pytest
from playwright.sync_api import Page, expect

from conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)

# Dispatches a cancelable beforeunload and reports whether the runner's guard
# called preventDefault on it (i.e. whether the browser would show the native
# "Leave site?" prompt).
_BEFOREUNLOAD_PREVENTED = """() => {
    const e = new Event('beforeunload', {cancelable: true});
    window.dispatchEvent(e);
    return e.defaultPrevented;
}"""


def _single_question_form(course_title: str, course_slug: str):
    """A course whose first item is a one-page, one-question form."""
    course = CourseFactory(title=course_title, slug=course_slug)
    form = FormFactory(title=f"{course_title} Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    question = FormQuestionFactory(
        form_page=form_page, type="multiple_choice", question="Pick one", order=0
    )
    QuestionOptionFactory(question=question, text="Alpha", order=0)
    QuestionOptionFactory(question=question, text="Beta", order=1)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    return course


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_submit_disarms_the_beforeunload_leave_prompt(
    live_server,
    logged_in_page: Page,
):
    """Clicking Submit must not leave a "Leave site?" beforeunload prompt armed.

    Regression: the runner armed a window ``beforeunload`` guard that called
    ``preventDefault`` on every unload. Clicking Submit ran ``form.submit()``,
    which triggered that prompt; if the student then pressed Cancel on it the
    navigation aborted but the Submit button stayed latched disabled forever,
    with no way out but a reload. Deliberate navigation (Submit) must disarm the
    guard so no prompt — and therefore no trap — can occur.
    """
    course = _single_question_form("Submit Guard Course", "submit-guard-course")
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    # Before any deliberate navigation the guard is armed for accidental leaves.
    assert logged_in_page.evaluate(_BEFOREUNLOAD_PREVENTED) is True

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

    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_role("button", name="Submit", exact=True).click()

    # The deliberate submit ran...
    assert logged_in_page.evaluate("() => window.__submitted") is True
    # ...and disarmed the beforeunload guard, so no "Leave site?" prompt fires.
    assert logged_in_page.evaluate(_BEFOREUNLOAD_PREVENTED) is False


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_submit_navigates_to_form_completion(
    live_server,
    logged_in_page: Page,
):
    """A deliberate Submit reaches the form-complete page (end-to-end smoke)."""
    # Accept any beforeunload that may still surface so navigation proceeds.
    logged_in_page.on("dialog", lambda dialog: dialog.accept())

    course = _single_question_form("Submit Flow Course", "submit-flow-course")
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    logged_in_page.get_by_text("Alpha", exact=True).click()
    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_role("button", name="Submit", exact=True).click()

    complete_url = reverse_url(
        live_server,
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    expect(logged_in_page).to_have_url(complete_url)
