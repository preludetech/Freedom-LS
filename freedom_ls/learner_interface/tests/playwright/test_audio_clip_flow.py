"""Browser flow for the longer audio clip widget (``c-audio-clip``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, File
from freedom_ls.learner_interface.tests.playwright.helpers import form_item_url
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

FIXTURES = Path(__file__).parent / "fixtures"
TONE_MP3 = FIXTURES / "tone_30s.mp3"
BEEP_MP3 = FIXTURES / "beep.mp3"

FIRST_CLIP = "Dialogue one"
SECOND_CLIP = "Dialogue two"


def _audio_file(name: str, source: Path, duration_seconds: float | None) -> None:
    FileFactory(
        file_path=f"audio/{name}.mp3",
        file=SimpleUploadedFile(
            f"{name}.mp3", source.read_bytes(), content_type="audio/mpeg"
        ),
        file_type=File.FileType.AUDIO,
        mime_type="audio/mpeg",
        duration_seconds=duration_seconds,
    )


def _clip_course(user: User) -> Course:
    """A free course whose one topic holds two clips and one speak button."""
    course: Course = CourseFactory(
        title="Clip Course",
        slug="clip-course",
        file_path="courses/clip/course.md",
        access_config={"access_type": "free"},
    )
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    _audio_file("one", TONE_MP3, 30.0)
    _audio_file("two", TONE_MP3, 30.0)
    _audio_file("beep", BEEP_MP3, None)
    content = (
        f'<c-audio-clip src="audio/one.mp3" title="{FIRST_CLIP}"></c-audio-clip>\n\n'
        f'<c-audio-clip src="audio/two.mp3" title="{SECOND_CLIP}"></c-audio-clip>\n\n'
        '<c-audio src="audio/beep.mp3" label="Beep"></c-audio>'
    )
    topic = TopicFactory(title="Clip Topic", slug="clip-topic", content=content)
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    return course


def test_learner_plays_and_pauses_a_clip(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _clip_course(logged_in_user)
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))

    page.goto(form_item_url(live_server, course, "view_course_item"))

    play = page.get_by_role("button", name=f"Play {FIRST_CLIP}")
    group = page.get_by_role("group", name=FIRST_CLIP)
    expect(play).to_have_attribute("aria-pressed", "false")
    expect(group).to_contain_text("0:30")
    assert not [
        url for url in requested if "/content/audio/" in url or "/media/" in url
    ]

    play.click()
    expect(play).to_have_attribute("aria-pressed", "true")
    expect(play.locator("[data-icon='media_pause']")).to_be_visible()
    elapsed = group.locator("[x-text='elapsedText']")
    expect(elapsed).not_to_have_text("0:00")

    play.click()
    expect(play).to_have_attribute("aria-pressed", "false")
    expect(play.locator("[data-icon='media_play']")).to_be_visible()
    paused_at = elapsed.inner_text()
    page.wait_for_timeout(1000)
    expect(elapsed).to_have_text(paused_at)
