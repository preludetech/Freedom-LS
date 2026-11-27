"""Tests for the course outline and the content previews."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.db.models import Model
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course as CourseModel
from freedom_ls.content_engine.models import CourseAudience, File
from freedom_ls.educator_interface.panels.course.content_preview import (
    OutlineRow,
    outline_rows,
    preview_sequence,
    reference_rows,
)
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
from freedom_ls.form_engine.models import (
    FormProgress,
    FormStrategy,
    QuestionAnswer,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import (
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.retire import retired
from freedom_ls.tests.site_context import site_context

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


@pytest.mark.django_db
def test_course_page_buttons_are_only_preview_triggers(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(title="Intro"), order=0
    )

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content"),
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


def _course_content_panel(
    client: Client, course: CourseModel, *, panel: str = "content"
) -> lxml.html.HtmlElement:
    organisation = OrganisationFactory()
    document = _get_document(
        client,
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content"),
    )
    (found,) = document.cssselect(f"section[data-panel='{panel}']")
    return found


def _outline_rows(
    panel: lxml.html.HtmlElement, label: str = "Course outline items"
) -> list[lxml.html.HtmlElement]:
    return list(panel.cssselect(f"[aria-label='{label}'] tbody tr"))


def _outline_numbers(
    panel: lxml.html.HtmlElement, label: str = "Course outline items"
) -> list[str]:
    numbers = [
        cell.text_content().strip()
        for row in _outline_rows(panel, label)
        for cell in row.cssselect("td.tabular-nums")[:1]
    ]
    return [number for number in numbers if number]


REFERENCE_LABEL = "Reference outline items"


def _reference_part(course: CourseModel, order: int, topic_count: int) -> Model:
    """A reference part of the course holding `topic_count` topics."""
    part = CoursePartFactory(title=f"Reference part {order}")
    CourseReferencePartFactory(course=course, course_part=part, order=order)
    for position in range(topic_count):
        ContentCollectionItemFactory(
            collection_object=part, child_object=TopicFactory(), order=position
        )
    return cast(Model, part)


@pytest.mark.django_db
def test_the_reference_panel_lists_parts_in_order_numbered_within_itself(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    _reference_part(course, order=1, topic_count=1)
    _reference_part(course, order=0, topic_count=2)

    panel = _course_content_panel(staff_client, course, panel="reference")

    assert _outline_numbers(panel, REFERENCE_LABEL) == ["1.", "1.1", "1.2", "2.", "2.1"]
    first_row = _outline_rows(panel, REFERENCE_LABEL)[0]
    assert "Reference part 0" in first_row.cssselect("td")[1].text_content()
    assert "Course details" not in panel.text_content()
    assert panel.cssselect("header button") == []


@pytest.mark.django_db
def test_reference_parts_sharing_an_order_are_numbered_by_primary_key(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    for title, pk in (("Field guide", 2), ("Glossary", 1)):
        CourseReferencePartFactory(
            id=uuid.UUID(int=pk),
            course=course,
            course_part=CoursePartFactory(title=title),
            order=0,
        )

    panel = _course_content_panel(staff_client, course, panel="reference")

    text = panel.cssselect(f"[aria-label='{REFERENCE_LABEL}'] tbody")[0].text_content()
    assert _outline_numbers(panel, REFERENCE_LABEL) == ["1.", "2."]
    assert text.index("Glossary") < text.index("Field guide")


@pytest.mark.django_db
def test_the_reference_numbers_start_at_one_beside_a_learning_path_topic(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    _reference_part(course, order=0, topic_count=0)

    panel = _course_content_panel(staff_client, course, panel="reference")

    assert _outline_numbers(panel, REFERENCE_LABEL) == ["1."]


@pytest.mark.django_db
def test_reference_parts_do_not_change_the_course_content_rows_or_count(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    part = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    _reference_part(course, order=0, topic_count=2)

    panel = _course_content_panel(staff_client, course)

    assert _outline_numbers(panel) == ["1.", "1.1"]
    (count,) = panel.cssselect("[data-entry-count]")
    assert count.text_content().strip() == "2 course outline items"


@pytest.mark.django_db
def test_the_reference_footer_counts_parts_and_topics(staff_client: Client) -> None:
    course = CourseFactory()
    _reference_part(course, order=0, topic_count=2)

    panel = _course_content_panel(staff_client, course, panel="reference")

    (count,) = panel.cssselect("[data-entry-count]")
    assert count.text_content().strip() == "3 reference outline items"


@pytest.mark.django_db
def test_a_course_without_reference_parts_shows_the_empty_note_and_no_count(
    staff_client: Client,
) -> None:
    panel = _course_content_panel(staff_client, CourseFactory(), panel="reference")

    assert "No reference material in this course yet." in panel.text_content()
    assert _outline_numbers(panel, REFERENCE_LABEL) == []
    assert panel.cssselect("[data-entry-count]") == []


@pytest.mark.django_db
def test_an_empty_reference_part_shows_its_note_and_counts_as_one_item(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    _reference_part(course, order=0, topic_count=0)

    panel = _course_content_panel(staff_client, course, panel="reference")

    assert "No items in this part." in panel.text_content()
    (count,) = panel.cssselect("[data-entry-count]")
    assert count.text_content().strip() == "1 reference outline item"


@pytest.mark.django_db
def test_a_reference_part_holding_a_form_and_a_nested_part_renders(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    part = CoursePartFactory()
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    form = FormFactory()
    FormPageFactory(form=form)
    ContentCollectionItemFactory(collection_object=part, child_object=form, order=0)
    nested = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=part, child_object=nested, order=1)
    ContentCollectionItemFactory(
        collection_object=nested, child_object=TopicFactory(), order=0
    )

    panel = _course_content_panel(staff_client, course, panel="reference")

    assert _outline_numbers(panel, REFERENCE_LABEL) == ["1.", "1.1", "1.2", "1.2.1"]


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
def test_the_course_content_and_reference_tables_start_collapsed(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    _reference_part(course, order=0, topic_count=1)

    for name in ("content", "reference"):
        panel = _course_content_panel(staff_client, course, panel=name)

        assert len(panel.cssselect("table[data-child-rows-collapsed]")) == 1
        assert len(panel.cssselect("ul[data-child-rows-collapsed]")) == 1


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
def test_outline_tables_switch_to_cards_by_their_own_containers_width(
    staff_client: Client,
) -> None:
    """Both outline tables stayed tables at a 768 viewport because they
    switched on the viewport instead of on the width of their container."""
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )

    panel = _course_content_panel(staff_client, course)

    (wrapper,) = panel.cssselect("[data-table-layout]")
    assert "@container" in wrapper.get("class", "").split()
    (region,) = wrapper.cssselect("[role='region']")
    assert "@min-[58rem]:block" in region.get("class", "").split()


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
    url = _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")

    with django_assert_max_num_queries(60):
        assert staff_client.get(url).status_code == 200


@pytest.mark.django_db
def test_reference_panel_query_count_does_not_grow_with_topics(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()

    def page_query_count(topic_count: int) -> int:
        course = cast(CourseModel, CourseFactory())
        # The order also keeps the part titles, and so their slugs, apart.
        _reference_part(course, order=topic_count, topic_count=topic_count)
        url = _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")
        assert staff_client.get(url).status_code == 200
        with CaptureQueriesContext(connection) as queries:
            assert staff_client.get(url).status_code == 200
        return len(queries.captured_queries)

    assert page_query_count(1) == page_query_count(12)


def _preview_url(
    client: Client,
    organisation: Organisation,
    course: CourseModel,
    *,
    panel: str = "content",
) -> str:
    """The Preview action's URL as the course page publishes it, without
    the item parameter."""
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")
    )
    trigger = document.cssselect(
        f"section[data-panel='{panel}'] table button[hx-get*='preview_content']"
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
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")
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
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")
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
    course_url = _interface_url(
        organisation.slug, f"courses/{course.pk}/__tabs/content"
    )
    preview_url = _preview_url(staff_client, organisation, course)

    preview = staff_client.get(
        f"{preview_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    ).content.decode()
    course_page = staff_client.get(course_url).content.decode()

    assert "data-src=" in preview
    assert "content_engine/js/alpine-components.js" in course_page


@pytest.mark.django_db
def test_a_topic_preview_renders_an_audio_reveal(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    FileFactory(
        file_path="bravo.mp3", file_type=File.FileType.AUDIO, mime_type="audio/mpeg"
    )
    topic = TopicFactory(
        content='<c-audio-reveal src="bravo.mp3" label="Bravo" symbol="B"></c-audio-reveal>\n'
    )
    course, item = _course_with_topic(topic)
    preview_url = _preview_url(staff_client, organisation, course)

    preview = staff_client.get(
        f"{preview_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    ).content.decode()

    assert 'x-data="audioReveal"' in preview


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

    page = staff_client.get(
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")
    )
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


def _drawing_page_preview(
    client: Client, form: Model, page: Model | None
) -> lxml.html.HtmlElement:
    """The read-only preview of one page of the form, or of its start page."""
    organisation = OrganisationFactory()
    course, item = _course_with_form(form)
    url = _preview_url(client, organisation, course)
    query = f"item={item.pk}" + (f"&page={page.pk}" if page else "")
    response = client.get(f"{url}?{query}", HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return lxml.html.fromstring(response.content)


def _drawing_lines(document: lxml.html.HtmlElement) -> list[str]:
    return [
        " ".join(p.text_content().split())
        for p in document.cssselect("p")
        if p.text_content().strip().startswith("Draws")
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("group_size", "unit_count", "draw", "expected"),
    [
        (1, 4, 2, "Draws 2 of 4 questions per attempt"),
        (2, 3, 2, "Draws 2 of 3 groups (4 questions) per attempt"),
    ],
)
def test_a_drawing_page_preview_says_what_a_sitting_draws(
    staff_client: Client,
    group_size: int,
    unit_count: int,
    draw: int,
    expected: str,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Pool", order=0, draw=draw)
    for unit in range(unit_count):
        for member in range(group_size):
            FormQuestionFactory(
                form_page=page,
                order=unit * group_size + member,
                question=f"Pool question {unit}-{member}",
                group=f"case-{unit}" if group_size > 1 else "",
            )

    document = _drawing_page_preview(staff_client, form, page)

    assert _drawing_lines(document) == [expected]
    html = lxml.html.tostring(document, encoding="unicode")
    for unit in range(unit_count):
        for member in range(group_size):
            assert f"Pool question {unit}-{member}" in html


@pytest.mark.django_db
def test_a_page_with_no_draw_has_no_drawing_line(staff_client: Client) -> None:
    form, second = _three_page_form()

    document = _drawing_page_preview(staff_client, form, second)

    assert _drawing_lines(document) == []


@pytest.mark.django_db
def test_the_start_page_counts_only_what_a_sitting_draws(
    staff_client: Client,
) -> None:
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    pool = FormPageFactory(form=form, order=0, draw=2)
    for order in range(5):
        FormQuestionFactory(form_page=pool, order=order)
    plain = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=plain, order=0)

    document = _drawing_page_preview(staff_client, form, None)

    text = " ".join(document.text_content().split())
    assert "3 questions" in text
    assert "6 questions" not in text


@pytest.mark.django_db
def test_a_drawing_quiz_row_states_the_per_sitting_question_count(
    staff_client: Client,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ)
    pool = FormPageFactory(form=form, order=0, draw=2)
    for order in range(5):
        FormQuestionFactory(form_page=pool, order=order)
    plain = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=plain, order=0)

    document = _drawing_page_preview(staff_client, form, None)

    assert _quiz_facts_block(document)["Questions"] == "3"


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
        and mark.getparent().tag != "span"
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
        staff_client,
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content"),
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


def _reference_topic_item_of(course: CourseModel) -> uuid.UUID:
    """The collection item of a topic held by a reference part of `course`."""
    part = CoursePartFactory()
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    item = ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    return cast(uuid.UUID, item.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "available"), PREVIEW_AVAILABLE)
@pytest.mark.parametrize(
    ("panel_key", "caption"),
    [("content", "#outline-table-caption"), ("reference", "#reference-table-caption")],
)
def test_a_course_panel_shows_its_outline_only_for_an_available_course(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    panel_key: str,
    caption: str,
    row: str,
    available: bool,
) -> None:
    organisation = OrganisationFactory()
    course = course_per_reach_row(organisation)[row]
    _topic_item_of(course)
    _reference_topic_item_of(course)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content")
    )

    panel = document.cssselect(f"section[data-panel='{panel_key}']")[0]
    assert (len(panel.cssselect(caption)) == 1) is available
    assert (len(panel.cssselect("button[hx-get]")) > 0) is available
    assert (len(panel.cssselect("[data-testid='preview-withheld']")) == 1) is (
        not available
    )


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "available"), PREVIEW_AVAILABLE)
def test_the_reference_preview_answers_only_for_an_available_course(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    row: str,
    available: bool,
) -> None:
    organisation = OrganisationFactory()
    course = course_per_reach_row(organisation)[row]
    item_pk = _reference_topic_item_of(course)
    client = logged_in_client(organisation_admin_viewer(organisation))
    url = _content_action_url(
        organisation, course, "preview_content", panel="reference"
    )

    response = client.get(f"{url}?item={item_pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == (200 if available else 404)


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


def _reference_topic_item(course: CourseModel, title: str = "Cheat sheet") -> Model:
    """The collection item placing a topic in a reference part of `course`."""
    part = CoursePartFactory()
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    return cast(
        Model,
        ContentCollectionItemFactory(
            collection_object=part, child_object=TopicFactory(title=title), order=0
        ),
    )


def _reference_preview(
    client: Client, organisation: Organisation, course: CourseModel, item: Model
) -> _MonkeyPatchedWSGIResponse:
    url = _content_action_url(
        organisation, course, "preview_content", panel="reference"
    )
    return client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")


@pytest.mark.django_db
def test_a_reference_topic_row_carries_a_preview_trigger_on_the_reference_url(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    item = _reference_topic_item(course)

    panel = _course_content_panel(staff_client, course, panel="reference")

    (trigger,) = panel.cssselect("table button[aria-label='Preview Cheat sheet']")
    assert trigger.get("hx-get").endswith(
        f"/__tabs/content/__panels/reference/__actions/preview_content?item={item.pk}"
    )


@pytest.mark.django_db
def test_opening_a_reference_topic_preview_renders_it_read_only(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    item = _reference_topic_item(course)

    response = _reference_preview(staff_client, organisation, course, item)

    html = response.content.decode()
    assert response.status_code == 200
    assert "Cheat sheet (Preview)" in html
    assert "Topic" in html
    assert "max-w-reading" in html


@pytest.mark.django_db
def test_a_reference_item_is_a_404_on_the_course_content_url(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    item = _reference_topic_item(course)
    url = _content_action_url(organisation, course, "preview_content")

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_learning_path_item_is_a_404_on_the_reference_url(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    _reference_topic_item(course)

    response = _reference_preview(staff_client, organisation, course, item)

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_reference_item_listed_only_by_another_course_is_a_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _reference_topic_item(course)
    other_item = _reference_topic_item(CourseFactory(), title="Other")

    response = _reference_preview(staff_client, organisation, course, other_item)

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_reference_item_on_another_site_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _reference_topic_item(course)
    with site_context(SiteFactory()):
        other_item = _reference_topic_item(CourseFactory(), title="Other")

    response = _reference_preview(staff_client, organisation, course, other_item)

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_part_nested_in_a_reference_part_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    nested_item = ContentCollectionItemFactory(
        collection_object=part, child_object=CoursePartFactory(), order=0
    )

    response = _reference_preview(staff_client, organisation, course, nested_item)

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_reference_part_pk_is_a_404(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    reference_part = CourseReferencePartFactory(course=course, course_part=part)

    response = _reference_preview(
        staff_client, organisation, course, cast(Model, reference_part)
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "item", ["", "not-a-uuid", "6f1c2f0e-3c1b-4a5e-9a57-0d1f6d3a9b11"]
)
def test_a_reference_preview_with_a_missing_or_malformed_item_is_a_404(
    staff_client: Client, item: str
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _reference_topic_item(course)
    url = _content_action_url(
        organisation, course, "preview_content", panel="reference"
    )

    response = staff_client.get(f"{url}?item={item}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_reference_preview_without_the_htmx_header_or_by_post_is_a_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    item = _reference_topic_item(course)
    url = _content_action_url(
        organisation, course, "preview_content", panel="reference"
    )

    plain_get = staff_client.get(f"{url}?item={item.pk}")
    post = staff_client.post(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
@pytest.mark.parametrize("listing_course", [0, 1])
def test_a_topic_in_a_shared_reference_part_previews_through_each_listing_course(
    staff_client: Client, listing_course: int
) -> None:
    organisation = OrganisationFactory()
    courses = [CourseFactory(), CourseFactory()]
    item = _reference_topic_item(courses[0])
    CourseReferencePartFactory(course=courses[1], course_part=item.collection, order=0)

    response = _reference_preview(
        staff_client, organisation, courses[listing_course], item
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_topic_in_a_reference_part_is_a_404_through_a_course_that_does_not_list_it(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    listing_course = CourseFactory()
    other_course = CourseFactory()
    item = _reference_topic_item(listing_course)
    _reference_topic_item(other_course, title="Own")

    response = _reference_preview(staff_client, organisation, other_course, item)

    assert response.status_code == 404


def test_outline_tables_fix_the_width_of_every_column_but_title() -> None:
    """The number, type and action columns of both outline tables carry fixed
    widths on header and cell, so stacked tables line up. They used to size
    themselves to their own content and drifted apart."""
    from freedom_ls.educator_interface.panels.course.content_preview import (
        CourseOutlineTable,
        ReferenceOutlineTable,
    )

    for table in (CourseOutlineTable, ReferenceOutlineTable):
        columns = {column.header: column for column in table.get_columns()}
        for header in ("#", "Type", "Actions"):
            column = columns[header]
            header_widths = [
                c for c in column.header_class.split() if c.startswith("w-")
            ]
            cell_widths = [c for c in column.cell_class.split() if c.startswith("w-")]
            assert header_widths, (table, header)
            assert header_widths != ["w-0"], (table, header)
            assert cell_widths == header_widths, (table, header)
        assert columns["Title"].header_class == "w-full"
        assert columns["Title"].cell_class == "w-full"


@pytest.mark.django_db
def test_outline_actions_header_stays_in_table_layout_with_a_hidden_label(
    staff_client: Client,
) -> None:
    """The Actions header cell stays a table cell and only its label is hidden
    visually. It used to be taken out of the layout (sr-only on the th itself),
    so an outline table with no rows misaligned its Type column and overflowed
    the page."""
    panel = _course_content_panel(staff_client, CourseFactory(), panel="reference")

    (actions,) = [
        th
        for th in panel.cssselect("thead th")
        if th.text_content().strip() == "Actions"
    ]
    assert "sr-only" not in actions.get("class", "").split()
    assert actions.cssselect("span.sr-only")


def _stepping_course() -> tuple[CourseModel, dict[str, Model]]:
    """A course holding topic A, a part holding topic B and a two-page form,
    an empty part, and a closing topic C, in that order."""
    course = cast(CourseModel, CourseFactory())
    items: dict[str, Model] = {}

    def place(parent: Model, child: Model, order: int, name: str) -> Model:
        item = cast(
            Model,
            ContentCollectionItemFactory(
                collection_object=parent, child_object=child, order=order
            ),
        )
        items[name] = item
        return item

    place(course, TopicFactory(title="Topic A"), 0, "a")
    part = CoursePartFactory(title="Part one")
    place(course, part, 1, "part")
    place(part, TopicFactory(title="Topic B"), 0, "b")
    form = FormFactory(title="Survey")
    pages = [
        FormPageFactory(form=form, title="Survey page 1", order=0),
        FormPageFactory(form=form, title="Survey page 2", order=1),
    ]
    items["page1"], items["page2"] = pages
    place(part, form, 1, "form")
    place(course, CoursePartFactory(title="Empty part"), 2, "empty")
    place(course, TopicFactory(title="Topic C"), 3, "c")
    return course, items


@pytest.mark.django_db
def test_the_preview_sequence_runs_depth_first_across_parts_and_form_pages(
    mock_site_context: object,
) -> None:
    course, _items = _stepping_course()

    sequence = preview_sequence(outline_rows(course, may_view_questions=True))

    assert [row.title for row in sequence] == [
        "Course details",
        "Topic A",
        "Topic B",
        "Survey",
        "Survey page 1",
        "Survey page 2",
        "Topic C",
    ]


@pytest.mark.django_db
def test_an_empty_course_has_only_the_course_details_to_step_through(
    mock_site_context: object,
) -> None:
    course = cast(CourseModel, CourseFactory())

    sequence = preview_sequence(outline_rows(course, may_view_questions=True))

    assert [row.title for row in sequence] == ["Course details"]


@pytest.mark.django_db
def test_a_one_topic_course_sequence_is_the_details_then_the_topic(
    mock_site_context: object,
) -> None:
    course, _item = _course_with_topic(TopicFactory(title="Only"))

    sequence = preview_sequence(
        outline_rows(cast(CourseModel, course), may_view_questions=True)
    )

    assert [row.title for row in sequence] == ["Course details", "Only"]


@pytest.mark.django_db
def test_the_reference_sequence_has_no_details_row_and_no_parts(
    mock_site_context: object,
) -> None:
    course = cast(CourseModel, CourseFactory())
    _reference_topic_item(course, "Cheat sheet")

    sequence = preview_sequence(reference_rows(course, may_view_questions=True))

    assert [row.title for row in sequence] == ["Cheat sheet"]


def _stepping_buttons(
    response: _MonkeyPatchedWSGIResponse,
) -> dict[str, lxml.html.HtmlElement]:
    document = lxml.html.fromstring(response.content.decode())
    (footer,) = document.cssselect("footer[data-modal-footer]")
    return {
        (button.text_content().strip()): button for button in footer.cssselect("button")
    }


def _step_target(button: lxml.html.HtmlElement) -> str:
    """The `item` and `page` query of a stepping button, or the details
    marker when it opens the course details."""
    url = str(button.get("hx-get"))
    if url.endswith("preview_course_details"):
        return "details"
    return url.split("?", 1)[1]


@pytest.mark.django_db
def test_the_course_details_preview_has_previous_disabled_and_next_on_the_first_item(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, items = _stepping_course()

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    buttons = _stepping_buttons(response)
    assert buttons["Previous"].get("disabled") is not None
    assert buttons["Previous"].get("hx-get") is None
    assert _step_target(buttons["Next"]) == f"item={items['a'].pk}"


@pytest.mark.django_db
def test_a_topic_preview_steps_across_a_part_boundary_both_ways(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, items = _stepping_course()
    url = _content_action_url(organisation, course, "preview_content")

    first = _stepping_buttons(
        staff_client.get(f"{url}?item={items['a'].pk}", HTTP_HX_REQUEST="true")
    )
    middle = _stepping_buttons(
        staff_client.get(f"{url}?item={items['b'].pk}", HTTP_HX_REQUEST="true")
    )

    assert _step_target(first["Previous"]) == "details"
    assert _step_target(first["Next"]) == f"item={items['b'].pk}"
    assert _step_target(middle["Previous"]) == f"item={items['a'].pk}"
    assert _step_target(middle["Next"]) == f"item={items['form'].pk}"


@pytest.mark.django_db
def test_a_multi_page_form_steps_to_its_first_page_and_its_last_page_to_the_next_item(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, items = _stepping_course()
    url = _content_action_url(organisation, course, "preview_content")
    form_pk, page1, page2 = items["form"].pk, items["page1"].pk, items["page2"].pk

    own = _stepping_buttons(
        staff_client.get(f"{url}?item={form_pk}", HTTP_HX_REQUEST="true")
    )
    last_page = _stepping_buttons(
        staff_client.get(f"{url}?item={form_pk}&page={page2}", HTTP_HX_REQUEST="true")
    )

    assert _step_target(own["Next"]) == f"item={form_pk}&page={page1}"
    assert _step_target(last_page["Previous"]) == f"item={form_pk}&page={page1}"
    assert _step_target(last_page["Next"]) == f"item={items['c'].pk}"


@pytest.mark.django_db
def test_the_last_row_has_next_disabled(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    course, items = _stepping_course()
    url = _content_action_url(organisation, course, "preview_content")

    response = staff_client.get(f"{url}?item={items['c'].pk}", HTTP_HX_REQUEST="true")

    buttons = _stepping_buttons(response)
    assert buttons["Next"].get("disabled") is not None
    assert buttons["Next"].get("hx-get") is None
    assert buttons["Previous"].get("hx-get") is not None


@pytest.mark.django_db
def test_a_reference_preview_steps_only_within_the_reference_list(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = cast(CourseModel, CourseFactory())
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(title="Path"), order=0
    )
    part = CoursePartFactory()
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    first = ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(title="Ref 1"), order=0
    )
    second = ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(title="Ref 2"), order=1
    )

    buttons = _stepping_buttons(
        _reference_preview(staff_client, organisation, course, cast(Model, first))
    )

    assert buttons["Previous"].get("disabled") is not None
    assert buttons["Previous"].get("hx-get") is None
    next_url = str(buttons["Next"].get("hx-get"))
    assert "/__panels/reference/__actions/preview_content" in next_url
    assert next_url.endswith(f"?item={second.pk}")


@pytest.mark.django_db
def test_the_stepping_footer_has_no_close_and_swaps_the_whole_dialog(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course, items = _stepping_course()
    url = _content_action_url(organisation, course, "preview_content")

    response = staff_client.get(f"{url}?item={items['b'].pk}", HTTP_HX_REQUEST="true")

    buttons = _stepping_buttons(response)
    assert list(buttons) == ["Previous", "Next"]
    for button in buttons.values():
        assert button.get("hx-target") == "#app-modal-body"
        assert button.get("hx-swap") == "innerHTML"


@pytest.mark.django_db
def test_a_topic_preview_query_count_stays_bounded_with_parts_and_a_multi_page_form(
    staff_client: Client, django_assert_max_num_queries
) -> None:
    organisation = OrganisationFactory()
    course, items = _stepping_course()
    url = _content_action_url(organisation, course, "preview_content")
    request_url = f"{url}?item={items['b'].pk}"
    assert staff_client.get(request_url, HTTP_HX_REQUEST="true").status_code == 200

    with django_assert_max_num_queries(20):
        assert staff_client.get(request_url, HTTP_HX_REQUEST="true").status_code == 200


def _quiz(pages: int, **fields: object) -> tuple[Model, list[Model]]:
    """A quiz with the given number of pages, each holding one question that
    draws nothing; returns the form and its pages."""
    form = FormFactory(title="Safety quiz", strategy=FormStrategy.QUIZ, **fields)
    form_pages = [
        FormPageFactory(form=form, title=f"Quiz page {number}", order=number)
        for number in range(pages)
    ]
    for form_page in form_pages:
        FormQuestionFactory(form_page=form_page, question="Is it safe?", order=0)
    return cast(Model, form), [cast(Model, page) for page in form_pages]


def _quiz_facts_block(document: lxml.html.HtmlElement) -> dict[str, str]:
    """The label and value of each row of the preview's definition list."""
    return {
        " ".join(row.cssselect("dt")[0].text_content().split()): " ".join(
            row.cssselect("dd")[0].text_content().split()
        )
        for row in document.cssselect("dl > div")
    }


