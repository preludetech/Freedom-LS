"""Tests for the c-audio component rendered through the markdown pipeline."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import FileFactory, TopicFactory
from freedom_ls.content_engine.models import File
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

pytestmark = pytest.mark.django_db


def _render(markup: str) -> str:
    topic = TopicFactory()
    return str(render_markdown(markup, None, context={"content_instance": topic}))


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
        assert "data-src=" in html

    def test_unlisted_attribute_is_stripped(self, mock_site_context: object) -> None:
        _audio_file("audio/bravo.mp3")

        html = _render(
            '<c-audio src="audio/bravo.mp3" label="Bravo" onclick="alert(1)"></c-audio>'
        )

        assert "onclick" not in html
