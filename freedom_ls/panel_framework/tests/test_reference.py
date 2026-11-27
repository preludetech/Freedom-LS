"""The component reference page: staff-only, every component, no query cost.

`component_reference` is a plain `staff_member_required` view, so most tests
run against the isolated test URLconf at `/test-panel/components/`
(`tests/urls.py`, `tests/root_urls.py`). One test exercises the real
`config.urls` include under `settings.DEBUG`, since that is the route a
developer actually uses.
"""

from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser

import pytest

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.urls import reverse

from ..actions import CHOOSE_AGAIN_MESSAGE
from ..reference import example_context
from .helpers import make_staff_user

pytestmark = pytest.mark.django_db

# One id prefix per component family the reference page documents, matching
# the section headings in _examples.html. `attention-list` and
# `attention-row` are separate names: both `panel-attention-list` and
# `panel-attention-row` are public components with their own example ids.
COMPONENT_NAMES = [
    "page-header",
    "stat-tile",
    "stat-row",
    "status-badge",
    "avatar-chip",
    "attention-list",
    "attention-row",
    "progress-bar",
    "card",
    "definition-list",
    "definition-row",
    "toolbar",
    "search-field",
    "filter-toggle",
    "applied-filter",
    "empty-state",
    "skeleton",
    "table",
    "list",
    "heading",
    "file-field",
    "callout",
    "reason-dialog",
    "lazy-panel",
    "editable-list",
    "data-table",
]


def _render_examples() -> str:
    return render_to_string(
        "panel_framework/reference/_examples.html",
        example_context(RequestFactory().get("/test-panel/components/")),
    )


def test_examples_partial_renders_with_no_queries(django_assert_num_queries) -> None:
    with django_assert_num_queries(0):
        _render_examples()


class _SidePanelDialogs(HTMLParser):
    """Records, per `x-data="sidePanel"` element, whether a `<dialog>` sits inside it."""

    VOID = {"input", "br", "hr", "img", "meta", "link"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, int | None]] = []
        self.has_dialog: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.VOID:
            return
        index: int | None = None
        if dict(attrs).get("x-data") == "sidePanel":
            index = len(self.has_dialog)
            self.has_dialog.append(False)
        if tag == "dialog":
            for _, open_index in self.stack:
                if open_index is not None:
                    self.has_dialog[open_index] = True
        self.stack.append((tag, index))

    def handle_endtag(self, tag: str) -> None:
        while self.stack:
            open_tag, _ = self.stack.pop()
            if open_tag == tag:
                break


def test_every_side_panel_in_the_examples_holds_a_dialog() -> None:
    """A sidePanel with no <dialog> throws in its init on the reference page."""
    html = _render_examples()
    parser = _SidePanelDialogs()
    parser.feed(html)
    assert False not in parser.has_dialog


def test_examples_partial_has_no_duplicate_ids() -> None:
    html = _render_examples()
    # `data-refocus-id="…"` names an element's id without being one.
    ids = Counter(re.findall(r'(?<![-\w])id="([^"]+)"', html))
    duplicates = {element_id: count for element_id, count in ids.items() if count > 1}
    assert duplicates == {}


@pytest.mark.parametrize(
    "example_id",
    [
        "reason-dialog-required",
        "reason-dialog-choices",
        "reason-dialog-choices-required",
        "modal-footer-stepping",
        "lazy-panel-as-of",
        "data-table-row-detail",
        "data-table-child-rows",
        "data-table-compact",
    ],
)
def test_reference_has_each_new_example(example_id: str) -> None:
    assert f'id="{example_id}"' in _render_examples()


def test_reference_lazy_panel_shows_its_as_of_stamp() -> None:
    assert "As of" in _render_examples()


def test_reference_child_rows_example_has_a_chevron_that_starts_open() -> None:
    html = _render_examples()
    assert 'aria-expanded="true"' in html


def test_reference_reason_dialogs_are_inert() -> None:
    html = _render_examples()
    assert html.count("hx-disable") >= 3


def test_reference_reason_dialogs_inset_their_body_like_the_app_modal() -> None:
    """The examples sit outside #app-modal, which supplies the body's side padding.

    Each example's wrapper has to supply it, or the body text and fields sit
    flush with the dialog's edges while the title and footer are inset.
    """
    html = _render_examples()
    wrappers = [
        w
        for w in re.findall(r'<div hx-disable class="([^"]*)"', html)
        if "overflow-hidden" in w
    ]
    assert len(wrappers) == 3
    assert all("[&_[data-modal-scroll]]:px-6" in w for w in wrappers)