@pytest.mark.django_db
def test_a_multi_page_quiz_row_shows_its_facts_in_place_of_the_count_chips(
    staff_client: Client,
) -> None:
    form, _pages = _quiz(
        2,
        quiz_pass_percentage=80,
        quiz_show_incorrect=True,
        submit_on_exit=True,
        shuffle_pages=False,
        shuffle_questions=True,
        shuffle_options=False,
    )

    document = _drawing_page_preview(staff_client, form, None)

    assert _quiz_facts_block(document) == {
        "Pages": "2",
        "Questions": "2",
        "Pass mark": "80%",
        "Shows incorrect answers": "Yes",
        "Submits on exit": "Yes",
        "Shuffle pages": "No",
        "Shuffle questions": "Yes",
        "Shuffle options": "No",
    }
    text = document.text_content()
    assert "2 questions" not in text
    assert "2 pages" not in text


@pytest.mark.django_db
def test_a_one_page_quiz_row_shows_its_facts_and_then_its_page(
    staff_client: Client,
) -> None:
    form, _pages = _quiz(1, quiz_pass_percentage=50)

    document = _drawing_page_preview(staff_client, form, None)

    assert _quiz_facts_block(document)["Pages"] == "1"
    html = lxml.html.tostring(document, encoding="unicode")
    assert html.index("Pass mark") < html.index("Quiz page 0")
    assert "Is it safe?" in html


