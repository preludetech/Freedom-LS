"""Browser flows for a learner working through forms and quizzes.

The server-rendered facts (landing page copy, scores, the incorrect-answer
review, which button resumes) are covered by the Django test client in
``views/test_form_runner.py``. What only a browser shows is covered here: the
live answered tally, required-answer validation before the submit dialog opens,
the leave prompt, the dialog's focus trap, the exit dialog, and layout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import pytest
from playwright.sync_api import Dialog, Page, expect
from pytest_django.live_server_helper import LiveServer

from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.conditions import ServedPaper
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    seed_serving,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from freedom_ls.learner_interface.tests.helpers import (
    course_with_form,
    course_with_single_question_form,
)
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_header_lines_up_with_content,
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
    """A survey: choice and name (required), checkboxes and notes, then a follow-up
    page that only applies to a learner who answered "5" to the first question."""
    form = FormFactory(title="Study Survey", subtitle="A survey for learners")
    first = FormPageFactory(form=form, title="About you", order=0)
    choice = FormQuestionFactory(
        form_page=first,
        type="multiple_choice",
        question="What is 2+2?",
        order=0,
        required=True,
    )
    options = [
        QuestionOptionFactory(question=choice, text=text, order=order)
        for order, text in enumerate(["3", "4", "5"])
    ]
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
    follow_up = FormPageFactory(
        form=form, title="Follow-up", order=2, condition_option=options[2]
    )
    FormQuestionFactory(
        form_page=follow_up,
        type="short_text",
        question="How did you get 5?",
        order=0,
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
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """A learner works through forms and quizzes in the browser.

    - The answered tally counts each kind of answer, and the submit dialog shows the count.
    - A multi-page survey numbers and marks its questions, carries answers across pages,
      offers to continue, and counts a gated page once its gate is open.
    - Required questions and checkbox groups hold the submit dialog shut.
    - The leave prompt arms only once an answer exists and stays quiet on submit.
    - The submit dialog traps focus, and the landing page lists the scored attempt.
    - Leaving a submit-on-exit quiz scores the page as it stands.
    - Option rows fit every QA viewport.
    """
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
    page.goto(form_item_url(live_server, survey, "form_fill_page", page_number=1))
    answer_multiple_choice_question(page, "5")
    click_next(page)
    expect(page.get_by_test_id("page-indicator")).to_have_text("Page 2 of 3")
    for option in ("Option A", "Option B"):
        page.get_by_text(option, exact=True).click()
    page.get_by_label("Explain your answer").fill("This is my explanation.")
    click_next(page)
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


def test_quiz_player_layout_flow(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """The quiz player lines up its chrome with its content.

    - The header lines up with the content on the landing page at 1920px.
    - The footer's Next button ends where the option rows end at tablet and
      desktop widths. It used to be 32px wider than the question column.
    - The exit dialog's backdrop sits over the footer. The dialog used to live
      inside the top bar's stacking context, so the footer painted above the
      backdrop and stayed undimmed and clickable.
    - The header lines up with the content on the results and course-finish pages.
    """
    page = logged_in_page
    course = _scored_quiz_course("Aligned Course", "aligned-course")
    register_user_for_course(course, logged_in_user)

    page.set_viewport_size({"width": 1920, "height": 1080})
    navigate_to_form(page, live_server, course)
    assert_header_lines_up_with_content(page)

    start_form(page)
    for viewport in QA_VIEWPORTS[1:]:
        width = viewport["width"]
        page.set_viewport_size(viewport)
        expect(
            page.get_by_text("Alpha", exact=True), f"Alpha option hidden at {width}px"
        ).to_be_visible()

        option_box = page.locator("label", has_text="Alpha").bounding_box()
        next_box = page.get_by_role("button", name="Next").bounding_box()
        assert option_box is not None
        assert next_box is not None
        option_right = option_box["x"] + option_box["width"]
        next_right = next_box["x"] + next_box["width"]
        assert abs(option_right - next_right) <= 2, (
            f"Next button edge differs from the option rows at {width}px: "
            f"options end at x={option_right}, Next ends at x={next_right}"
        )

    page.get_by_role("button", name="Exit test").click()
    exit_dialog = page.get_by_role("dialog")
    expect(exit_dialog, "exit dialog did not open").to_be_visible()
    next_box = page.get_by_role("button", name="Next").bounding_box()
    assert next_box is not None
    footer_on_top = page.evaluate(
        """([x, y]) => {
            const top = document.elementFromPoint(x, y);
            return top !== null && top.closest("[role=dialog]") === null;
        }""",
        [next_box["x"] + next_box["width"] / 2, next_box["y"] + next_box["height"] / 2],
    )
    assert footer_on_top is False, "exit dialog backdrop sits under the footer"
    page.keyboard.press("Escape")
    expect(exit_dialog, "exit dialog did not close").to_be_hidden()

    page.set_viewport_size({"width": 1920, "height": 1080})
    answer_multiple_choice_question(page, "Beta")
    submit_form(page)
    expect(page).to_have_url(form_item_url(live_server, course, "course_form_complete"))
    assert_header_lines_up_with_content(page)

    page.goto(
        str(
            reverse_url(
                live_server,
                "learner_interface:course_finish",
                kwargs={"course_slug": course.slug},
            )
        )
    )
    assert_header_lines_up_with_content(page)


def test_a_long_form_page_scrolls_only_the_player_region(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """The document stays exactly the viewport tall on a long form page.

    The "(required)" text in each question's legend is absolutely positioned;
    with no positioned ancestor in the scroll region it used to extend the
    document, so the player header scrolled away.
    """
    page = logged_in_page
    form = FormFactory(title="Long Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    for order in range(8):
        FormQuestionFactory(
            form_page=form_page,
            type="long_text",
            question=f"Question number {order}",
            order=order,
            required=True,
        )
    course = course_with_form(form, title="Long Form Course", slug="long-form")
    register_user_for_course(course, logged_in_user)
    page.set_viewport_size({"width": 1920, "height": 1080})

    navigate_to_form(page, live_server, course)
    start_form(page)

    heights = page.evaluate(
        "() => [document.documentElement.scrollHeight, window.innerHeight]"
    )
    assert heights[0] == heights[1]


@pytest.mark.browser_context_args(locale="en-ZA")
def test_a_preselected_phone_country_does_not_count_as_an_answer(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    form = FormFactory(title="Phone Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    FormQuestionFactory(
        form_page=form_page, type="phone", question="Your phone number", order=0
    )
    course = course_with_form(form, title="Phone Course", slug="phone-course")
    register_user_for_course(course, logged_in_user)

    navigate_to_form(page, live_server, course)
    start_form(page)

    expect(page.get_by_label("Country").locator("option:checked")).to_have_text(
        "South Africa (+27)"
    )
    summary = page.get_by_test_id("answered-summary")
    expect(summary).to_have_text("0 of 1 answered")
    page.get_by_label("Phone number").fill("82 123 4567")
    expect(summary).to_have_text("1 of 1 answered")
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


STEM_TEXT = "Read this passage before answering"
QUESTION_TEXTS = {
    "multiple_choice": "Which one is right",
    "checkboxes": "Which ones are right",
    "dropdown": "Which dropdown value is right",
}


@dataclass
class ShuffledQuizCourse:
    course: Course
    form: Form
    stem: FormContent
    questions: dict[str, FormQuestion]


def _shuffled_quiz_course() -> ShuffledQuizCourse:
    """A QUIZ, every shuffle knob on, whose second authored page holds a content
    block grouped with a multiple-choice question, then a checkboxes and a
    dropdown question. The first option of each is right, and a checkboxes
    question's second option is too."""
    form = FormFactory(
        title="Shuffled Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=50,
        quiz_show_incorrect=True,
        shuffle_pages=True,
        shuffle_questions=True,
        shuffle_options=True,
    )
    pages = [
        FormPageFactory(form=form, order=order, id=UUID(int=order + 1))
        for order in range(3)
    ]
    stem = FormContentFactory(
        form_page=pages[1], content=STEM_TEXT, order=0, group="stem", id=UUID(int=10)
    )
    specs = [
        ("lone_first", pages[0], "multiple_choice", 0, ""),
        ("multiple_choice", pages[1], "multiple_choice", 1, "stem"),
        ("checkboxes", pages[1], "checkboxes", 2, ""),
        ("dropdown", pages[1], "dropdown", 3, ""),
        ("lone_last", pages[2], "multiple_choice", 0, ""),
    ]
    questions: dict[str, FormQuestion] = {}
    for number, (name, page, question_type, order, group) in enumerate(specs, 20):
        question = FormQuestionFactory(
            id=UUID(int=number),
            form_page=page,
            type=question_type,
            order=order,
            group=group,
            question=QUESTION_TEXTS.get(name, f"Lone question {name}"),
            required=False,
        )
        questions[name] = question
        correct_count = 2 if question_type == "checkboxes" else 1
        for n in range(4):
            QuestionOptionFactory(
                question=question,
                text=f"{name} option {n}",
                order=n,
                correct=n < correct_count,
            )
    course = course_with_form(form, title="Shuffled Course", slug="shuffled-course")
    return ShuffledQuizCourse(course, form, stem, questions)


