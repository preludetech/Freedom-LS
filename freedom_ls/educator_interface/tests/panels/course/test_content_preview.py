"""Tests for the course outline and the content previews."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db.models import Model
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course as CourseModel
from freedom_ls.content_engine.models import File
from freedom_ls.educator_interface.tests.helpers import (
    _content_action_url,
    _get_document,
    _interface_url,
    course_per_reach_row,
    organisation_admin_viewer,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.learner_management.models import (
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context


@pytest.mark.django_db
def test_course_page_buttons_are_only_preview_triggers(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(title="Intro"), order=0
    )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert header.cssselect("button[hx-get]") == []
    buttons = document.cssselect("section[data-panel] button[hx-get]")
    assert {button.get("aria-label") for button in buttons} == {
        "Preview course details page",
        "Preview Intro",
    }
    assert document.cssselect("section[data-panel] footer button") == []


def _course_content_panel(client: Client, course: CourseModel) -> lxml.html.HtmlElement:
    organisation = OrganisationFactory()
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    (panel,) = document.cssselect("section[data-panel='content']")
    return panel


def _outline_rows(panel: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
    return list(panel.cssselect("[aria-label='Course outline items'] tbody tr"))


def _outline_numbers(panel: lxml.html.HtmlElement) -> list[str]:
    numbers = [
        cell.text_content().strip()
        for row in _outline_rows(panel)
        for cell in row.cssselect("td.tabular-nums")[:1]
    ]
    return [number for number in numbers if number]


@pytest.mark.django_db
def test_course_content_numbers_rows_in_collection_order(staff_client: Client) -> None:
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=1
    )
    part = CoursePartFactory(title="Warm up")
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=2)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=1
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=FormFactory(), order=3
    )

    panel = _course_content_panel(staff_client, course)

    assert panel.cssselect(".panel-data-table table")
    assert _outline_numbers(panel) == ["1.", "2.", "3.", "3.1", "3.2", "4."]
    rows = _outline_rows(panel)
    first_cells = [cell.text_content().strip() for cell in rows[0].cssselect("td")]
    assert first_cells[:3] == ["", "Course details", "Course"]
    assert rows[0].cssselect("button[hx-get]")[0].text_content().strip() == "Preview"
    form_row = rows[-1]
    assert form_row.cssselect("svg")
    assert form_row.cssselect(".sr-only")[0].text_content().strip() == "Form"
    assert form_row.cssselect("td")[2].text_content().strip() == "Form"
    assert form_row.cssselect("button[hx-get]")[0].text_content().strip() == "Preview"
    assert panel.cssselect("header button") == []


@pytest.mark.django_db
def test_course_content_part_rows_are_expandable_buttons(staff_client: Client) -> None:
    course = CourseFactory()
    part = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=1
    )
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=1
    )

    panel = _course_content_panel(staff_client, course)

    (button,) = panel.cssselect("table button[aria-controls]")
    assert button.get("aria-expanded") == "true"
    # aria-expanded carries the state, so the name holds no verb that would
    # be wrong once the group is collapsed.
    assert button.get("aria-label") == part.title
    row_ids = {node.get("id") for node in panel.cssselect("tbody tr[id]")}
    controlled = set(str(button.get("aria-controls")).split())
    assert len(controlled) == 2
    assert controlled <= row_ids
    assert button.xpath("ancestor::tr")[0].cssselect("button[hx-get]") == []


@pytest.mark.django_db
def test_a_multi_page_form_expands_into_one_row_per_page(staff_client: Client) -> None:
    course = CourseFactory()
    survey = FormFactory(title="Survey")
    first = FormPageFactory(form=survey, title="About you", order=0)
    FormPageFactory(form=survey, title="", order=1)
    quiz = FormFactory(title="Quiz")
    FormPageFactory(form=quiz, title="Only page", order=0)
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    survey_item = ContentCollectionItemFactory(
        collection_object=course, child_object=survey, order=1
    )
    ContentCollectionItemFactory(collection_object=course, child_object=quiz, order=2)

    panel = _course_content_panel(staff_client, course)

    assert _outline_numbers(panel) == ["1.", "2.", "2.1", "2.2", "3."]
    rows = _outline_rows(panel)
    survey_row, page_one, page_two, quiz_row = rows[2], rows[3], rows[4], rows[5]
    (toggle,) = survey_row.cssselect("button[aria-controls]")
    assert set(str(toggle.get("aria-controls")).split()) == {
        page_one.get("id"),
        page_two.get("id"),
    }
    (survey_trigger,) = survey_row.cssselect("button[hx-get]")
    assert survey_trigger.get("hx-get").endswith(f"?item={survey_item.pk}")
    (page_trigger,) = page_one.cssselect("button[hx-get]")
    assert page_trigger.get("hx-get").endswith(
        f"?item={survey_item.pk}&page={first.pk}"
    )
    assert page_trigger.get("aria-label") == "Preview Survey: About you"
    assert page_one.cssselect("td")[2].text_content().strip() == "Page"
    assert page_two.cssselect("td .font-medium")[0].text_content().strip() == "Page 2"
    assert quiz_row.cssselect("button[aria-controls]") == []
    (quiz_trigger,) = quiz_row.cssselect("button[hx-get]")
    assert "page=" not in str(quiz_trigger.get("hx-get"))


@pytest.mark.django_db
def test_course_content_shows_every_row_on_one_page(staff_client: Client) -> None:
    course = CourseFactory()
    topics = [TopicFactory(title=f"Topic {number:03d}") for number in range(60)]
    for order, topic in enumerate(topics):
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=order
        )

    panel = _course_content_panel(staff_client, course)

    assert len(_outline_rows(panel)) == 61
    assert "outline-page=" not in lxml.html.tostring(panel, encoding="unicode")
    (count,) = panel.cssselect("[data-entry-count]")
    assert count.text_content().strip() == "60 course outline items"


@pytest.mark.django_db
def test_course_content_counts_nested_rows_but_not_the_details_or_notes(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    part = CoursePartFactory(title="Warm up")
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=CoursePartFactory(), order=1
    )

    panel = _course_content_panel(staff_client, course)

    (count,) = panel.cssselect("[data-entry-count]")
    assert count.text_content().strip() == "3 course outline items"


@pytest.mark.django_db
def test_course_content_cards_mirror_the_rows_without_repeating_ids(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    part = CoursePartFactory(title="Warm up")
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )

    panel = _course_content_panel(staff_client, course)

    rows = _outline_rows(panel)
    cards = panel.cssselect("li.panel-data-table-card")
    assert len(cards) == len(rows) == 3
    assert len(cards[1].cssselect("button[aria-controls]")) == 1
    assert cards[2].cssselect("button[aria-controls]") == []
    ids = [node.get("id") for node in panel.cssselect("[id]")]
    assert len(ids) == len(set(ids))


@pytest.mark.django_db
def test_course_content_empty_course_shows_empty_state(staff_client: Client) -> None:
    panel = _course_content_panel(staff_client, CourseFactory())

    assert "No content in this course yet." in panel.text_content()
    assert _outline_numbers(panel) == []
    assert len(_outline_rows(panel)) == 2
    assert panel.cssselect("[data-entry-count]") == []


@pytest.mark.django_db
def test_course_content_empty_part_shows_empty_message(staff_client: Client) -> None:
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=CoursePartFactory(), order=0
    )

    panel = _course_content_panel(staff_client, course)

    assert "No items in this part." in panel.text_content()


@pytest.mark.django_db
@pytest.mark.parametrize("in_development", [True, False])
def test_course_content_callout_shows_only_while_in_development(
    staff_client: Client, in_development: bool
) -> None:
    course = CourseFactory(table_of_contents_in_development=in_development)

    panel = _course_content_panel(staff_client, course)

    assert ("Learners can't see this outline yet." in panel.text_content()) is (
        in_development
    )


@pytest.mark.django_db
def test_course_content_callout_has_space_below_it_before_the_table(
    staff_client: Client,
) -> None:
    """The in-development callout's wrapper had top padding only, so the callout touched the table."""
    course = CourseFactory(table_of_contents_in_development=True)

    panel = _course_content_panel(staff_client, course)

    (text_element,) = [
        element
        for element in panel.iter()
        if "Learners can't see this outline yet." in (element.text or "")
    ]
    wrapper = next(
        ancestor
        for ancestor in text_element.iterancestors()
        if "pt-4" in ancestor.get("class", "").split()
    )
    classes = wrapper.get("class", "").split()
    assert "pt-4" in classes
    assert "pb-4" in classes or "py-4" in classes