@pytest.mark.django_db
def test_a_quiz_without_a_pass_mark_or_incorrect_answer_setting_says_so(
    staff_client: Client,
) -> None:
    form, _pages = _quiz(2, quiz_pass_percentage=None, quiz_show_incorrect=None)

    facts = _quiz_facts_block(_drawing_page_preview(staff_client, form, None))

    assert facts["Pass mark"] == "None set"
    assert facts["Shows incorrect answers"] == "No"


@pytest.mark.django_db
def test_a_survey_row_shows_the_count_chips_and_no_facts(
    staff_client: Client,
) -> None:
    form, _second = _three_page_form()

    document = _drawing_page_preview(staff_client, form, None)

    assert document.cssselect("dl") == []
    assert "3 pages" in document.text_content()


@pytest.mark.django_db
def test_a_quiz_page_row_shows_no_facts(staff_client: Client) -> None:
    form, pages = _quiz(2)

    document = _drawing_page_preview(staff_client, form, pages[1])

    assert document.cssselect("dl") == []
    assert "Quiz page 1" in document.text_content()


def _flagged_titles(rows: list[OutlineRow]) -> list[str]:
    """The titles of every row at any depth that is flagged retired."""
    return [
        title
        for row in rows
        for title in ([row.title] if row.retired else [])
        + _flagged_titles(list(row.children))
    ]


