"""Browser flow for the course content preview: the outline's Preview buttons
open topic, form and course-details dialogs over the course page.

Focus placement and return, the content_engine widgets running after an htmx
swap, and history restoring the page are browser state the Django test client
never runs.
"""

from __future__ import annotations

from typing import cast

import pytest
from playwright.sync_api import Locator, Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
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
from freedom_ls.tests.retire import retire

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
    topic, a part with a second topic, a quiz and a two-page survey, and a
    reference part holding one topic."""
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
    nested = FormFactory(title="Nested survey")
    FormPageFactory(form=nested, title="Nested one", order=0)
    FormPageFactory(form=nested, title="Nested two", order=1)
    ContentCollectionItemFactory(collection_object=part, child_object=nested, order=1)
    ContentCollectionItemFactory(collection_object=course, child_object=quiz, order=2)
    ContentCollectionItemFactory(collection_object=course, child_object=survey, order=3)

    field_guide = CoursePartFactory(title="Field guide")
    glossary = TopicFactory(title="Glossary", content="Glossary body.")
    ContentCollectionItemFactory(
        collection_object=field_guide, child_object=glossary, order=0
    )
    CourseReferencePartFactory(course=course, course_part=field_guide, order=0)
    return organisation, course


def _left_edge(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None
    return box["x"]


def _visible_text(page: Page, text: str) -> Locator:
    """The outline's visible copy of `text`: the table and the cards both
    hold every row, and only the one for the viewport shows."""
    return page.get_by_text(text, exact=True).locator("visible=true")


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
    content_url = f"{course_url}/__tabs/content"
    courses_url = interface_url(live_server, organisation.slug, "courses")
    modal = page.locator("#app-modal[open]")
    topic_preview = page.get_by_role("button", name="Preview Cards")

    for viewport in QA_VIEWPORTS:
        with no_console_errors(page):
            page.set_viewport_size(viewport)
            page.goto(course_url)
            page.get_by_role("navigation", name="Course sections").get_by_role(
                "link", name="Content"
            ).click()
            expect(page).to_have_url(content_url)
            outline = page.locator("[data-table-layout]")
            reference_panel = page.locator("section[data-panel='reference']")
            if viewport["width"] >= 1920:
                expect(
                    page.get_by_role("region", name="Course outline items")
                ).to_be_visible()
                expect(
                    page.get_by_role("region", name="Reference outline items")
                ).to_be_visible()
            else:
                expect(
                    page.get_by_role("region", name="Course outline items")
                ).to_be_hidden()
                expect(
                    page.get_by_role("region", name="Reference outline items")
                ).to_be_hidden()
            # Every group starts collapsed, nested ones included. Opening a
            # part shows its rows and leaves a form inside it collapsed.
            group_toggles = page.locator("button[aria-controls]").locator(
                "visible=true"
            )
            for toggle in group_toggles.all():
                expect(toggle).to_have_attribute("aria-expanded", "false")
            expect(_visible_text(page, "Inside the part")).to_be_hidden()
            expect(_visible_text(page, "Your thoughts")).to_be_hidden()
            expect(_visible_text(page, "Glossary")).to_be_hidden()
            chapter_toggle = page.get_by_role(
                "button", name="Chapter One", exact=True
            ).locator("visible=true")
            chapter_toggle.click()
            expect(chapter_toggle).to_have_attribute("aria-expanded", "true")
            expect(_visible_text(page, "Inside the part")).to_be_visible()
            nested_toggle = page.get_by_role(
                "button", name="Nested survey", exact=True
            ).locator("visible=true")
            expect(nested_toggle).to_have_attribute("aria-expanded", "false")
            expect(_visible_text(page, "Nested two")).to_be_hidden()
            for name in ("Survey", "Field guide"):
                page.get_by_role("button", name=name, exact=True).locator(
                    "visible=true"
                ).click()
            for title in ("Field guide", "Glossary"):
                expect(
                    reference_panel.get_by_text(title, exact=True).locator(
                        "visible=true"
                    )
                ).to_be_visible()
            for title in (
                "Course details",
                "Cards",
                "Chapter One",
                "Inside the part",
                "Check yourself",
                "Survey",
                "Your thoughts",
            ):
                expect(
                    outline.get_by_text(title, exact=True).locator("visible=true")
                ).to_be_visible()
            assert_no_horizontal_overflow(page)
            if viewport["width"] >= 1920:
                outline_rows = page.get_by_role(
                    "region", name="Course outline items"
                ).locator("tbody tr")
                boxes = [
                    row.bounding_box()
                    for row in outline_rows.locator("visible=true").all()
                ]
                row_heights = [box["height"] for box in boxes if box is not None]
                assert max(row_heights) - min(row_heights) <= 1

                # Stacked outline tables share their column positions: each
                # table used to size its own columns from its content.
                content_region = page.get_by_role("region", name="Course outline items")
                reference_region = page.get_by_role(
                    "region", name="Reference outline items"
                )
                for header in ("#", "Type"):
                    assert _left_edge(
                        content_region.get_by_role("columnheader", name=header)
                    ) == _left_edge(
                        reference_region.get_by_role("columnheader", name=header)
                    )
                assert _left_edge(
                    content_region.get_by_role("button", name="Preview").first
                ) == _left_edge(
                    reference_region.get_by_role("button", name="Preview").first
                )

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

            # Next steps across the part boundary to the first topic inside
            # it, Previous steps back, focus lands on each new title, and the
            # footer offers no Close.
            topic_preview.click()
            expect(modal.get_by_role("button", name="Close", exact=True)).to_have_count(
                1
            )  # the header's close button only
            expect(modal.locator("footer").get_by_role("button")).to_have_count(2)
            expect(modal.get_by_role("button", name="Previous")).to_be_enabled()
            modal.get_by_role("button", name="Next").click()
            expect(
                modal.get_by_role("heading", name="Inside the part (Preview)")
            ).to_be_visible()
            expect(page.locator("#app-modal-title")).to_be_focused()
            modal.get_by_role("button", name="Previous").click()
            expect(modal.get_by_role("heading", name="Cards (Preview)")).to_be_visible()
            expect(page.locator("#app-modal-title")).to_be_focused()
            _press_escape_and_expect_closed(page)

            # The header's close button closes the dialog too.
            topic_preview.click()
            modal.get_by_role("button", name="Close", exact=True).click()
            expect(page.locator("#app-modal[open]")).to_have_count(0)

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
            survey_toggle = page.get_by_role(
                "button", name="Survey", exact=True
            ).locator("visible=true")
            page_row = _visible_text(page, "Your thoughts")
            expect(page_row).to_be_visible()
            survey_toggle.click()
            expect(page_row).to_be_hidden()
            expect(_visible_text(page, "Check yourself")).to_be_visible()
            survey_toggle.click()
            expect(page_row).to_be_visible()

            part_toggle = page.get_by_role(
                "button", name="Chapter One", exact=True
            ).locator("visible=true")
            part_item = _visible_text(page, "Inside the part")
            part_toggle.click()
            expect(part_item).to_be_hidden()
            expect(_visible_text(page, "Cards")).to_be_visible()
            expect(_visible_text(page, "Survey")).to_be_visible()
            part_toggle.click()
            expect(part_item).to_be_visible()
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
            expect(page).to_have_url(content_url)
            topic_preview.click()
            expect(modal.get_by_role("heading", name="Cards (Preview)")).to_be_visible()
            expect(modal.get_by_role("button", name="Flip card")).to_be_visible()
            _press_escape_and_expect_closed(page)

            # A reference topic's preview opens and closes like the outline's.
            # Going back reloaded the page, so its groups start collapsed.
            page.get_by_role("button", name="Field guide", exact=True).locator(
                "visible=true"
            ).click()
            glossary_preview = page.get_by_role("button", name="Preview Glossary")
            glossary_preview.click()
            expect(
                modal.get_by_role("heading", name="Glossary (Preview)")
            ).to_be_visible()
            assert_no_horizontal_overflow(page)
            _press_escape_and_expect_closed(page)
            expect(glossary_preview).to_be_focused()


def test_course_list_shows_a_retired_badge_on_a_retired_course_at_every_viewport(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation, course = _seed_course(educator_user)
    retire(course)
    courses_url = interface_url(live_server, organisation.slug, "courses")

    for viewport in QA_VIEWPORTS:
        with no_console_errors(page):
            page.set_viewport_size(viewport)
            page.goto(courses_url)
            expect(
                page.get_by_text("Retired", exact=True).locator("visible=true").first
            ).to_be_visible()
            assert_no_horizontal_overflow(page)