@pytest.mark.django_db
def test_course_content_query_count_stays_bounded_as_children_grow(
    staff_client: Client, django_assert_max_num_queries
) -> None:
    course = CourseFactory()
    part = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    for order in range(12):
        ContentCollectionItemFactory(
            collection_object=part, child_object=TopicFactory(), order=order
        )
    organisation = OrganisationFactory()
    url = _interface_url(organisation.slug, f"courses/{course.pk}")

    with django_assert_max_num_queries(60):
        assert staff_client.get(url).status_code == 200


def _preview_url(
    client: Client, organisation: Organisation, course: CourseModel
) -> str:
    """The Preview action's URL as the course page publishes it, without
    the item parameter."""
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    trigger = document.cssselect(
        "section[data-panel='content'] table button[hx-get*='preview_content']"
    )[0]
    return str(trigger.get("hx-get")).split("?")[0]


def _course_with_topic(topic: Model | None = None) -> tuple[CourseModel, Model]:
    course = cast(CourseModel, CourseFactory())
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=topic or TopicFactory(), order=0
    )
    return course, cast(Model, item)


@pytest.mark.django_db
def test_a_topic_row_carries_a_preview_trigger_for_its_collection_item(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic(TopicFactory(title="Intro"))

    html = staff_client.get(
        _interface_url(organisation.slug, f"courses/{course.pk}")
    ).content.decode()
    panel = lxml.html.fromstring(html).cssselect("section[data-panel='content']")[0]

    (trigger,) = panel.cssselect("table button[aria-label='Preview Intro']")
    assert trigger.get("hx-get").endswith(f"/__actions/preview_content?item={item.pk}")
    assert trigger.text_content().strip() == "Preview"
    assert trigger.get("aria-label") == "Preview Intro"
    assert "view_course_item" not in html
    assert reverse("learner_interface:course_detail", args=[course.slug]) not in html


@pytest.mark.django_db
def test_opening_a_topic_preview_renders_it_read_only_in_the_wide_dialog(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic(
        TopicFactory(title="Intro", content="Hello **learners**")
    )
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert response.status_code == 200
    assert 'data-modal-size="wide"' in html
    assert "Intro (Preview)" in html
    assert "Topic" in html
    assert "Nothing here is saved." not in html
    assert "max-w-reading" in html
    assert "<strong>learners</strong>" in html
    assert "<form" not in html
    assert "Mark complete" not in html
    assert "<nav" not in html


@pytest.mark.django_db
def test_the_course_page_loads_katex_before_the_content_components(
    staff_client: Client,
) -> None:
    """A previewed equation typesets only when KaTeX is on the page by the
    time the equation component starts."""
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()

    html = staff_client.get(
        _interface_url(organisation.slug, f"courses/{course.pk}")
    ).content.decode()

    assert "content_engine/vendor/katex/katex.min.css" in html
    katex_script = html.index("content_engine/vendor/katex/katex.min.js")
    assert katex_script < html.index("content_engine/js/alpine-components.js")


@pytest.mark.django_db
def test_a_topic_holding_a_content_link_previews(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    TopicFactory(file_path="1. welcome/content.md")
    topic = TopicFactory(
        file_path="2. reading/content.md",
        content=(
            'Go back to <c-content-link path="../1. welcome/content.md">'
            "the Welcome topic</c-content-link>."
        ),
    )
    course, item = _course_with_topic(topic)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "the Welcome topic" in response.content.decode()


@pytest.mark.django_db
def test_opening_a_topic_preview_writes_nothing(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    FileFactory(file_path="pic.png", mime_type="image/png")
    FileFactory(file_path="notes.txt")
    topic = TopicFactory(
        content=(
            '<c-picture src="pic.png" alt="A picture"></c-picture>\n\n'
            '<c-file-download src="notes.txt" text="Get notes"></c-file-download>\n'
        )
    )
    course, item = _course_with_topic(topic)
    url = _preview_url(staff_client, organisation, course)
    counted = [
        TopicProgress,
        CourseProgress,
        LearnerCourseRegistration,
        AuditLogEntry,
        FormProgress,
        QuestionAnswer,
    ]
    before = [model.objects.count() for model in counted]

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "Get notes" in response.content.decode()
    assert [model.objects.count() for model in counted] == before


@pytest.mark.django_db
def test_a_topic_preview_renders_a_speak_button_and_the_course_page_loads_its_script(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    FileFactory(
        file_path="bravo.mp3", file_type=File.FileType.AUDIO, mime_type="audio/mpeg"
    )
    topic = TopicFactory(content='<c-audio src="bravo.mp3" label="Bravo"></c-audio>\n')
    course, item = _course_with_topic(topic)
    course_url = _interface_url(organisation.slug, f"courses/{course.pk}")
    preview_url = _preview_url(staff_client, organisation, course)

    preview = staff_client.get(
        f"{preview_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    ).content.decode()
    course_page = staff_client.get(course_url).content.decode()

    assert "data-src=" in preview
    assert "content_engine/js/alpine-components.js" in course_page


@pytest.mark.django_db
def test_a_preview_of_another_courses_item_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    _other_course, other_item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_of_an_item_on_another_site_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    with site_context(SiteFactory()):
        _other_course, other_item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_of_a_part_row_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    part_item = ContentCollectionItemFactory(
        collection_object=course, child_object=CoursePartFactory(), order=1
    )
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={part_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "item", ["", "not-a-uuid", "6f1c2f0e-3c1b-4a5e-9a57-0d1f6d3a9b11"]
)
def test_a_preview_with_a_missing_or_malformed_item_is_a_404(
    staff_client: Client, item: str
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_without_the_htmx_header_or_by_post_is_a_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    plain_get = staff_client.get(f"{url}?item={item.pk}")
    post = staff_client.post(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["topic", "form"])
def test_the_preview_url_built_for_the_denial_tests_is_the_published_one(
    staff_client: Client, kind: str
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic() if kind == "topic" else _course_with_form()

    url = _content_action_url(organisation, course, "preview_content")
    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert url == _preview_url(staff_client, organisation, course)
    assert response.status_code == 200


@pytest.mark.django_db
def test_a_topic_inside_a_part_nested_in_a_part_can_be_previewed(
    staff_client: Client,
) -> None:
    """The outline shows a Preview button at every depth, but the preview used
    to find items only one part deep, so a nested part's topic returned 404."""
    organisation = OrganisationFactory()
    course = CourseFactory()
    outer = CoursePartFactory(title="Outer part")
    inner = CoursePartFactory(title="Inner part")
    ContentCollectionItemFactory(collection_object=course, child_object=outer, order=0)
    ContentCollectionItemFactory(collection_object=outer, child_object=inner, order=0)
    nested = ContentCollectionItemFactory(
        collection_object=inner,
        child_object=TopicFactory(title="Nested topic"),
        order=0,
    )
    url = _content_action_url(organisation, course, "preview_content")

    response = staff_client.get(f"{url}?item={nested.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_course_belonging_only_to_another_organisation_cannot_be_previewed(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    course.organisations.add(OrganisationFactory())
    action_url = _content_action_url(organisation, course, "preview_content")

    page = staff_client.get(_interface_url(organisation.slug, f"courses/{course.pk}"))
    action = staff_client.get(f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (page.status_code, action.status_code) == (404, 404)


@pytest.mark.django_db
def test_a_user_with_no_role_in_the_organisation_cannot_preview(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    action_url = _content_action_url(organisation, course, "preview_content")

    response = logged_in_client(UserFactory()).get(
        f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


QUESTION_TYPES = [
    "multiple_choice",
    "checkboxes",
    "short_text",
    "long_text",
    "number",
    "date",
    "time",
    "email",
    "url",
    "phone",
    "dropdown",
    "file_upload",
]


def _course_with_form(form: Model | None = None) -> tuple[CourseModel, Model]:
    course = cast(CourseModel, CourseFactory())
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=form or FormFactory(), order=0
    )
    return course, cast(Model, item)


@pytest.mark.django_db
def test_opening_a_form_preview_renders_every_question_type_disabled(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    form = FormFactory(title="Intake", content="Tell us **more**")
    page = FormPageFactory(form=form, title="About you")
    for order, question_type in enumerate(QUESTION_TYPES):
        question = FormQuestionFactory(
            form_page=page, type=question_type, order=order, question=f"Q {order}"
        )
        if question_type in {"multiple_choice", "checkboxes", "dropdown"}:
            QuestionOptionFactory(question=question, text="Yes", order=0)
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    document = lxml.html.fromstring(html)
    assert response.status_code == 200
    assert "<strong>more</strong>" in html
    assert "About you" in html
    (heading,) = document.cssselect("h2")
    assert heading.text_content().split() == ["Intake", "(Preview)", "Form"]
    controls = document.cssselect("input, textarea, select")
    assert controls
    assert all(control.get("disabled") is not None for control in controls)
    assert "File upload question" in html
    assert "questionFileUpload" not in html
    assert "hx-post" not in html
    assert "<form" not in html
    assert document.cssselect("button[type='submit']") == []


@pytest.mark.django_db
def test_a_form_preview_lists_options_and_the_dropdown_answer_key_as_authored(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    form = FormFactory(title="Intake")
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type="dropdown", order=0)
    QuestionOptionFactory(question=question, text="Second", order=1, correct=True)
    QuestionOptionFactory(question=question, text="First", order=0)
    QuestionOptionFactory(question=question, text="Third", order=2, correct=True)
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content)
    options = [
        o.text_content() for o in document.cssselect("select option") if o.get("value")
    ]
    key = [li.text_content() for li in document.cssselect("ul.list-none li")]
    assert options == ["First", "Second", "Third"]
    assert [" ".join(text.split()) for text in key] == [
        "Correct answer: Second",
        "Correct answer: Third",
    ]


def _three_page_form(title: str = "Survey") -> tuple[Model, Model]:
    """A survey whose second page is shown only on one answer; returns the
    form and that second page."""
    form = FormFactory(title=title, content="Tell us **everything**")
    first = FormPageFactory(form=form, title="First page", order=0)
    gate = FormQuestionFactory(form_page=first, question="Do you smoke?", order=0)
    option = QuestionOptionFactory(question=gate, text="Yes", order=0)
    second = FormPageFactory(
        form=form, title="Second page", order=1, condition_option=option
    )
    FormQuestionFactory(form_page=second, question="How many a day?", order=0)
    FormPageFactory(form=form, title="Third page", order=2)
    return cast(Model, form), cast(Model, second)


@pytest.mark.django_db
def test_a_page_previews_alone_headed_by_its_place_and_its_condition(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    form, second = _three_page_form()
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={second.pk}", HTTP_HX_REQUEST="true"
    )

    html = response.content.decode()
    document = lxml.html.fromstring(html)
    assert response.status_code == 200
    (heading,) = document.cssselect("h2")
    assert heading.text_content().split() == [
        "Second",
        "page",
        "(Preview)",
        "Form",
        "page",
    ]
    assert "Page 2 of 3: Second page" in html
    assert "Shown only if Do you smoke? is answered Yes" in html
    assert "How many a day?" in html
    assert "Do you smoke?" not in html.split("Shown only if")[0]
    assert "Third page" not in html
    assert "<strong>everything</strong>" not in html
    assert "<form" not in html


@pytest.mark.django_db
def test_a_page_condition_names_its_question_as_rendered_text(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    form = FormFactory(title="Survey")
    first = FormPageFactory(form=form, title="First page", order=0)
    gate = FormQuestionFactory(form_page=first, question="**Did you** attend?", order=0)
    option = QuestionOptionFactory(question=gate, text="No", order=0)
    second = FormPageFactory(
        form=form, title="Second page", order=1, condition_option=option
    )
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={second.pk}", HTTP_HX_REQUEST="true"
    )

    (note,) = [
        p
        for p in lxml.html.fromstring(response.content).cssselect("p")
        if p.text_content().startswith("Shown only if")
    ]
    assert " ".join(note.text_content().split()) == (
        "Shown only if Did you attend? is answered No"
    )
    assert note.cssselect("p p") == []


@pytest.mark.django_db
def test_a_multi_page_form_previews_its_start_page(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    form, _second = _three_page_form()
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert response.status_code == 200
    assert "Survey (Preview)" in html
    assert "<strong>everything</strong>" in html
    assert "3 pages" in html
    assert "2 questions" in html
    for absent in ("Do you smoke?", "First page", "Shown only if", "<form", "Start"):
        assert absent not in html


@pytest.mark.django_db
def test_a_page_of_another_form_is_not_found(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    form, _second = _three_page_form()
    _other, other_page = _three_page_form(title="Other survey")
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={other_page.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_page_on_a_topic_is_not_found(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    _form, page = _three_page_form()
    course, item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={page.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_opening_a_form_preview_writes_nothing(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    form = FormFactory()
    page = FormPageFactory(form=form)
    FormQuestionFactory(form_page=page, type="file_upload")
    FormQuestionFactory(form_page=page, type="short_text")
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)
    counted = [
        TopicProgress,
        CourseProgress,
        LearnerCourseRegistration,
        AuditLogEntry,
        FormProgress,
        QuestionAnswer,
    ]
    before = [model.objects.count() for model in counted]

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert [model.objects.count() for model in counted] == before


@pytest.mark.django_db
def test_a_preview_of_another_courses_form_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_form()
    _other_course, other_item = _course_with_form()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_of_a_form_on_another_site_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_form()
    with site_context(SiteFactory()):
        _other_course, other_item = _course_with_form()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_form_of_a_course_belonging_only_to_another_organisation_cannot_be_previewed(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_form()
    course.organisations.add(OrganisationFactory())
    action_url = _content_action_url(organisation, course, "preview_content")

    action = staff_client.get(f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert action.status_code == 404


@pytest.mark.django_db
def test_a_form_preview_without_the_htmx_header_or_by_post_is_a_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_form()
    url = _preview_url(staff_client, organisation, course)

    plain_get = staff_client.get(f"{url}?item={item.pk}")
    post = staff_client.post(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
def test_a_user_with_no_role_cannot_preview_a_form(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_form()
    action_url = _content_action_url(organisation, course, "preview_content")

    response = logged_in_client(UserFactory()).get(
        f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


def _marks(document: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
    return [
        mark
        for mark in document.cssselect("span")
        if mark.text_content().strip().startswith("Correct answer")
    ]


@pytest.mark.django_db
def test_a_quiz_preview_marks_exactly_the_correct_options(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    form = FormFactory()
    page = FormPageFactory(form=form)
    single = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=single, text="Single right", correct=True, order=0)
    QuestionOptionFactory(question=single, text="Single wrong", order=1)
    several = FormQuestionFactory(form_page=page, type="checkboxes", order=1)
    QuestionOptionFactory(question=several, text="Box right 1", correct=True, order=0)
    QuestionOptionFactory(question=several, text="Box right 2", correct=True, order=1)
    QuestionOptionFactory(question=several, text="Box wrong", order=2)
    pick = FormQuestionFactory(form_page=page, type="dropdown", order=2)
    QuestionOptionFactory(question=pick, text="Pick right", correct=True, order=0)
    QuestionOptionFactory(question=pick, text="Pick wrong", order=1)
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content.decode())
    marks = _marks(document)
    assert response.status_code == 200
    assert len(marks) == 4
    assert all(mark.cssselect("svg") for mark in marks)
    labelled = [
        label.text_content()
        for label in document.cssselect("label")
        if label.cssselect("span") and _marks(label)
    ]
    assert len(labelled) == 3
    assert all("wrong" not in text for text in labelled)
    (dropdown_list,) = document.cssselect("ul")
    assert dropdown_list.text_content().split(":")[1].strip() == "Pick right"


def _course_details_preview_url(organisation: Organisation, course: CourseModel) -> str:
    return _content_action_url(organisation, course, "preview_course_details")


@pytest.mark.django_db
def test_the_course_content_table_opens_with_the_course_details_row(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    (panel,) = document.cssselect("section[data-panel='content']")
    assert panel.cssselect("header button") == []
    first_row = _outline_rows(panel)[0]
    assert "Course details" in first_row.text_content()
    (trigger,) = first_row.cssselect("button[hx-get]")
    assert trigger.get("hx-get") == _course_details_preview_url(organisation, course)
    assert trigger.text_content().strip() == "Preview"
    assert trigger.get("aria-label") == "Preview course details page"


@pytest.mark.django_db
def test_opening_the_course_details_preview_renders_the_learner_facing_page(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    course.title = "Intro to Rust"
    course.content = "Learn **ownership**"
    course.learning_outcomes = ["Borrow safely"]
    course.save()

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    html = response.content.decode()
    assert response.status_code == 200
    assert 'data-modal-size="wide"' in html
    assert "Intro to Rust (Preview)" in html
    assert "Course details" in html
    assert "Nothing here is saved." not in html
    assert "About this course" in html
    assert "learn" in html
    assert "Borrow safely" in html
    assert "<strong>ownership</strong>" in html
    assert "1 lesson" in html
    for absent in (
        "Course content",
        "Enrolment",
        "signup-panel",
        "express_interest",
        "<form",
        reverse("learner_interface:course_detail", args=[course.slug]) + "start",
    ):
        assert absent not in html


@pytest.mark.django_db
def test_opening_the_course_details_preview_writes_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    counted = [
        TopicProgress,
        CourseProgress,
        LearnerCourseRegistration,
        AuditLogEntry,
        FormProgress,
        QuestionAnswer,
    ]
    before = [model.objects.count() for model in counted]

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert [model.objects.count() for model in counted] == before


@pytest.mark.django_db
def test_the_course_details_preview_without_the_htmx_header_or_by_post_is_a_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    url = _course_details_preview_url(organisation, course)

    plain_get = staff_client.get(url)
    post = staff_client.post(url, HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
def test_a_course_belonging_only_to_another_organisation_has_no_details_preview(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    course.organisations.add(OrganisationFactory())

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_user_with_no_role_cannot_open_the_course_details_preview(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()

    response = logged_in_client(UserFactory()).get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


PREVIEW_AVAILABLE = [
    ("no_owner", True),
    ("owned", True),
    ("shared", True),
    ("held", False),
]


def _topic_item_of(course: CourseModel) -> uuid.UUID:
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    return cast(uuid.UUID, item.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "available"), PREVIEW_AVAILABLE)
def test_the_content_panel_shows_its_outline_only_for_an_available_course(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    row: str,
    available: bool,
) -> None:
    organisation = OrganisationFactory()
    course = course_per_reach_row(organisation)[row]
    _topic_item_of(course)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    panel = document.cssselect("section[data-panel='content']")[0]
    assert (len(panel.cssselect("#outline-table-caption")) == 1) is available
    assert (len(panel.cssselect("button[hx-get]")) > 0) is available
    assert (len(panel.cssselect("[data-testid='preview-withheld']")) == 1) is (
        not available
    )


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "available"), PREVIEW_AVAILABLE)
def test_the_preview_actions_answer_only_for_an_available_course(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    row: str,
    available: bool,
) -> None:
    organisation = OrganisationFactory()
    course = course_per_reach_row(organisation)[row]
    item_pk = _topic_item_of(course)
    client = logged_in_client(organisation_admin_viewer(organisation))
    content_url = _content_action_url(organisation, course, "preview_content")
    details_url = _content_action_url(organisation, course, "preview_course_details")

    content = client.get(f"{content_url}?item={item_pk}", HTTP_HX_REQUEST="true")
    details = client.get(details_url, HTTP_HX_REQUEST="true")

    expected = 200 if available else 404
    assert (content.status_code, details.status_code) == (expected, expected)


@pytest.mark.django_db
def test_a_form_page_of_a_course_held_only_through_a_registration_cannot_be_previewed(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    organisation = OrganisationFactory()
    course = course_per_reach_row(organisation)["held"]
    form = FormFactory()
    page = FormPageFactory(form=form)
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=form, order=0
    )
    client = logged_in_client(organisation_admin_viewer(organisation))
    url = _content_action_url(organisation, course, "preview_content")

    response = client.get(
        f"{url}?item={item.pk}&page={page.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404