@pytest.mark.django_db
def test_outline_rows_flag_a_retired_topic_and_nothing_else(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(title="Live"), order=0
    )
    ContentCollectionItemFactory(
        collection_object=course,
        child_object=retired(TopicFactory(title="Gone")),
        order=1,
    )

    assert _flagged_titles(outline_rows(course, may_view_questions=True)) == ["Gone"]


@pytest.mark.django_db
def test_outline_rows_flag_a_retired_part_but_not_its_live_children(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    part = retired(CoursePartFactory(title="Old part"))
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(title="Kept"), order=0
    )

    assert _flagged_titles(outline_rows(course, may_view_questions=True)) == [
        "Old part"
    ]


@pytest.mark.django_db
def test_outline_rows_flag_a_retired_form(mock_site_context: Site) -> None:
    course = CourseFactory()
    form = retired(FormFactory(title="Old quiz"))
    FormPageFactory(form=form, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)

    assert _flagged_titles(outline_rows(course, may_view_questions=True)) == [
        "Old quiz"
    ]


@pytest.mark.django_db
def test_outline_rows_flag_a_retired_form_page_but_not_its_form(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    form = FormFactory(title="Survey")
    FormPageFactory(form=form, title="Kept page", order=0)
    retired(FormPageFactory(form=form, title="Old page", order=1))
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)

    assert _flagged_titles(outline_rows(course, may_view_questions=True)) == [
        "Old page"
    ]


