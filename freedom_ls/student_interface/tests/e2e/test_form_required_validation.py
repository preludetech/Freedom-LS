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


def _single_required_question_form(course_title: str, course_slug: str):
    """A course whose first item is a one-page form with one required question."""
    course = CourseFactory(title=course_title, slug=course_slug)
    form = FormFactory(title=f"{course_title} Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    question = FormQuestionFactory(
        form_page=form_page,
        type="multiple_choice",
        question="Pick one",
        required=True,
        order=0,
    )
    QuestionOptionFactory(question=question, text="Alpha", order=0)
    QuestionOptionFactory(question=question, text="Beta", order=1)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    return course


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_final_page_submit_dialog_blocked_until_required_answered(
    live_server,
    logged_in_page: Page,
):
    """The final-page Next must not open the submit dialog while a required
    question is unanswered, matching the intermediate-page Next buttons.

    The final page submits via JS (form.submit()), which skips HTML5 constraint
    validation, while the server silently accepts and scores blank answers as 0.
    openSubmitDialog therefore runs reportValidity() first: with a required
    question unanswered the submit dialog stays closed; once answered it opens.
    """
    course = _single_required_question_form(
        "Required Validation Course", "required-validation-course"
    )
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    dialog = logged_in_page.locator('[aria-labelledby="submit-dialog-title"]')

    # Required question unanswered → clicking Next must NOT open the dialog.
    logged_in_page.get_by_role("button", name="Next").click()
    expect(dialog).to_be_hidden()

    # Answer the required question, then Next opens the submit dialog.
    logged_in_page.get_by_text("Alpha", exact=True).click()
    logged_in_page.get_by_role("button", name="Next").click()
    expect(dialog).to_be_visible()
