"""Browser flow for a learner's revision session.

The Django test client covers who may open the revision page and what each
answer records (``views/test_course_revision.py``). What only a browser shows
is covered here: the way in from the player's outline, the htmx swaps between
cards, the focus move onto the feedback, the pressed state of the guessed
toggle, a reload of answered feedback and the layout at real widths.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect
from pytest_django.live_server_helper import LiveServer

from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Topic
from freedom_ls.content_engine.models.question_sections import FormQuestionTopic
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormPage, FormQuestion
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_interface.tests.playwright.helpers import (
    answer_multiple_choice_question,
    click_next,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

EXPLANATION = "Because a write that fails is a conflict, not a malformed request."


def _bank_question(
    page_row: FormPage, topic: Topic, order: int, **kwargs: str
) -> FormQuestion:
    """A question on `page_row` that tests `topic`, with a right and a wrong option."""
    question: FormQuestion = FormQuestionFactory(
        form_page=page_row,
        question=f"Question number {order}?",
        order=order,
        **kwargs,
    )
    QuestionOptionFactory(question=question, text=f"Right {order}", correct=True)
    QuestionOptionFactory(question=question, text=f"Wrong {order}", correct=False)
    FormQuestionTopic.objects.create(question=question, topic=topic)
    return question


def _press_check_answer(page: Page) -> None:
    page.get_by_role("button", name="Check answer").click()


def _box(locator: Locator) -> dict[str, float]:
    box = locator.bounding_box()
    assert box is not None
    return dict(box)


def _content_width(locator: Locator) -> float:
    """The width inside an element's padding, where its children are laid out."""
    return float(
        locator.evaluate(
            """el => {
                const style = getComputedStyle(el);
                return el.clientWidth
                    - parseFloat(style.paddingLeft)
                    - parseFloat(style.paddingRight);
            }"""
        )
    )


def _is_tinted(locator: Locator) -> bool:
    """Whether a row has a background of its own, not a transparent one."""
    colour = str(locator.evaluate("el => getComputedStyle(el).backgroundColor"))
    return colour not in {"rgba(0, 0, 0, 0)", "transparent"}


def test_learner_works_through_a_revision_session(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = CourseFactory(title="Revision Course", slug="revision-course")
    topic = TopicFactory(title="Write Errors", slug="write-errors")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    LearnerCourseRegistrationFactory(
        learner__user=logged_in_user, course=course, is_active=True
    )
    topic_completion(course, logged_in_user, topic, complete_time=timezone.now())
    bank_page = FormPageFactory(form=FormFactory())
    _bank_question(bank_page, topic, 1, explanation=EXPLANATION)
    _bank_question(bank_page, topic, 2)
    _bank_question(bank_page, topic, 3)
    feedback = page.locator("#revision-feedback")
    card = page.locator("#revision-card")
    outline = page.locator("#course-toc-region")

    # The course details page says nothing about revision: it starts in the player.
    page.goto(
        str(
            reverse_url(
                live_server,
                "learner_interface:course_detail",
                kwargs={"course_slug": course.slug},
            )
        )
    )
    expect(page.get_by_text("Revision", exact=True)).to_have_count(0)

    page.goto(
        str(
            reverse_url(
                live_server,
                "learner_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": 1},
            )
        )
    )
    entry = outline.get_by_role("link", name="Revision")
    expect(entry).to_contain_text("3 due")
    # The entry sits under the table of contents, not above it.
    assert (
        _box(entry)["y"]
        > _box(outline.get_by_role("navigation", name="Course outline"))["y"]
    )
    entry.click()

    # The dashboard opens inside the player: the outline stays beside it.
    expect(card.get_by_role("heading", name="Revision")).to_be_visible()
    expect(card.get_by_text("3 questions due.")).to_be_visible()
    expect(outline.get_by_role("link", name="Revision")).to_be_visible()
    start = card.get_by_role("button", name="Start revision")
    assert _box(start)["width"] == pytest.approx(_content_width(card), abs=1)
    start.click()

    expect(page.get_by_text("Question number 1?")).to_be_visible()
    expect(outline.get_by_role("link", name="Revision")).to_be_visible()
    check = card.get_by_role("button", name="Check answer")
    assert _box(check)["width"] == pytest.approx(_content_width(card), abs=1)
    # Checking with nothing selected reaches the server and shows the card's own
    # error; the browser's native validation bubble used to block the request.
    _press_check_answer(page)
    expect(card.get_by_text("Choose an answer.")).to_be_visible()
    expect(page.get_by_text("Question number 1?")).to_be_visible()
    answer_multiple_choice_question(page, "Wrong 1")
    _press_check_answer(page)
    expect(feedback).to_be_focused()
    result = feedback.get_by_test_id("revision-result")
    expect(result).to_contain_text("Not quite. The answer is Right 1.")
    expect(result.get_by_text(EXPLANATION)).to_be_visible()
    expect(result.get_by_role("link", name="Revisit: Write Errors")).to_be_visible()
    # Each marked option carries its result as a tint; the unmarked callout does too.
    assert _is_tinted(feedback.locator('li[data-result="wrong"]'))
    assert _is_tinted(feedback.locator('li[data-result="correct"]'))
    assert _is_tinted(result)
    # The option list shares the card's left edge instead of being indented.
    assert _box(feedback.locator("ul"))["x"] == _box(result)["x"]
    assert (
        feedback.locator("ul").evaluate("el => getComputedStyle(el).listStyleType")
        == "none"
    )

    click_next(page)
    expect(page.get_by_text("Question number 2?")).to_be_visible()
    answer_multiple_choice_question(page, "Right 2")
    _press_check_answer(page)
    guessed = feedback.get_by_role("button", name="I guessed")
    expect(guessed).to_have_attribute("aria-pressed", "false")
    guessed.click()
    expect(feedback.get_by_role("button", name="I guessed")).to_have_attribute(
        "aria-pressed", "true"
    )

    page.reload()
    expect(feedback.get_by_test_id("revision-result")).to_contain_text("Correct.")
    expect(feedback.get_by_role("button", name="I guessed")).to_have_attribute(
        "aria-pressed", "true"
    )

    click_next(page)
    expect(page.get_by_text("Question number 3?")).to_be_visible()
    answer_multiple_choice_question(page, "Right 3")
    _press_check_answer(page)
    click_next(page)

    expect(card.get_by_role("heading", name="Revision done")).to_be_visible()
    expect(page.get_by_test_id("revision-answered")).to_have_text(
        "You answered 3 questions."
    )
    expect(page.get_by_test_id("revision-knew")).to_have_text("1")
    expect(page.get_by_test_id("revision-hard")).to_have_text("1")
    expect(page.get_by_test_id("revision-forgot")).to_have_text("1")
    back = card.get_by_role("link", name="Back to the course")
    assert _box(back)["width"] == pytest.approx(_content_width(card), abs=1)
    expect(card.get_by_role("link")).to_have_count(1)
    expect(card.get_by_role("button")).to_have_count(0)

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)

    back.click()
    expect(page.get_by_role("heading", name="Write Errors")).to_be_visible()
