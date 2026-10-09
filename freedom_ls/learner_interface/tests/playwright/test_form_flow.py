"""Browser flows for a learner working through forms and quizzes.

The server-rendered facts (landing page copy, scores, the incorrect-answer
review, which button resumes) are covered by the Django test client in
``views/test_form_runner.py``. What only a browser shows is covered here: the
live answered tally, required-answer validation before the submit dialog opens,
the leave prompt, the dialog's focus trap, the exit dialog, and layout.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Dialog, Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormStrategy, QuestionOption
from freedom_ls.learner_interface.tests.helpers import (
    course_with_form,
    course_with_single_question_form,
)
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import (
    BEFOREUNLOAD_PREVENTED,
    FOCUS_IN_SUBMIT_DIALOG,
    answer_multiple_choice_question,
    click_next,
    form_item_url,
    navigate_to_form,
    start_form,
    submit_form,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def _scored_quiz_course(
    title: str, slug: str, *, question_type: str = "multiple_choice"
) -> Course:
    """A course with a one-question required quiz whose right answer is "Alpha"."""
    course = course_with_single_question_form(
        title, slug, required=True, question_type=question_type
    )
    Form.objects.filter(title=f"{title} Form").update(
        strategy=FormStrategy.QUIZ, quiz_pass_percentage=50
    )
    QuestionOption.objects.filter(
        question__form_page__form__title=f"{title} Form", text="Alpha"
    ).update(correct=True)
    return course


def _four_input_types_course() -> Course:
    """A one-page form with a choice, a text, a checkbox and a dropdown question."""
    form = FormFactory(title="Answer Count Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    choice = FormQuestionFactory(
        form_page=form_page, type="multiple_choice", question="Pick one", order=0
    )
    QuestionOptionFactory(question=choice, text="Alpha", order=0)
    QuestionOptionFactory(question=choice, text="Beta", order=1)
    FormQuestionFactory(
        form_page=form_page, type="short_text", question="Your name", order=1
    )
    checkboxes = FormQuestionFactory(
        form_page=form_page, type="checkboxes", question="Pick many", order=2
    )
    QuestionOptionFactory(question=checkboxes, text="Red", order=0)
    QuestionOptionFactory(question=checkboxes, text="Green", order=1)
    dropdown = FormQuestionFactory(
        form_page=form_page, type="dropdown", question="Pick a colour", order=3
    )
    QuestionOptionFactory(question=dropdown, text="Blue", order=0)
    QuestionOptionFactory(question=dropdown, text="Yellow", order=1)
    return course_with_form(form, title="Answer Count Course", slug="answer-count")


def _two_page_survey_course() -> Course:
    """A two-page survey: choice and name (required) then checkboxes and notes."""
    form = FormFactory(title="Study Survey", subtitle="A survey for learners")
    first = FormPageFactory(form=form, title="About you", order=0)
    choice = FormQuestionFactory(
        form_page=first,
        type="multiple_choice",
        question="What is 2+2?",
        order=0,
        required=True,
    )
    for order, text in enumerate(["3", "4", "5"]):
        QuestionOptionFactory(question=choice, text=text, order=order)
    FormQuestionFactory(
        form_page=first,
        type="short_text",
        question="What is your name?",
        order=1,
        required=True,
    )
    second = FormPageFactory(form=form, title="About your work", order=1)
    checkboxes = FormQuestionFactory(
        form_page=second,
        type="checkboxes",
        question="Select all that apply",
        order=0,
        required=False,
    )
    for order, text in enumerate(["Option A", "Option B"]):
        QuestionOptionFactory(question=checkboxes, text=text, order=order)
    FormQuestionFactory(
        form_page=second,
        type="long_text",
        question="Explain your answer",
        order=1,
        required=False,
    )
    return course_with_form(form, title="Survey Course", slug="survey-course")


def _submit_on_exit_course() -> Course:
    """A quiz that scores on exit, with two required questions."""
    form = FormFactory(
        title="Exit Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=50,
        submit_on_exit=True,
    )
    form_page = FormPageFactory(form=form, title="Page 1", order=0)
    answered = FormQuestionFactory(
        form_page=form_page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0,
        required=True,
    )
    QuestionOptionFactory(question=answered, text="4", correct=True, order=0)
    QuestionOptionFactory(question=answered, text="5", correct=False, order=1)
    skipped = FormQuestionFactory(
        form_page=form_page,
        question="What is 3+3?",
        type="multiple_choice",
        order=1,
        required=True,
    )
    QuestionOptionFactory(question=skipped, text="6", correct=True, order=0)
    return course_with_form(form, title="Exit Course", slug="exit-course")


def _record_beforeunload_dialogs(page: Page) -> list[Dialog]:
    """Accept, and collect, every native leave prompt the page raises."""
    prompts: list[Dialog] = []

    def accept(dialog: Dialog) -> None:
        if dialog.type == "beforeunload":
            prompts.append(dialog)
        dialog.accept()

    page.on("dialog", accept)
    return prompts


def test_learner_works_through_forms_and_quizzes(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    quiz = _scored_quiz_course("Quiz Course", "quiz-course")
    checkbox_quiz = _scored_quiz_course(
        "Checkbox Course", "checkbox-course", question_type="checkboxes"
    )
    counted = _four_input_types_course()
    survey = _two_page_survey_course()
    exit_quiz = _submit_on_exit_course()
    for course in (quiz, checkbox_quiz, counted, survey, exit_quiz):
        register_user_for_course(course, logged_in_user)

    # The landing page leads into the runner, whose tally starts at zero and
    # counts each kind of answer as it is given.
    navigate_to_form(page, live_server, counted)
    start_form(page)
    summary = page.get_by_test_id("answered-summary")
    expect(summary).to_have_text("0 of 4 answered")
    answer_multiple_choice_question(page, "Alpha")
    expect(summary).to_have_text("1 of 4 answered")
    page.get_by_label("Your name").fill("Sheena")
    expect(summary).to_have_text("2 of 4 answered")
    page.get_by_text("Red", exact=True).click()
    expect(summary).to_have_text("3 of 4 answered")
    page.get_by_label("Pick a colour").select_option(label="Blue")
    expect(summary).to_have_text("4 of 4 answered")
    click_next(page)
    expect(page.get_by_test_id("modal-answered-count")).to_have_text("4")

    # A multi-page form numbers its questions, marks the required ones and
    # carries typed answers across pages; leaving mid-way offers to continue.
    survey_landing = navigate_to_form(page, live_server, survey)
    expect(page.get_by_text("A survey for learners")).to_be_visible()
    start_form(page)
    expect(page.get_by_test_id("page-indicator")).to_have_text("Page 1 of 2")
    expect(page.get_by_test_id("question-number-1")).to_be_visible()
    expect(page.get_by_test_id("question-number-2")).to_be_visible()
    expect(page.get_by_test_id("required-indicator-1")).to_be_visible()
    answer_multiple_choice_question(page, "4")
    page.get_by_label("What is your name?").fill("John Doe")
    click_next(page)
    expect(page.get_by_test_id("page-indicator")).to_have_text("Page 2 of 2")
    page.goto(survey_landing)
    page.get_by_role("link", name="Continue Form").click()
    expect(page.get_by_test_id("page-indicator")).to_have_text("Page 2 of 2")
    for option in ("Option A", "Option B"):
        page.get_by_text(option, exact=True).click()
    page.get_by_label("Explain your answer").fill("This is my explanation.")
    submit_form(page)
    expect(page).to_have_url(form_item_url(live_server, survey, "course_form_complete"))

    # A required question holds the submit dialog shut until it is answered.
    quiz_landing = navigate_to_form(page, live_server, quiz)
    start_form(page)
    dialog = page.get_by_role("dialog", name="Ready to submit?")
    click_next(page)
    expect(dialog).to_be_hidden()

    # So does a required checkbox group, which HTML cannot mark required.
    navigate_to_form(page, live_server, checkbox_quiz)
    start_form(page)
    click_next(page)
    expect(dialog).to_be_hidden()
    expect(page.get_by_text("Select at least one option.")).to_be_visible()
    page.get_by_text("Alpha", exact=True).click()
    click_next(page)
    expect(dialog).to_be_visible()

    # An untouched page has no unsaved answers to protect; answering arms the
    # leave prompt.
    page.goto(quiz_landing)
    start_form(page)
    assert page.evaluate(BEFOREUNLOAD_PREVENTED) is False
    answer_multiple_choice_question(page, "Alpha")
    assert page.evaluate(BEFOREUNLOAD_PREVENTED) is True

    # The submit dialog takes focus in and keeps Shift+Tab inside it.
    click_next(page)
    expect(dialog).to_be_visible()
    page.wait_for_function(FOCUS_IN_SUBMIT_DIALOG)
    page.keyboard.press("Shift+Tab")
    assert page.evaluate(FOCUS_IN_SUBMIT_DIALOG) is True
    expect(dialog.get_by_role("button", name="Submit", exact=True)).to_be_focused()

    # Submitting is deliberate, so no leave prompt gets in the way.
    prompts = _record_beforeunload_dialogs(page)
    dialog.get_by_role("button", name="Submit", exact=True).click()
    expect(page).to_have_url(form_item_url(live_server, quiz, "course_form_complete"))
    assert prompts == []

    # The landing page now lists the attempt with its score.
    page.goto(quiz_landing)
    expect(page.get_by_role("heading", name="Previous attempts")).to_be_visible()
    expect(page.get_by_test_id("previous-submission-score")).to_contain_text("100%")

    # Leaving a submit-on-exit quiz scores the page as it stands, even with a
    # required question unanswered.
    navigate_to_form(page, live_server, exit_quiz)
    start_form(page)
    answer_multiple_choice_question(page, "4")
    page.get_by_role("button", name="Exit test").click()
    page.get_by_role("button", name="Leave and submit").click()
    expect(page).to_have_url(
        form_item_url(live_server, exit_quiz, "course_form_complete")
    )
    expect(page.get_by_test_id("quiz-score")).to_have_text(re.compile(r"1\s*/\s*2"))

    # Option rows with their selection indicators fit every viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(
            form_item_url(live_server, checkbox_quiz, "form_fill_page", page_number=1)
        )
        expect(page.get_by_text("Alpha", exact=True)).to_be_visible()
        assert_no_horizontal_overflow(page)
