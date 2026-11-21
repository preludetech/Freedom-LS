"""Tests for the c-audio-reveal component rendered through the markdown pipeline."""

from __future__ import annotations

import lxml.html
import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import FileFactory
from freedom_ls.content_engine.models import File
from freedom_ls.content_engine.tests.components.helpers import (
    audio_file,
    render,
    render_tree,
)

pytestmark = pytest.mark.django_db

MARKUP = (
    '<c-audio-reveal src="audio/november.mp3" label="November" '
    'respelling="no-VEM-ber" symbol="N"></c-audio-reveal>'
)


def _by_attribute(
    tree: lxml.html.HtmlElement, name: str, value: str
) -> list[lxml.html.HtmlElement]:
    return list(tree.xpath(f"//*[@*[name()='{name}']=\"{value}\"]"))


def _answer_region(tree: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (element,) = _by_attribute(tree, "x-bind:id", "$id('audio-answer')")
    return element


class TestResolvedWidget:
    def test_tile_holds_the_symbol_and_is_not_hidden_from_screen_readers(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        tree = render_tree(MARKUP)

        (tile,) = tree.xpath("//span[contains(@class, 'size-12')]")
        assert tile.text_content() == "N"
        assert tile.get("aria-hidden") is None

    def test_label_and_respelling_sit_inside_the_answer_region(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        answer = _answer_region(render_tree(MARKUP))

        text = answer.text_content()
        assert "November" in text
        assert "no-VEM-ber" in text

    def test_root_carries_the_component_hooks(self, mock_site_context: object) -> None:
        file_obj = audio_file("audio/november.mp3")

        tree = render_tree(MARKUP)

        (root,) = tree.xpath("//*[@x-data='audioReveal']")
        assert root.get("x-id") == "['audio-respelling', 'audio-answer']"
        assert root.get("data-label") == "November"
        assert root.get("data-src") == reverse(
            "content_engine:audio_file", args=[file_obj.pk]
        )

    def test_play_button_data_src_equals_the_root_data_src(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        tree = render_tree(MARKUP)

        (root,) = tree.xpath("//*[@x-data='audioReveal']")
        (button,) = _by_attribute(tree, "x-on:click", "toggle")
        assert button.get("data-src") == root.get("data-src")

    def test_answer_region_is_inert_and_aria_hidden_until_revealed(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        answer = _answer_region(render_tree(MARKUP))

        assert answer.get("inert") is not None
        assert answer.get("aria-hidden") == "true"
        assert answer.get("x-bind:inert") == "!revealed"
        assert answer.get("x-bind:aria-hidden") == "!revealed"

    def test_reveal_button_binds_its_state_and_click(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        tree = render_tree(MARKUP)

        (button,) = _by_attribute(tree, "x-on:click", "toggleReveal")
        assert button.get("x-bind:aria-expanded") == "revealed"
        assert button.get("x-bind:aria-controls") == "$id('audio-answer')"

    def test_status_element_announces_the_answer(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        tree = render_tree(MARKUP)

        (status,) = _by_attribute(tree, "x-text", "announcement")
        assert status.get("role") == "status"


class TestAuthorMistakes:
    @pytest.mark.parametrize(
        ("markup", "message"),
        [
            (
                '<c-audio-reveal src="audio/nope.mp3" label="Nope" symbol="N">'
                "</c-audio-reveal>",
                "Audio not found: audio/nope.mp3",
            ),
            (
                '<c-audio-reveal src="notes.txt" label="Notes" symbol="N">'
                "</c-audio-reveal>",
                "Audio not found: notes.txt",
            ),
            (
                '<c-audio-reveal src="audio/november.mp3" symbol="N"></c-audio-reveal>',
                "Audio needs a label: audio/november.mp3",
            ),
            (
                '<c-audio-reveal src="audio/november.mp3" label="November">'
                "</c-audio-reveal>",
                "Audio reveal needs a symbol: audio/november.mp3",
            ),
        ],
        ids=["missing-file", "non-audio-file", "empty-label", "empty-symbol"],
    )
    def test_renders_a_red_box_naming_the_problem(
        self, mock_site_context: object, markup: str, message: str
    ) -> None:
        audio_file("audio/november.mp3")
        FileFactory(file_path="notes.txt", file_type=File.FileType.OTHER)

        html = render(markup)

        assert message in html
        assert "bg-error/10" in html
        assert "x-data" not in html


class TestSanitising:
    def test_the_four_attributes_survive(self, mock_site_context: object) -> None:
        audio_file("audio/november.mp3")

        html = render(MARKUP)

        assert "November" in html
        assert "VEM" in html
        assert 'x-data="audioReveal"' in html
        assert "data-src=" in html

    def test_unlisted_attribute_is_stripped(self, mock_site_context: object) -> None:
        audio_file("audio/november.mp3")

        html = render(
            '<c-audio-reveal src="audio/november.mp3" label="November" symbol="N" '
            'onclick="alert(1)"></c-audio-reveal>'
        )

        assert "onclick" not in html


class TestInsideGrid:
    def test_component_hooks_survive_inside_a_grid(
        self, mock_site_context: object
    ) -> None:
        audio_file("audio/november.mp3")

        html = render(f'<c-grid columns="2">\n\n{MARKUP}\n\n</c-grid>')

        assert 'x-data="audioReveal"' in html
        assert "data-src=" in html


class TestInsideSlotWidgets:
    @pytest.mark.parametrize(
        "wrapped",
        [
            f'<c-accordion title="Say it">\n\n{MARKUP}\n\n</c-accordion>',
            (
                "<c-flashcard>\n"
                '<c-slot name="front">\n\nQuestion\n\n</c-slot>\n'
                f'<c-slot name="back">\n\n{MARKUP}\n\n</c-slot>\n'
                "</c-flashcard>"
            ),
        ],
        ids=["accordion", "flashcard-back"],
    )
    def test_component_hooks_survive(
        self, mock_site_context: object, wrapped: str
    ) -> None:
        audio_file("audio/november.mp3")

        tree = render_tree(wrapped)

        (root,) = tree.xpath("//*[@x-data='audioReveal']")
        assert root.get("data-src")
        assert len(_by_attribute(tree, "x-on:click", "toggleReveal")) == 1
