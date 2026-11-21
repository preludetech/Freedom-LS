"""Tests for the c-audio-clip component rendered through the markdown pipeline."""

from __future__ import annotations

import lxml.html
import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import FileFactory, TopicFactory
from freedom_ls.content_engine.models import File
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

pytestmark = pytest.mark.django_db

CLIP = '<c-audio-clip src="audio/talk.mp3" title="The talk"{extra}></c-audio-clip>'


def _render(markup: str) -> str:
    topic = TopicFactory()
    return str(render_markdown(markup, None, context={"content_instance": topic}))


def _tree(markup: str) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(_render(markup))


def _audio_file(duration_seconds: float | None = 198.4) -> File:
    file_obj: File = FileFactory(
        file_path="audio/talk.mp3",
        file_type=File.FileType.AUDIO,
        mime_type="audio/mpeg",
        duration_seconds=duration_seconds,
    )
    return file_obj


def _seek(tree: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (seek,) = tree.xpath("//input[@type='range']")
    return seek


class TestResolvedClip:
    def test_renders_group_with_title_and_title_attribute(
        self, mock_site_context: object
    ) -> None:
        _audio_file()

        tree = _tree(CLIP.format(extra=""))

        (group,) = tree.xpath("//div[@x-data='audioClip']")
        assert group.get("role") == "group"
        (title,) = tree.xpath("//span[@title='The talk']")
        assert title.text_content() == "The talk"

    def test_seek_bar_uses_the_unrounded_duration(
        self, mock_site_context: object
    ) -> None:
        _audio_file(198.4)

        tree = _tree(CLIP.format(extra=""))

        seek = _seek(tree)
        assert seek.get("max") == "198.4"
        assert seek.get("aria-valuetext") == "0 seconds of 3 minutes 18 seconds"
        assert seek.get("aria-label") == "Seek The talk"
        (times,) = tree.xpath("//span[@aria-hidden='true']")
        assert "3:18" in times.text_content()

    @pytest.mark.parametrize(
        ("duration", "elapsed", "total"),
        [(198.4, "0:00", "3:18"), (3725.0, "0:00:00", "1:02:05")],
    )
    def test_total_and_elapsed_text(
        self,
        mock_site_context: object,
        duration: float,
        elapsed: str,
        total: str,
    ) -> None:
        _audio_file(duration)

        tree = _tree(CLIP.format(extra=""))

        (elapsed_el,) = tree.xpath("//span[@x-text='elapsedText']")
        (total_el,) = tree.xpath("//span[@x-text='totalText']")
        assert elapsed_el.text_content() == elapsed
        assert total_el.text_content() == total

    def test_null_duration_shows_placeholder_and_disabled_seek(
        self, mock_site_context: object
    ) -> None:
        _audio_file(None)

        tree = _tree(CLIP.format(extra=""))

        (total_el,) = tree.xpath("//span[@x-text='totalText']")
        assert total_el.text_content() == "--:--"
        assert _seek(tree).get("disabled") is not None

    def test_known_duration_leaves_the_seek_bar_enabled(
        self, mock_site_context: object
    ) -> None:
        _audio_file(198.4)

        tree = _tree(CLIP.format(extra=""))

        assert _seek(tree).get("disabled") is None

    def test_seek_bar_binds_no_style(self, mock_site_context: object) -> None:
        """The seek bar bound a `--played` style that no CSS read; `accent-primary` fills it."""
        _audio_file(198.4)

        tree = _tree(CLIP.format(extra=""))

        assert _seek(tree).get("x-bind:style") is None
        assert "accent-primary" in _seek(tree).get("class", "")

    def test_kind_renders_when_given(self, mock_site_context: object) -> None:
        _audio_file()

        html = _render(CLIP.format(extra=' kind="Listening exercise"'))

        assert "Listening exercise" in html

    def test_no_kind_renders_no_kind_text(self, mock_site_context: object) -> None:
        _audio_file()

        html = _render(CLIP.format(extra=""))

        assert "Listening exercise" not in html
        assert "font-mono" not in html

    def test_unlisted_attribute_is_stripped(self, mock_site_context: object) -> None:
        _audio_file()

        html = _render(CLIP.format(extra=' onclick="alert(1)"'))

        assert "onclick" not in html

    def test_status_line_is_always_rendered(self, mock_site_context: object) -> None:
        _audio_file()

        tree = _tree(CLIP.format(extra=""))

        assert len(tree.xpath("//p[@role='status']")) == 1


class TestPlayButton:
    def test_play_button_carries_the_redirect_url_and_name(
        self, mock_site_context: object
    ) -> None:
        file_obj = _audio_file()

        tree = _tree(CLIP.format(extra=""))

        (button,) = tree.xpath("//button[@x-ref='play']")
        assert button.get("data-src") == reverse(
            "content_engine:audio_file", args=[file_obj.pk]
        )
        assert button.get("aria-label") == "Play The talk"
        assert button.get("x-bind:aria-pressed") == "playing"
        assert button.get("x-on:click") == "toggle"


class TestAuthorMistakes:
    def test_missing_file_renders_a_red_box(self, mock_site_context: object) -> None:
        html = _render(
            '<c-audio-clip src="audio/nope.mp3" title="Nope"></c-audio-clip>'
        )

        assert "Audio not found: audio/nope.mp3" in html
        assert "x-data" not in html

    def test_non_audio_file_renders_a_red_box(self, mock_site_context: object) -> None:
        FileFactory(file_path="notes.txt", file_type=File.FileType.OTHER)

        html = _render('<c-audio-clip src="notes.txt" title="Notes"></c-audio-clip>')

        assert "Audio not found: notes.txt" in html
        assert "x-data" not in html

    def test_empty_title_renders_a_red_box(self, mock_site_context: object) -> None:
        _audio_file()

        html = _render('<c-audio-clip src="audio/talk.mp3"></c-audio-clip>')

        assert "Audio needs a title: audio/talk.mp3" in html
        assert "x-data" not in html

    def test_valid_clip_shows_no_error(self, mock_site_context: object) -> None:
        _audio_file()

        html = _render(CLIP.format(extra=""))

        assert "Audio not found" not in html
        assert "Audio needs a title" not in html


class TestErrorState:
    def test_empty_status_line_is_always_rendered(
        self, mock_site_context: object
    ) -> None:
        _audio_file()

        tree = _tree(CLIP.format(extra=""))

        (status,) = tree.xpath("//p[@role='status']")
        assert status.get("x-text") == "statusText"
        assert (status.text or "").strip() == ""

    def test_play_button_carries_the_retry_name_for_the_error_state(
        self, mock_site_context: object
    ) -> None:
        _audio_file()

        tree = _tree(CLIP.format(extra=""))

        (button,) = tree.xpath("//button[@data-retry-label='Try again: The talk']")
        assert button.get("aria-label") == "Play The talk"
        assert not tree.xpath("//button[normalize-space()='Try again']")


class TestTranscript:
    def test_transcript_renders_a_toggle_and_a_markdown_panel(
        self, mock_site_context: object
    ) -> None:
        _audio_file()
        markup = (
            '<c-audio-clip src="audio/talk.mp3" title="The talk">\n\n'
            "First paragraph.\n\nSecond paragraph.\n\n</c-audio-clip>"
        )

        tree = _tree(markup)

        (toggle,) = tree.xpath("//button[@*[name()='x-on:click']='toggleTranscript']")
        assert "Show transcript" in toggle.text_content()
        (panel,) = tree.xpath("//div[@x-show='transcriptOpen']")
        assert [p.text_content() for p in panel.xpath(".//p")] == [
            "First paragraph.",
            "Second paragraph.",
        ]

    def test_whitespace_only_slot_renders_no_toggle_or_panel(
        self, mock_site_context: object
    ) -> None:
        _audio_file()

        tree = _tree(
            '<c-audio-clip src="audio/talk.mp3" title="The talk">\n\n \n\n</c-audio-clip>'
        )

        assert not tree.xpath("//button[@*[name()='x-on:click']='toggleTranscript']")
        assert not tree.xpath("//div[@x-show='transcriptOpen']")

    def test_no_slot_renders_no_toggle(self, mock_site_context: object) -> None:
        _audio_file()

        tree = _tree(CLIP.format(extra=""))

        assert not tree.xpath("//button[@*[name()='x-on:click']='toggleTranscript']")

    def test_script_and_event_handler_in_the_transcript_are_stripped(
        self, mock_site_context: object
    ) -> None:
        _audio_file()
        markup = (
            '<c-audio-clip src="audio/talk.mp3" title="The talk">\n\n'
            'Safe words <script>alert("xss")</script>'
            '<img src="x" onerror="alert(1)">\n\n</c-audio-clip>'
        )

        html = _render(markup)

        assert "Safe words" in html
        assert "<script" not in html
        assert "onerror" not in html
