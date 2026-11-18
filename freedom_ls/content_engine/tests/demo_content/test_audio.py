"""The widgets demo course has to play its four phonetic-alphabet words, so
each `c-audio` widget can be heard without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.models import File, Topic

pytestmark = pytest.mark.fls_internal

DEMO_WORDS = ["bravo", "charlie", "oscar", "romeo"]


@pytest.mark.django_db
def test_the_demo_mp3_files_load_as_audio(site, loaded_demo_content, mock_site_context):
    file_types = {
        file.file_path.rsplit("/", 1)[-1]: file.file_type
        for file in File.objects.filter(site=site, file_path__endswith=".mp3")
    }

    assert file_types == {f"{word}.mp3": File.FileType.AUDIO for word in DEMO_WORDS}


@pytest.mark.django_db
def test_the_media_topic_renders_four_audio_widgets_without_red_boxes(
    site, loaded_demo_content, mock_site_context
):
    topic = Topic.objects.get(site=site, title="Media")

    rendered = topic.rendered_content()

    assert rendered.count("data-src=") == 4
    assert "Audio not found" not in rendered
    assert "Audio needs a label" not in rendered
