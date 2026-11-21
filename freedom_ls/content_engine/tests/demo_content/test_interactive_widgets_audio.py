"""The Interactive Widgets demo topic has to show the say-it-then-reveal cards
and a flashcard that plays its answer, so the audio widgets can be tried
without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Topic

pytestmark = pytest.mark.fls_internal


@pytest.mark.django_db
def test_the_interactive_widgets_topic_renders_four_audio_reveals_and_one_flashcard_player_without_red_boxes(
    site: Site, loaded_demo_content: Site, mock_site_context: object
) -> None:
    topic = Topic.objects.get(site=site, title="Interactive Widgets")

    rendered = topic.rendered_content()

    assert rendered.count('x-data="audioReveal"') == 4
    assert rendered.count('x-data="audioFile"') == 1
    assert "Audio not found" not in rendered
    assert "Audio needs a label" not in rendered
    assert "Audio reveal needs a symbol" not in rendered