@pytest.mark.django_db
def test_reference_rows_flag_a_retired_part_and_a_retired_topic(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    retired_part = retired(CoursePartFactory(title="Old reference"))
    CourseReferencePartFactory(course=course, course_part=retired_part, order=0)
    live_part = CoursePartFactory(title="Live reference")
    CourseReferencePartFactory(course=course, course_part=live_part, order=1)
    ContentCollectionItemFactory(
        collection_object=live_part,
        child_object=retired(TopicFactory(title="Old glossary")),
        order=0,
    )

    assert _flagged_titles(reference_rows(course, may_view_questions=True)) == [
        "Old reference",
        "Old glossary",
    ]


@pytest.mark.django_db
def test_the_rendered_outline_shows_a_retired_badge_for_exactly_the_retired_rows(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    for order, topic in enumerate(
        [
            TopicFactory(title="Live one"),
            retired(TopicFactory(title="Gone one")),
            TopicFactory(title="Live two"),
        ]
    ):
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=order
        )

    panel = _course_content_panel(staff_client, course)

    badged = [
        " ".join(row.text_content().split())
        for row in _outline_rows(panel)
        if "Retired" in row.text_content()
    ]
    assert len(badged) == 1
    assert "Gone one" in badged[0]


@pytest.mark.django_db
def test_the_rendered_outline_cards_show_the_retired_badge(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course,
        child_object=retired(TopicFactory(title="Gone one")),
        order=0,
    )

    panel = _course_content_panel(staff_client, course)

    details_card, topic_card = panel.cssselect("li.panel-data-table-card")
    assert "Retired" not in details_card.text_content()
    assert "Retired" in topic_card.text_content()


@pytest.mark.django_db
def test_a_form_preview_badges_exactly_the_retired_question_and_option(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    form = FormFactory(title="Intake")
    page = FormPageFactory(form=form, order=0)
    live = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=live, text="Live option", order=0)
    retired(QuestionOptionFactory(question=live, text="Gone option", order=1))
    retired(FormQuestionFactory(form_page=page, type="short_text", order=1))
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content)
    assert response.content.decode().count("Retired") == 2
    (option_label,) = [
        label
        for label in document.cssselect("label")
        if "Gone option" in label.text_content()
    ]
    assert "Retired" in option_label.text_content()
    (live_label,) = [
        label
        for label in document.cssselect("label")
        if "Live option" in label.text_content()
    ]
    assert "Retired" not in live_label.text_content()


