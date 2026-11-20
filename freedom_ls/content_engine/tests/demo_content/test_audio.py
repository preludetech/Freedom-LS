"""The widgets demo course has to play its four phonetic-alphabet words and
its one longer recording (shared by both `c-audio-clip` widgets), so each audio
widget can be heard without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import File, Topic

pytestmark = pytest.mark.fls_internal

DEMO_FILES = ["bravo", "charlie", "oscar", "romeo", "gettysburg"]


@pytest.mark.django_db
def test_the_demo_mp3_files_load_as_audio(
    site: Site, loaded_demo_content: Site, mock_site_context: object
) -> None:
    file_types = {
        file.file_path.rsplit("/", 1)[-1]: file.file_type
        for file in File.objects.filter(site=site, file_path__endswith=".mp3")
    }

    assert file_types == {f"{name}.mp3": File.FileType.AUDIO for name in DEMO_FILES}


@pytest.mark.django_db
def test_the_media_topic_renders_six_audio_widgets_without_red_boxes(
    site: Site, loaded_demo_content: Site, mock_site_context: object
) -> None:
    topic = Topic.objects.get(site=site, title="Media")

    rendered = topic.rendered_content()

    assert rendered.count('x-data="audioFile"') == 4
    assert rendered.count('x-data="audioClip"') == 2
    assert "Audio not found" not in rendered
    assert "Audio needs a label" not in rendered
    assert "Audio needs a title" not in rendered
