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


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_answered_count_reflects_answers_filled_in_on_the_current_page(
    live_server,
    logged_in_page: Page,
):
    """The runner's "answered" tally counts answers filled in on the page, live.

    Regression: the count was rendered from persisted answers only, so on the
    page the student was filling it stayed at 0 (the submit modal showed
    "0 Answered" even after every question was answered). It must now reflect
    answers present in the browser — updating as the student answers, and
    correct in the "Ready to submit?" modal.
    """
    course = CourseFactory(title="Answer Count Course", slug="answer-count-course")
    form = FormFactory(title="Answer Count Form")
    page = FormPageFactory(form=form, order=0, title="Only Page")

    # Three questions across the input types the counter must handle.
    mc = FormQuestionFactory(
        form_page=page, type="multiple_choice", question="Pick one", order=0
    )
    QuestionOptionFactory(question=mc, text="Alpha", order=0)
    QuestionOptionFactory(question=mc, text="Beta", order=1)

    FormQuestionFactory(
        form_page=page, type="short_text", question="Your name", order=1
    )

    cb = FormQuestionFactory(
        form_page=page, type="checkboxes", question="Pick many", order=2
    )
    QuestionOptionFactory(question=cb, text="Red", order=0)
    QuestionOptionFactory(question=cb, text="Green", order=1)

    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)

    # form_start creates the FormProgress for the logged-in user, then redirects
    # to the fill page.
    start_url = reverse_url(
        live_server,
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(start_url)

    summary = logged_in_page.get_by_test_id("answered-summary")
    expect(summary).to_have_text("0 of 3 answered")

    # Answer each question and watch the live tally climb.
    # exact=True so option text does not substring-match words like "answe(red)".
    logged_in_page.get_by_text("Alpha", exact=True).click()
    expect(summary).to_have_text("1 of 3 answered")

    logged_in_page.get_by_label("Your name").fill("Sheena")
    expect(summary).to_have_text("2 of 3 answered")

    logged_in_page.get_by_text("Red", exact=True).click()
    expect(summary).to_have_text("3 of 3 answered")

    # Open the "Ready to submit?" modal — it must show the same honest count.
    logged_in_page.get_by_role("button", name="Next").click()
    expect(logged_in_page.get_by_test_id("modal-answered-count")).to_have_text("3")