@pytest.mark.django_db
def test_a_dropdown_preview_badges_a_retired_option(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    form = FormFactory(title="Intake")
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type="dropdown", order=0)
    QuestionOptionFactory(question=question, text="Live option", order=0)
    retired(QuestionOptionFactory(question=question, text="Gone option", order=1))
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content)
    (gone,) = [
        option
        for option in document.cssselect("select option")
        if "Gone option" in option.text_content()
    ]
    assert gone.text_content().strip() == "Gone option (Retired)"
    assert response.content.decode().count("Retired") == 1


def _question_viewer_client(organisation: Organisation, *, holds_role: bool) -> Client:
    """A client for a staff member of `organisation`, who holds the question
    bank viewer role too when `holds_role`."""
    user = cast(User, UserFactory(staff=True))
    grantor = cast(User, UserFactory(superuser=True))
    assign_role(grantor, user, "organisation_admin", organisation)
    if holds_role:
        assign_role(grantor, user, "question_bank_viewer", organisation)
    client = Client()
    client.force_login(user)
    return client


def _available_course(organisation: Organisation) -> CourseModel:
    course = cast(CourseModel, CourseFactory(audience=CourseAudience.PUBLIC))
    course.organisations.add(organisation)
    return course


def _quiz_form(title: str = "Safety quiz", pages: int = 1) -> Model:
    form = FormFactory(title=title, strategy=FormStrategy.QUIZ)
    for order in range(pages):
        page = FormPageFactory(form=form, title=f"Page {order + 1}", order=order)
        FormQuestionFactory(form_page=page, question=f"Question {order + 1}")
    return cast(Model, form)


def _place(course: CourseModel, child: Model, order: int = 0) -> Model:
    return cast(
        Model,
        ContentCollectionItemFactory(
            collection_object=course, child_object=child, order=order
        ),
    )


def _preview_get(
    client: Client,
    organisation: Organisation,
    course: CourseModel,
    query: str,
    *,
    htmx: bool = True,
    panel: str = "content",
) -> _MonkeyPatchedWSGIResponse:
    url = _content_action_url(organisation, course, "preview_content", panel=panel)
    extra = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    return client.get(f"{url}?{query}", **extra)