def _serves_the_grouped_page_first(
    quiz: ShuffledQuizCourse, paper: ServedPaper
) -> bool:
    """Whether the paper serves the authored pages as 2, 3, 1 and puts the
    grouped page's checkboxes question ahead of the group."""
    page_ids = [page["id"] for page in paper["pages"]]
    (grouped,) = [p for p in paper["pages"] if p["id"] == str(quiz.stem.form_page_id)]
    children = grouped["children"]
    return page_ids == [str(UUID(int=2)), str(UUID(int=3)), str(UUID(int=1))] and (
        children.index(str(quiz.questions["checkboxes"].id))
        < children.index(str(quiz.stem.id))
    )


def _served_page_texts(
    quiz: ShuffledQuizCourse, paper: ServedPaper
) -> tuple[list[str], list[int], dict[str, list[str]]]:
    """What the page under test must show, read from the stored paper: its
    children's texts top to bottom, its questions' served numbers, and each
    question's option texts."""
    served_questions = [
        child
        for page in paper["pages"]
        for child in page["children"]
        if child in {str(q.id) for q in quiz.questions.values()}
    ]
    (page,) = [p for p in paper["pages"] if p["id"] == str(quiz.stem.form_page_id)]
    names = {str(q.id): name for name, q in quiz.questions.items()}
    texts = [
        STEM_TEXT if child == str(quiz.stem.id) else QUESTION_TEXTS[names[child]]
        for child in page["children"]
    ]
    numbers = [
        served_questions.index(child) + 1
        for child in page["children"]
        if child != str(quiz.stem.id)
    ]
    option_texts = {
        QUESTION_TEXTS[names[question_id]]: [
            QuestionOption.objects.get(pk=option_id).text for option_id in option_ids
        ]
        for question_id, option_ids in paper["options"].items()
        if names[question_id] in QUESTION_TEXTS
    }
    return texts, numbers, option_texts


