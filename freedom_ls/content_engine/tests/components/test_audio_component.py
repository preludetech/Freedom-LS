"""Tests for the c-audio component rendered through the markdown pipeline."""

from __future__ import annotations

import lxml.html
import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import FileFactory, TopicFactory
from freedom_ls.content_engine.models import File
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

pytestmark = pytest.mark.django_db


def _render(markup: str) -> str:
    topic = TopicFactory()
    return str(render_markdown(markup, None, context={"content_instance": topic}))


def _render_tree(markup: str) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(_render(markup))


def _respelling(tree: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (element,) = tree.xpath("//*[@*[name()='x-bind:id']=\"$id('audio-respelling')\"]")
    return element


def _audio_file(file_path: str) -> File:
    file_obj: File = FileFactory(
        file_path=file_path,
        file_type=File.FileType.AUDIO,
        mime_type="audio/mpeg",
    )
    return file_obj


class TestResolvedAudioFile:
    def test_renders_label_and_playback_hooks(self, mock_site_context: object) -> None:
        file_obj = _audio_file("audio/bravo.mp3")

        html = _render('<c-audio src="audio/bravo.mp3" label="Bravo"></c-audio>')

        assert "Bravo" in html
        assert 'x-data="audioFile"' in html
        assert 'aria-label="Play pronunciation of Bravo"' in html
        assert 'x-bind:aria-pressed="playing"' in html
        redirect = reverse("content_engine:audio_file", args=[file_obj.pk])
        assert f'data-src="{redirect}"' in html

    def test_src_label_and_respelling_survive_sanitising(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render(
            '<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH VOH">'
            "</c-audio>"
        )

        assert "Bravo" in html
        assert "BRAH VOH" in html
        assert "data-src=" in html

    def test_unlisted_attribute_is_stripped(self, mock_site_context: object) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render(
            '<c-audio src="audio/bravo.mp3" label="Bravo" onclick="alert(1)"></c-audio>'
        )

        assert "onclick" not in html


class TestRespelling:
    def test_respelling_renders_and_describes_the_button(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render(
            '<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH VOH">'
            "</c-audio>"
        )

        assert "BRAH VOH" in html
        assert "x-id=\"['audio-respelling']\"" in html
        assert "x-bind:id=\"$id('audio-respelling')\"" in html
        assert "x-bind:aria-describedby=\"$id('audio-respelling')\"" in html

    def test_two_widgets_on_one_file_share_no_server_rendered_id(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render(
            '<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH VOH">'
            "</c-audio>\n\n"
            '<c-audio src="audio/bravo.mp3" label="bravo" respelling="brah-voh">'
            "</c-audio>"
        )

        assert ' id="audio-respelling' not in html
        assert html.count("x-bind:id=\"$id('audio-respelling')\"") == 2

    def test_no_respelling_renders_no_respelling_element_or_description(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render('<c-audio src="audio/bravo.mp3" label="Bravo"></c-audio>')

        assert "audio-respelling" not in html
        assert 'x-bind:aria-describedby="null"' in html


class TestErrorLine:
    def test_status_line_is_always_rendered_and_its_text_follows_failure(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render('<c-audio src="audio/bravo.mp3" label="Bravo"></c-audio>')

        status_line = (
            '<p role="status" x-text="failed ? '
            "'Audio could not be played. Try again.' : ''\""
        )
        assert status_line in html
        assert 'x-show="failed"' not in html


class TestAuthorMistakes:
    def test_missing_file_renders_a_red_box_naming_the_src(
        self, mock_site_context: object
    ) -> None:
        html = _render('<c-audio src="audio/nope.mp3" label="Nope"></c-audio>')

        assert "Audio not found: audio/nope.mp3" in html
        assert "bg-error/10" in html
        assert "x-data" not in html

    def test_non_audio_file_renders_a_red_box_naming_the_src(
        self, mock_site_context: object
    ) -> None:
        FileFactory(file_path="notes.txt", file_type=File.FileType.OTHER)

        html = _render('<c-audio src="notes.txt" label="Notes"></c-audio>')

        assert "Audio not found: notes.txt" in html
        assert "x-data" not in html

    def test_empty_label_renders_a_red_box_naming_the_src(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render('<c-audio src="audio/bravo.mp3"></c-audio>')

        assert "Audio needs a label: audio/bravo.mp3" in html
        assert "x-data" not in html


class TestInsideGrid:
    def test_playback_attributes_survive_inside_a_grid(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render(
            '<c-grid columns="2">\n\n'
            '<c-audio src="audio/bravo.mp3" label="Bravo"></c-audio>\n\n'
            "</c-grid>"
        )

        assert 'x-data="audioFile"' in html
        assert 'x-on:click="toggle"' in html
        assert "data-src=" in html


class TestSymbol:
    def test_symbol_renders_a_tile_hidden_from_screen_readers(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/november.mp3")

        tree = _render_tree(
            '<c-audio src="audio/november.mp3" label="November" symbol="N"></c-audio>'
        )

        (tile,) = tree.xpath("//span[@aria-hidden='true']")
        assert tile.text_content() == "N"

    def test_no_symbol_renders_no_tile(self, mock_site_context: object) -> None:
        _audio_file("audio/november.mp3")

        tree = _render_tree(
            '<c-audio src="audio/november.mp3" label="November"></c-audio>'
        )

        assert tree.xpath("//span[@aria-hidden='true']") == []


class TestRespellingStress:
    def test_stressed_syllable_is_emphasised_and_the_text_reads_as_authored(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/november.mp3")

        tree = _render_tree(
            '<c-audio src="audio/november.mp3" label="November" '
            'respelling="no-VEM-ber"></c-audio>'
        )

        respelling = _respelling(tree)
        assert respelling.text_content() == "no-VEM-ber"
        assert respelling.xpath(".//strong/text()") == ["VEM"]

    def test_respelling_all_in_capitals_emphasises_nothing(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        tree = _render_tree(
            '<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH VOH">'
            "</c-audio>"
        )

        respelling = _respelling(tree)
        assert respelling.text_content() == "BRAH VOH"
        assert respelling.xpath(".//strong") == []


class TestPlaybackIcons:
    def test_playing_state_shows_the_audio_playing_icon(
        self, mock_site_context: object
    ) -> None:
        _audio_file("audio/bravo.mp3")

        tree = _render_tree('<c-audio src="audio/bravo.mp3" label="Bravo"></c-audio>')

        icon = tree.xpath("//button//span[@x-show='playing']//svg/@data-icon")
        assert icon == ["audio_playing"]