def _question_views() -> list[AuditLogEntry]:
    return list(AuditLogEntry.unscoped.filter(action="question.viewed"))


def _quiz_course_rows(
    may_view_questions: bool, *, in_part: bool, reference: bool
) -> list[OutlineRow]:
    """The outline rows of a course whose only quiz has two pages, placed in
    the learning path or the reference list, in a part or not."""
    course = cast(CourseModel, CourseFactory())
    quiz = _quiz_form(pages=2)
    if reference:
        part = CoursePartFactory()
        CourseReferencePartFactory(course=course, course_part=part, order=0)
        _place(part, quiz)
        _place(part, TopicFactory(title="Reference topic"), 1)
        return reference_rows(course, may_view_questions=may_view_questions)
    if in_part:
        part = CoursePartFactory()
        _place(course, part)
        _place(part, quiz)
        _place(part, TopicFactory(title="Part topic"), 1)
    else:
        _place(course, quiz)
        _place(course, TopicFactory(title="Loose topic"), 1)
    return outline_rows(course, may_view_questions=may_view_questions)


def _flatten(rows: list[OutlineRow]) -> list[OutlineRow]:
    return [found for row in rows for found in (row, *_flatten(list(row.children)))]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("in_part", "reference"), [(False, False), (True, False), (False, True)]
)
def test_without_the_permission_a_quiz_and_its_pages_are_withheld_and_nothing_else(
    mock_site_context: object, in_part: bool, reference: bool
) -> None:
    rows = _flatten(_quiz_course_rows(False, in_part=in_part, reference=reference))

    withheld = [row for row in rows if row.preview_withheld]
    assert [row.title for row in withheld] == [
        "Safety quiz",
        "Page 1",
        "Page 2",
    ]
    assert [row.preview_query for row in withheld] == ["", "", ""]
    assert all(row.preview_query for row in rows if row.kind == "topic")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("in_part", "reference"), [(False, False), (True, False), (False, True)]
)
def test_with_the_permission_no_row_is_withheld_and_every_row_previews(
    mock_site_context: object, in_part: bool, reference: bool
) -> None:
    rows = _flatten(_quiz_course_rows(True, in_part=in_part, reference=reference))

    assert not any(row.preview_withheld for row in rows)
    assert all(
        row.preview_query for row in rows if row.kind in {"form", "page", "topic"}
    )


@pytest.mark.django_db
def test_the_preview_sequence_omits_withheld_rows(mock_site_context: object) -> None:
    rows = _quiz_course_rows(False, in_part=False, reference=False)

    assert [row.title for row in preview_sequence(rows)] == [
        "Course details",
        "Loose topic",
    ]


@pytest.mark.django_db
def test_a_survey_row_is_not_withheld(mock_site_context: object) -> None:
    course = cast(CourseModel, CourseFactory())
    _place(course, FormFactory(title="Plain survey"))

    rows = _flatten(outline_rows(course, may_view_questions=False))

    assert not any(row.preview_withheld for row in rows)