def _expect_page_follows_paper(
    page: Page, quiz: ShuffledQuizCourse, user: User
) -> None:
    """The page under test shows its children, question numbers and options in
    the order the sitting's stored paper holds them."""
    paper = FormProgress.objects.get(form=quiz.form, user=user).served_paper
    texts, numbers, option_texts = _served_page_texts(quiz, paper)
    expect(page.get_by_text(STEM_TEXT)).to_be_visible()
    shown = page.get_by_text(
        re.compile("^(" + "|".join([STEM_TEXT, *QUESTION_TEXTS.values()]) + ")$")
    )
    # The dropdown's text appears twice: as its legend and as its select's label.
    assert list(dict.fromkeys(shown.all_text_contents())) == texts
    expect(page.get_by_test_id(re.compile(r"^question-number-\d+$"))).to_have_text(
        [f"{number}." for number in numbers]
    )
    for kind in ("multiple_choice", "checkboxes"):
        options = option_texts[QUESTION_TEXTS[kind]]
        expect(page.get_by_text(re.compile(rf"^{kind} option \d$"))).to_have_text(
            options
        )
    dropdown = page.get_by_label(QUESTION_TEXTS["dropdown"]).get_by_role(
        "option", name=re.compile(r"^dropdown option \d$")
    )
    expect(dropdown).to_have_text(option_texts[QUESTION_TEXTS["dropdown"]])