def test_anonymous_user_is_redirected_to_admin_login(client: Client) -> None:
    response = client.get("/test-panel/components/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))


def test_non_staff_user_is_redirected_to_admin_login(
    client: Client, mock_site_context: object
) -> None:
    user = get_user_model().objects.create_user(
        email="learner@test.local",
        password="testpass",  # pragma: allowlist secret
        is_staff=False,
    )
    client.force_login(user)
    response = client.get("/test-panel/components/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))


def test_staff_user_gets_200(client: Client, mock_site_context: object) -> None:
    client.force_login(make_staff_user())
    response = client.get("/test-panel/components/")
    assert response.status_code == 200


def test_the_reference_page_under_the_minimal_shell_has_its_own_title_and_examples(
    client: Client, mock_site_context: object
) -> None:
    client.force_login(make_staff_user())

    html = client.get("/test-panel/components/").content.decode()

    title = re.search(r"<title>\s*(.*?)\s*</title>", html, re.DOTALL)
    main_start = html.index('id="interface-main"')
    assert title is not None
    assert title.group(1) == "Component reference"
    assert main_start < html.index('id="table-default"')


@pytest.mark.parametrize("component_name", COMPONENT_NAMES)
def test_every_component_has_at_least_one_example_id(
    client: Client, mock_site_context: object, component_name: str
) -> None:
    client.force_login(make_staff_user())
    response = client.get("/test-panel/components/")
    assert f'id="{component_name}-' in response.content.decode()


ROLE_BY_TONE = {"info": None, "warning": None, "error": "alert", "success": "status"}


@pytest.mark.parametrize("tone", ["info", "warning", "error", "success"])
def test_reference_shows_a_callout_in_each_tone(tone: str) -> None:
    """The reference page shows one `c-panel-callout` per tone."""
    html = _render_examples()
    block = html[html.index(f'id="callout-{tone}"') :]
    block = block[: block.index("</div>")]
    role = ROLE_BY_TONE[tone]

    if role is None:
        assert "role=" not in block
    else:
        assert f'role="{role}"' in block


def _example_block(html: str, example_id: str) -> str:
    """The markup of one example wrapper, up to the next example or section."""
    start = html.index(f'id="{example_id}"')
    ends = [html.find(marker, start) for marker in ('<div id="', "</section>")]
    return html[start : min(end for end in ends if end != -1)]


@pytest.mark.parametrize(
    "example_id", ["file-field-dialog", "file-field-error", "file-field-inline"]
)
def test_reference_shows_each_file_field_example(example_id: str) -> None:
    assert f'id="{example_id}"' in _render_examples()


def test_file_field_dialog_example_shows_the_current_file_and_a_remove_checkbox() -> (
    None
):
    block = _example_block(_render_examples(), "file-field-dialog")
    assert "Current file:" in block
    assert "first-aid-certificate.pdf" in block
    assert "certificates/2026/" not in block
    assert "Remove" in block
    assert 'type="checkbox"' in block
    assert 'type="file"' in block


def test_file_field_error_example_shows_the_choose_again_message_and_a_summary() -> (
    None
):
    block = _example_block(_render_examples(), "file-field-error")
    assert CHOOSE_AGAIN_MESSAGE in block
    assert "data-error-summary" in block


def test_file_field_inline_example_posts_multipart_with_no_remove_checkbox() -> None:
    block = _example_block(_render_examples(), "file-field-inline")
    assert 'hx-encoding="multipart/form-data"' in block
    assert "Remove" not in block
    assert 'type="checkbox"' not in block


def test_file_field_inline_example_wrapper_disables_htmx() -> None:
    """The inline example's Save used to post for real and nest a copy of the page."""
    html = _render_examples()
    start = html.index('<div id="file-field-inline"')
    assert "hx-disable" in html[start : html.index(">", start)]


def test_no_file_field_dialog_example_can_post() -> None:
    html = _render_examples()
    for example_id in ("file-field-dialog", "file-field-error"):
        assert "hx-post" not in _example_block(html, example_id)


@pytest.mark.parametrize("tone", ["info", "error", "success"])
def test_reference_callout_wrapper_spaces_its_explanatory_line_from_the_callout(
    tone: str,
) -> None:
    """The callout has no outer margin, so a wrapper holding an explanatory line
    above it must space its children or the line touches the callout."""
    from lxml import html as lxml_html

    root = lxml_html.fromstring(_render_examples())
    (wrapper,) = root.xpath(f'//div[@id="callout-{tone}"]')
    assert wrapper.xpath("./p")
    assert "space-y-" in wrapper.get("class", "")


@pytest.mark.parametrize("state", ["default", "empty", "cap", "table"])
def test_reference_shows_an_editable_list_in_each_state(state: str) -> None:
    assert f'id="editable-list-{state}"' in _render_examples()


def test_reference_editable_list_cap_example_hides_the_add_trigger() -> None:
    block = _example_block(_render_examples(), "editable-list-cap")
    assert "data-editable-list-cap" in block
    assert 'data-editable-list-action="add_entry"' not in block


def test_reference_editable_list_cap_example_shows_the_sentence_the_panel_renders() -> (
    None
):
    """The cap example used to word the cap line differently from the panel."""
    block = _example_block(_render_examples(), "editable-list-cap")
    assert "You can have up to 3. Remove one to add another." in block


def test_reference_editable_list_table_heads_its_column_with_the_singular_noun() -> (
    None
):
    """A real panel heads the column with its noun, which is singular; the
    example used to say "Contacts"."""
    html = _render_examples()
    block = html[html.index('id="editable-list-table"') :]
    first_header = re.search(r"<thead>.*?<th[^>]*>(.*?)</th>", block, re.S)
    assert first_header is not None
    assert first_header.group(1).strip() == "Contact"
