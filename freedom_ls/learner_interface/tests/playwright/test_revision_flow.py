"""Browser flow for a learner's revision session.

The Django test client covers who may open the revision page and what each
answer records (``views/test_course_revision.py``). What only a browser shows
is covered here: the htmx swaps between cards, the focus move onto the
feedback, the pressed state of the guessed toggle, a reload of answered
feedback and the layout at real widths.
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


def _left_edge(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None
    return box["x"]


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

    page.goto(
        str(
            reverse_url(
                live_server,
                "learner_interface:course_detail",
                kwargs={"course_slug": course.slug},
            )
        )
    )
    page.get_by_role("link", name="Revise", exact=True).click()
    page.get_by_role("button", name="All sections").click()

    expect(page.get_by_text("Question number 1?")).to_be_visible()
    answer_multiple_choice_question(page, "Wrong 1")
    _press_check_answer(page)
    expect(feedback).to_be_focused()
    expect(feedback.get_by_text("Incorrect.")).to_be_visible()
    expect(feedback.get_by_text("Your answer")).to_be_visible()
    expect(feedback.get_by_text(EXPLANATION)).to_be_visible()
    expect(feedback.get_by_role("link", name="Revise: Write Errors")).to_be_visible()
    # The option list shares the card's left edge instead of being indented.
    assert _left_edge(feedback.locator("ul")) == _left_edge(feedback.locator("p").first)
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
    expect(feedback.get_by_text("Correct.")).to_be_visible()
    expect(feedback.get_by_role("button", name="I guessed")).to_have_attribute(
        "aria-pressed", "true"
    )

    click_next(page)
    expect(page.get_by_text("Question number 3?")).to_be_visible()
    answer_multiple_choice_question(page, "Right 3")
    _press_check_answer(page)
    click_next(page)

    expect(page.get_by_test_id("revision-end")).to_have_text("3 answered, 2 right.")
    missed = page.get_by_test_id("revision-missed")
    expect(missed.get_by_text("Question number 1?")).to_be_visible()
    expect(missed.get_by_role("link", name="Revise: Write Errors")).to_be_visible()
    # The missed list shares the card's left edge and shows no bullet markers.
    assert _left_edge(missed) == _left_edge(page.get_by_test_id("revision-end"))
    assert missed.evaluate("el => getComputedStyle(el).listStyleType") == "none"

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