def test_a_shuffled_quiz_shows_the_served_order_on_every_visit(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = logged_in_page
    quiz = _shuffled_quiz_course()
    register_user_for_course(quiz.course, logged_in_user)
    # `random.shuffle` output is not stable across Python versions, so the
    # seed is searched for rather than fixed.
    seed = seed_serving(
        quiz.form, lambda paper: _serves_the_grouped_page_first(quiz, paper)
    )
    monkeypatch.setattr("freedom_ls.form_engine.served_paper.new_seed", lambda: seed)

    # The first served page is the grouped one, though it is authored second.
    landing = navigate_to_form(page, live_server, quiz.course)
    page.get_by_role("link", name="Start Form").click()
    expect(page).to_have_url(re.compile(r"/fill_form/2$"))
    _expect_page_follows_paper(page, quiz, logged_in_user)

    page.reload()
    _expect_page_follows_paper(page, quiz, logged_in_user)

    page.goto(landing)
    page.get_by_role("link", name="Continue Form").click()
    expect(page).to_have_url(re.compile(r"/fill_form/2$"))
    _expect_page_follows_paper(page, quiz, logged_in_user)

    click_next(page)
    expect(page).to_have_url(re.compile(r"/fill_form/3$"))
    page.go_back()
    expect(page).to_have_url(re.compile(r"/fill_form/2$"))
    _expect_page_follows_paper(page, quiz, logged_in_user)

    # Wrong answers on the grouped page, then on to the end of the paper.
    page.get_by_text("multiple_choice option 3", exact=True).click()
    page.get_by_text("checkboxes option 3", exact=True).click()
    page.get_by_label(QUESTION_TEXTS["dropdown"]).select_option(
        label="dropdown option 3"
    )
    click_next(page)
    click_next(page)
    submit_form(page)
    expect(page).to_have_url(
        form_item_url(live_server, quiz.course, "course_form_complete")
    )

    # The review labels each wrong answer with the number it was served at.
    paper = FormProgress.objects.get(form=quiz.form, user=logged_in_user).served_paper
    served_questions = [
        child for served in paper["pages"] for child in served["children"]
    ]
    for name in ("multiple_choice", "checkboxes", "dropdown"):
        question = quiz.questions[name]
        number = [
            c
            for c in served_questions
            if c in {str(q.id) for q in quiz.questions.values()}
        ].index(str(question.id)) + 1
        expect(
            page.get_by_test_id(f"incorrect-question-{question.id}")
        ).to_contain_text(f"Question {number}")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


def _declaration_quiz_course() -> Course:
    """A course whose only item is a one-question quiz that requires a declaration."""
    form = FormFactory(
        title="Declaration Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=50,
        requires_declaration=True,
        declaration_text="I wrote every answer myself.",
    )
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(
        form_page=page,
        type="multiple_choice",
        question="Which option is right?",
        required=False,
    )
    QuestionOptionFactory(question=question, text="Alpha", order=0, correct=True)
    QuestionOptionFactory(question=question, text="Beta", order=1)
    return course_with_form(form, title="Declaration Course", slug="declaration-course")


def test_a_declaration_quiz_asks_for_a_signature_before_page_one(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _declaration_quiz_course()
    register_user_for_course(course, logged_in_user)

    navigate_to_form(page, live_server, course)
    page.get_by_role("link", name="Start Form").click()
    expect(page.get_by_test_id("declaration-text")).to_contain_text(
        "I wrote every answer myself."
    )

    page.get_by_test_id("declaration-agreed").check()
    page.get_by_test_id("declaration-typed-name").fill("Sheena O'Connell")
    page.get_by_test_id("sign-declaration-button").click()

    expect(page).to_have_url(re.compile(r"/fill_form/1$"))
    expect(page.get_by_text("Which option is right?")).to_be_visible()


def _timed_quiz_course() -> Course:
    """A one-minute quiz with two required multiple-choice questions."""
    form = FormFactory(
        title="Timed Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=50,
        time_limit_minutes=1,
    )
    form_page = FormPageFactory(form=form, title="Page 1", order=0)
    for order, (question_text, option) in enumerate(
        [("What is 2+2?", "4"), ("What is 3+3?", "6")]
    ):
        question = FormQuestionFactory(
            form_page=form_page,
            question=question_text,
            type="multiple_choice",
            order=order,
            required=True,
        )
        QuestionOptionFactory(question=question, text=option, correct=True, order=0)
    return course_with_form(form, title="Timed Course", slug="timed-course")


def test_a_timed_quiz_submits_itself_when_the_countdown_reaches_zero(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _timed_quiz_course()
    register_user_for_course(course, logged_in_user)

    navigate_to_form(page, live_server, course)
    expect(page.get_by_text("1 minute").first).to_be_visible()
    expect(page.get_by_text("This quiz has a time limit of 1 minute.")).to_be_visible()
    start_form(page)

    # Leave a few seconds on the clock rather than waiting out the whole minute.
    FormProgress.objects.filter(user=logged_in_user).update(
        start_time=timezone.now() - timedelta(seconds=55)
    )
    page.reload()
    countdown = page.get_by_test_id("quiz-countdown")
    expect(countdown).to_have_text(re.compile(r"^0:0[1-5]$"))
    first_reading = countdown.inner_text()
    expect(countdown).not_to_have_text(first_reading)

    answer_multiple_choice_question(page, "4")

    expect(page).to_have_url(re.compile(r"/1/complete$"), timeout=15000)
    expect(page.get_by_text("Time ran out")).to_be_visible()
    stored = FormProgress.objects.get(user=logged_in_user)
    assert stored.answers.count() == 1
