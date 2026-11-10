"""Browser flow for the course content preview: the outline's Preview buttons
open topic, form and course-details dialogs over the course page.

Focus placement and return, the content_engine widgets running after an htmx
swap, and history restoring the page are browser state the Django test client
never runs.
"""

from __future__ import annotations

from typing import cast

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url, no_console_errors

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

FLASHCARD = (
    "<c-flashcard>\n"
    '<c-slot name="front">\n\nWhat is two plus two?\n\n</c-slot>\n'
    '<c-slot name="back">\n\nFour.\n\n</c-slot>\n'
    "</c-flashcard>"
)


def _seed_course(user: AbstractBaseUser) -> tuple[Organisation, Course]:
    """An organisation `user` administers, holding a course with a flashcard
    topic, a part with a second topic, a quiz and a two-page survey."""
    organisation = cast(Organisation, OrganisationFactory(name="Org A"))
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, user, "organisation_admin", organisation)
    course = cast(Course, CourseFactory(title="Algebra"))
    LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=organisation), course=course
    )

    topic = TopicFactory(title="Cards", content=FLASHCARD)
    part = CoursePartFactory(title="Chapter One")
    part_topic = TopicFactory(title="Inside the part", content="Part body.")
    quiz = FormFactory(title="Check yourself")
    page = FormPageFactory(form=quiz, title="Page one")
    question = FormQuestionFactory(form_page=page, question="Pick one")
    QuestionOptionFactory(question=question, text="Option A")
    QuestionOptionFactory(question=question, text="Option B", correct=True)
    survey = FormFactory(title="Survey")
    FormQuestionFactory(
        form_page=FormPageFactory(form=survey, title="About you", order=0),
        question="Your name",
    )
    FormQuestionFactory(
        form_page=FormPageFactory(form=survey, title="Your thoughts", order=1),
        question="Anything else",
    )

    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=1)
    ContentCollectionItemFactory(
        collection_object=part, child_object=part_topic, order=0
    )
    ContentCollectionItemFactory(collection_object=course, child_object=quiz, order=2)
    ContentCollectionItemFactory(collection_object=course, child_object=survey, order=3)
    return organisation, course


def _tab_to_focus(page: Page, selector: str) -> None:
    """Presses Tab until the element matching `selector` holds focus."""
    for _ in range(80):
        page.keyboard.press("Tab")
        if page.evaluate(
            "(selector) => document.activeElement?.matches(selector)", selector
        ):
            return
    pytest.fail(f"Tab never reached {selector}")


def _press_escape_and_expect_closed(page: Page) -> None:
    page.keyboard.press("Escape")
    expect(page.locator("#app-modal[open]")).to_have_count(0)


def _open_courses_from_sidebar(page: Page) -> None:
    """Follows the sidebar's Courses link, opening the sheet first when the
    sidebar is not docked."""
    sidebar = page.locator("dialog[aria-label='Navigation']")
    if not sidebar.is_visible():
        page.get_by_role("button", name="Open navigation panel").click()
    sidebar.get_by_role("link", name="Courses").click()


def test_educator_previews_course_content(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation, course = _seed_course(educator_user)
    course_url = interface_url(live_server, organisation.slug, f"courses/{course.pk}")
    courses_url = interface_url(live_server, organisation.slug, "courses")
    modal = page.locator("#app-modal[open]")
    topic_preview = page.get_by_role("button", name="Preview Cards")

    for viewport in QA_VIEWPORTS:
        with no_console_errors(page):
            page.set_viewport_size(viewport)
            page.goto(course_url)
            outline = page.get_by_role("region", name="Course outline")
            for title in (
                "Course details",
                "Cards",
                "Chapter One",
                "Inside the part",
                "Check yourself",
                "Survey",
                "Your thoughts",
            ):
                expect(outline.get_by_text(title, exact=True)).to_be_visible()
            assert_no_horizontal_overflow(page)

            # Enter on the keyboard-focused button opens the dialog and puts
            # focus on its title.
            _tab_to_focus(page, "[aria-label='Preview Cards']")
            page.keyboard.press("Enter")
            expect(modal).to_be_visible()
            expect(modal.get_by_role("heading", name="Cards (Preview)")).to_be_visible()
            assert page.evaluate("document.activeElement.id") == "app-modal-title"
            assert_no_horizontal_overflow(page)

            # The flashcard's Alpine component runs after the htmx swap.
            flip = modal.get_by_role("button", name="Flip card")
            expect(flip).to_have_attribute("aria-pressed", "false")
            flip.click()
            expect(flip).to_have_attribute("aria-pressed", "true")

            _press_escape_and_expect_closed(page)
            expect(topic_preview).to_be_focused()

            page.get_by_role("button", name="Preview Check yourself").click()
            expect(modal.get_by_text("Option B")).to_be_visible()
            assert_no_horizontal_overflow(page)
            _press_escape_and_expect_closed(page)

            page.get_by_role("button", name="Preview course details page").click()
            expect(modal).to_be_visible()
            expect(modal.get_by_text("Algebra").first).to_be_visible()
            assert_no_horizontal_overflow(page)
            _press_escape_and_expect_closed(page)

            # A multi-page form's page row previews that page alone.
            survey_toggle = page.get_by_role("button", name="Collapse Survey")
            page_row = page.locator("tr", has_text="Your thoughts")
            expect(page_row).to_be_visible()
            survey_toggle.click()
            expect(page_row).to_be_hidden()
            survey_toggle.click()
            expect(page_row).to_be_visible()
            page.get_by_role("button", name="Preview Survey: Your thoughts").click()
            expect(
                modal.get_by_role("heading", name="Your thoughts (Preview)")
            ).to_be_visible()
            expect(modal.get_by_text("Page 2 of 2: Your thoughts")).to_be_visible()
            expect(modal.get_by_text("Your name")).to_have_count(0)
            _press_escape_and_expect_closed(page)

            # Back restores the course page with working Preview buttons.
            _open_courses_from_sidebar(page)
            expect(page).to_have_url(courses_url)
            page.go_back()
            expect(page).to_have_url(course_url)
            topic_preview.click()
            expect(modal.get_by_role("heading", name="Cards (Preview)")).to_be_visible()
            expect(modal.get_by_role("button", name="Flip card")).to_be_visible()
            _press_escape_and_expect_closed(page)