@pytest.mark.django_db
def test_a_non_holders_outline_disables_each_quiz_preview_and_keeps_others(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course = _available_course(organisation)
    _place(course, TopicFactory(title="Intro"), 0)
    _place(course, _quiz_form("Safety quiz", pages=2), 1)
    _place(course, FormFactory(title="Plain survey"), 2)
    client = _question_viewer_client(organisation, holds_role=False)

    document = _get_document(
        client,
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content"),
    )

    panel = document.cssselect("section[data-panel='content']")[0]
    disabled = panel.cssselect("table button[disabled]")
    assert {button.get("aria-label") for button in disabled} == {
        "Needs permission to preview Safety quiz",
        "Needs permission to preview Safety quiz: Page 1",
        "Needs permission to preview Safety quiz: Page 2",
    }
    for button in disabled:
        assert button.text_content().strip() == "Needs permission"
        # The cell holds the button alone: a sentence beside it wraps.
        assert button.getparent().text_content().strip() == "Needs permission"
        assert not any(name.startswith("hx-") for name in button.attrib)
    assert "question bank viewer role" not in panel.text_content()
    assert {
        button.get("aria-label") for button in panel.cssselect("table button[hx-get]")
    } == {
        "Preview course details page",
        "Preview Intro",
        "Preview Plain survey",
    }


@pytest.mark.django_db
def test_an_outline_card_labels_its_type_and_footers_its_button(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course = _available_course(organisation)
    _place(course, TopicFactory(title="Intro"), 0)
    _place(course, _quiz_form("Safety quiz", pages=1), 1)
    client = _question_viewer_client(organisation, holds_role=False)

    document = _get_document(
        client,
        _interface_url(organisation.slug, f"courses/{course.pk}/__tabs/content"),
    )

    panel = document.cssselect("section[data-panel='content']")[0]
    cards = panel.cssselect("li.panel-data-table-card")
    for title, kind, button in (
        ("Intro", "Topic", "Preview"),
        ("Safety quiz", "Form", "Needs permission"),
    ):
        (card,) = [
            card
            for card in cards
            if title in card.cssselect("[data-card-title]")[0].text_content()
        ]
        (row,) = card.cssselect("dl > div")
        assert row.cssselect("dt")[0].text_content().strip() == "Type"
        assert row.cssselect("dd")[0].text_content().strip() == kind
        (footer,) = card.cssselect("[data-item-footer]")
        assert "mt-3" in footer.get("class", "").split()
        assert footer.cssselect("button")[0].text_content().strip() == button


@pytest.mark.django_db
def test_a_non_holders_topic_next_link_skips_the_quiz(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course = _available_course(organisation)
    first = _place(course, TopicFactory(title="First"), 0)
    _place(course, _quiz_form(), 1)
    last = _place(course, TopicFactory(title="Last"), 2)
    client = _question_viewer_client(organisation, holds_role=False)

    response = _preview_get(client, organisation, course, f"item={first.pk}")

    assert _step_target(_stepping_buttons(response)["Next"]) == f"item={last.pk}"


def _quiz_in_course(
    organisation: Organisation, pages: int
) -> tuple[CourseModel, Model, Model]:
    course = _available_course(organisation)
    quiz = _quiz_form(f"Safety quiz {uuid.uuid4().hex[:8]}", pages=pages)
    return course, _place(course, quiz), quiz.pages.first()


def _cohort_only_client(organisation: Organisation) -> Client:
    user = cast(User, UserFactory(staff=True))
    cohort = CohortFactory(organisation=organisation)
    assign_role(cast(User, UserFactory(superuser=True)), user, "cohort_admin", cohort)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("pages", [1, 2])
def test_a_non_holder_asking_for_a_quiz_directly_is_refused_and_logs_nothing(
    mock_site_context: object, pages: int
) -> None:
    organisation = cast(Organisation, OrganisationFactory(name="Acme Training"))
    course, item, first_page = _quiz_in_course(organisation, pages)
    client = _question_viewer_client(organisation, holds_role=False)

    item_response = _preview_get(client, organisation, course, f"item={item.pk}")
    page_response = _preview_get(
        client, organisation, course, f"item={item.pk}&page={first_page.pk}"
    )

    assert (item_response.status_code, page_response.status_code) == (403, 403)
    assert "Acme Training" in item_response.content.decode()
    assert _question_views() == []


@pytest.mark.django_db
def test_a_holder_of_a_cohort_role_only_is_refused_a_quiz_preview(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course, item, _page = _quiz_in_course(organisation, 1)
    client = _cohort_only_client(organisation)

    response = _preview_get(client, organisation, course, f"item={item.pk}")

    assert response.status_code != 200
    assert _question_views() == []


@pytest.mark.django_db
def test_a_holders_quiz_page_preview_writes_one_entry_describing_the_view(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course, item, first_page = _quiz_in_course(organisation, 2)
    form = item.child
    client = _question_viewer_client(organisation, holds_role=True)

    response = _preview_get(
        client, organisation, course, f"item={item.pk}&page={first_page.pk}"
    )

    (entry,) = _question_views()
    assert response.status_code == 200
    assert (entry.target_object_id, entry.organisation, entry.target_label) == (
        str(course.pk),
        organisation,
        course.title,
    )
    assert entry.details == {
        "surface": "preview",
        "forms": [{"id": str(form.pk), "title": form.title}],
        "page": {"id": str(first_page.pk), "number": 1},
    }


@pytest.mark.django_db
def test_a_second_view_by_a_holder_writes_a_second_entry(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course, item, first_page = _quiz_in_course(organisation, 2)
    client = _question_viewer_client(organisation, holds_role=True)
    _preview_get(client, organisation, course, f"item={item.pk}&page={first_page.pk}")

    _preview_get(client, organisation, course, f"item={item.pk}&page={first_page.pk}")

    assert len(_question_views()) == 2


@pytest.mark.django_db
def test_a_single_page_quizs_form_row_logs_page_one_and_a_multi_page_intro_logs_nothing(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    client = _question_viewer_client(organisation, holds_role=True)
    multi_course, multi_item, _page = _quiz_in_course(organisation, 2)
    _preview_get(client, organisation, multi_course, f"item={multi_item.pk}")
    nothing_logged = _question_views()
    single_course, single_item, only_page = _quiz_in_course(organisation, 1)

    _preview_get(client, organisation, single_course, f"item={single_item.pk}")

    (entry,) = _question_views()
    assert nothing_logged == []
    assert entry.details["page"] == {"id": str(only_page.pk), "number": 1}


@pytest.mark.django_db
def test_a_non_htmx_quiz_request_by_a_holder_is_a_404_and_logs_nothing(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course, item, _page = _quiz_in_course(organisation, 1)
    client = _question_viewer_client(organisation, holds_role=True)

    response = _preview_get(client, organisation, course, f"item={item.pk}", htmx=False)

    assert response.status_code == 404
    assert _question_views() == []


@pytest.mark.django_db
def test_a_superusers_quiz_preview_succeeds_and_is_logged(
    mock_site_context: object, staff_client: Client
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course, item, _page = _quiz_in_course(organisation, 1)

    response = _preview_get(staff_client, organisation, course, f"item={item.pk}")

    assert response.status_code == 200
    assert len(_question_views()) == 1


@pytest.mark.django_db
def test_topic_and_survey_previews_write_no_question_entry(
    mock_site_context: object, staff_client: Client
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course = _available_course(organisation)
    topic = _place(course, TopicFactory(), 0)
    survey = _place(course, FormFactory(), 1)
    survey_page = FormPageFactory(form=survey.child)

    _preview_get(staff_client, organisation, course, f"item={topic.pk}")
    _preview_get(staff_client, organisation, course, f"item={survey.pk}")
    _preview_get(
        staff_client, organisation, course, f"item={survey.pk}&page={survey_page.pk}"
    )

    assert _question_views() == []


@pytest.mark.django_db
def test_a_shared_courses_entry_belongs_to_the_viewers_organisation(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    owner = cast(Organisation, OrganisationFactory())
    course = cast(CourseModel, CourseFactory(audience=CourseAudience.PUBLIC))
    course.organisations.add(owner)
    course.shared_with.add(organisation)
    item = _place(course, _quiz_form())
    client = _question_viewer_client(organisation, holds_role=True)

    _preview_get(client, organisation, course, f"item={item.pk}")

    (entry,) = _question_views()
    assert entry.organisation == organisation


@pytest.mark.django_db
def test_the_audit_log_shows_a_quiz_title_with_markup_escaped(
    mock_site_context: object,
) -> None:
    organisation = cast(Organisation, OrganisationFactory())
    course = _available_course(organisation)
    item = _place(course, _quiz_form("<b>Bold</b> quiz"))
    client = _question_viewer_client(organisation, holds_role=True)
    _preview_get(client, organisation, course, f"item={item.pk}")

    html = client.get(_interface_url(organisation.slug, "audit-log")).content.decode()

    assert "Course preview: &lt;b&gt;Bold&lt;/b&gt; quiz" in html
    assert "<b>Bold</b>" not in html
