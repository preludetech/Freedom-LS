import pytest
from playwright.sync_api import Page

from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy

from ..conftest import course_with_form, register_user_for_course, reverse_url


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_leave_and_submit_scores_the_answers_on_the_page_being_left(
    live_server,
    logged_in_page: Page,
    logged_in_user,
):
    """Leaving a submit-on-exit quiz must score what the learner just answered.

    Regression (QA report bug 2): the exit dialog posted its own empty form, so
    the current page's answers were discarded and the attempt scored 0% — and a
    submit-on-exit form cannot be re-sat, so that failing grade was permanent.

    Both questions here are required and only one is answered, which also proves
    the exit path is not gated by required-answer validation: leaving scores the
    attempt as it stands.
    """
    form = FormFactory(
        title="Exit Quiz",
        slug="exit-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=50,
        submit_on_exit=True,
    )
    page = FormPageFactory(form=form, title="Page 1", order=0)
    answered = FormQuestionFactory(
        form_page=page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0,
        required=True,
    )
    QuestionOptionFactory(question=answered, text="4", correct=True, order=0)
    QuestionOptionFactory(question=answered, text="5", correct=False, order=1)
    skipped = FormQuestionFactory(
        form_page=page,
        question="What is 3+3?",
        type="multiple_choice",
        order=1,
        required=True,
    )
    QuestionOptionFactory(question=skipped, text="6", correct=True, order=0)

    course = course_with_form(form, title="Exit Course", slug="exit-course")
    register_user_for_course(course, logged_in_user)

    logged_in_page.goto(
        reverse_url(
            live_server,
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    logged_in_page.locator("[data-testid='start-form-button']").click()
    logged_in_page.wait_for_url("**/fill_form/**")

    # Answer the first question only. Radio inputs are sr-only; click the label.
    correct = answered.options.get(correct=True)
    logged_in_page.locator(f"label[for='q{answered.id}_opt{correct.id}']").click()

    logged_in_page.locator("button[aria-label='Exit test']").click()
    logged_in_page.locator("[data-testid='leave-and-submit-button']").click()
    logged_in_page.wait_for_url("**/complete")

    # 1 of 2 correct — not the 0 of 2 the discarded-answers bug produced.
    score = logged_in_page.locator("[data-testid='quiz-score']")
    assert "1" in score.inner_text()
    assert "2" in score.inner_text()
