"""Browser flow for the longer audio clip widget (``c-audio-clip``)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Locator, Page, Route, expect

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
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

FIXTURES = Path(__file__).parent / "fixtures"
TONE_MP3 = FIXTURES / "tone_30s.mp3"
BEEP_MP3 = FIXTURES / "beep.mp3"

FIRST_CLIP = "Dialogue one"
SECOND_CLIP = "Dialogue two"
THIRD_CLIP = "Dialogue three"
TRANSCRIPT = "Anna: Good morning. Ben: Good morning, how are you?"


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


def _clip_course(user: User, third_clip_duration: float | None = None) -> Course:
    """A free course whose one topic holds three clips and one speak button.

    The third clip's stored duration is ``third_clip_duration``, null by default.
    """
    course: Course = CourseFactory(
        title="Clip Course",
        slug="clip-course",
        file_path="courses/clip/course.md",
        access_config={"access_type": "free"},
    )
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    _audio_file("one", TONE_MP3, 30.0)
    _audio_file("two", TONE_MP3, 30.0)
    _audio_file("three", TONE_MP3, third_clip_duration)
    _audio_file("beep", BEEP_MP3, None)
    content = (
        f'<c-audio-clip src="audio/one.mp3" title="{FIRST_CLIP}">\n\n{TRANSCRIPT}\n\n'
        "</c-audio-clip>\n\n"
        f'<c-audio-clip src="audio/two.mp3" title="{SECOND_CLIP}"></c-audio-clip>\n\n'
        f'<c-audio-clip src="audio/three.mp3" title="{THIRD_CLIP}"></c-audio-clip>\n\n'
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


def _seek_bar(page: Page, title: str = FIRST_CLIP) -> Locator:
    return page.get_by_role("slider", name=f"Seek {title}")


def _elapsed(page: Page, title: str = FIRST_CLIP) -> Locator:
    return page.get_by_role("group", name=title).locator("[x-text='elapsedText']")


def _serve_with_ranges(route: Route) -> None:
    """Answer a media request the way a real media server does, honouring Range.

    The live server's static handler ignores Range, so a seek past the buffered
    part of the file cannot be satisfied without this. The route sits on the
    audio endpoint and answers with the file itself: a browser does not route
    the redirect's target.
    """
    body = TONE_MP3.read_bytes()
    requested = route.request.headers.get("range")
    headers = {"Content-Type": "audio/mpeg", "Accept-Ranges": "bytes"}
    if requested is None:
        route.fulfill(status=200, headers=headers, body=body)
        return
    start_text, _, end_text = requested.removeprefix("bytes=").partition("-")
    start = int(start_text)
    end = int(end_text) if end_text else len(body) - 1
    headers["Content-Range"] = f"bytes {start}-{end}/{len(body)}"
    route.fulfill(status=206, headers=headers, body=body[start : end + 1])


def _open_clips(live_server, page: Page, user: User) -> None:
    course = _clip_course(user)
    page.route("**/content/audio/**", _serve_with_ranges)
    page.goto(form_item_url(live_server, course, "view_course_item"))


def test_learner_seeks_a_clip_by_keyboard_and_mouse(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    seek = _seek_bar(page)
    elapsed = _elapsed(page)
    play = page.get_by_role("button", name=f"Play {FIRST_CLIP}")

    # A seek before the first Play is kept and applied once the audio loads.
    seek.fill("10")
    expect(elapsed).to_have_text("0:10")
    play.click()
    expect(play).to_have_attribute("aria-pressed", "true")
    expect(elapsed).not_to_have_text("0:00")
    expect(elapsed).not_to_have_text(re.compile(r"0:0\d"))
    play.click()
    expect(play).to_have_attribute("aria-pressed", "false")

    # Seeking while paused stays paused, and the slider speaks the time.
    seek.focus()
    seek.press("Home")
    expect(elapsed).to_have_text("0:00")
    seek.press("ArrowRight")
    expect(elapsed).to_have_text("0:05")
    seek.press("ArrowRight")
    expect(elapsed).to_have_text("0:10")
    seek.press("ArrowLeft")
    expect(elapsed).to_have_text("0:05")
    expect(seek).to_have_attribute("aria-valuetext", "5 seconds of 30 seconds")
    seek.press("End")
    expect(elapsed).to_have_text("0:30")
    expect(play).to_have_attribute("aria-pressed", "false")

    # A click at the right edge reaches the end of the bar.
    seek.press("Home")
    box = seek.bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] - 2, box["y"] + box["height"] / 2)
    expect(elapsed).to_have_text(re.compile(r"0:(29|30)"))
    expect(play).to_have_attribute("aria-pressed", "false")


def test_clip_seeked_near_the_end_returns_to_the_start(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    play = page.get_by_role("button", name=f"Play {FIRST_CLIP}")

    _seek_bar(page).fill("28")
    play.click()

    expect(play).to_have_attribute("aria-pressed", "false", timeout=10_000)
    expect(_elapsed(page)).to_have_text("0:00")
    expect(play.locator("[data-icon='media_play']")).to_be_visible()

    play.click()
    expect(play).to_have_attribute("aria-pressed", "true")


def test_clip_seeked_while_playing_from_a_host_without_range_still_ends(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """A seek the host can never serve must not freeze the bar while sound plays."""
    page = logged_in_page
    course = _clip_course(logged_in_user)
    page.route("**/content/audio/**", _serve_without_ranges)
    page.goto(form_item_url(live_server, course, "view_course_item"))
    play = page.get_by_role("button", name=f"Play {FIRST_CLIP}")

    play.click()
    expect(play).to_have_attribute("aria-pressed", "true", timeout=10_000)
    page.wait_for_timeout(1500)
    _seek_bar(page).fill("28")

    # Either the seek lands and the clip ends, or the bar goes back to following the audio.
    expect(_elapsed(page)).not_to_have_text("0:28", timeout=5_000)


def test_clip_without_a_stored_duration_enables_its_seek_bar_after_play(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    seek = _seek_bar(page, THIRD_CLIP)
    group = page.get_by_role("group", name=THIRD_CLIP)

    expect(seek).to_be_disabled()
    expect(group).to_contain_text("--:--")

    page.get_by_role("button", name=f"Play {THIRD_CLIP}").click()

    expect(seek).to_be_enabled()
    expect(group).to_contain_text("0:30")


@pytest.mark.browser_context_args(has_touch=True)
def test_learner_seeks_a_clip_by_touch(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    seek = _seek_bar(page)

    box = seek.bounding_box()
    assert box is not None
    page.touchscreen.tap(box["x"] + box["width"] - 2, box["y"] + box["height"] / 2)

    expect(_elapsed(page)).to_have_text(re.compile(r"0:(29|30)"))


def _to_seconds(clock: str) -> int:
    minutes, seconds = clock.split(":")
    return int(minutes) * 60 + int(seconds)


def test_only_one_clip_or_speak_button_plays_at_a_time(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    play_a = page.get_by_role("button", name=f"Play {FIRST_CLIP}")
    play_b = page.get_by_role("button", name=f"Play {SECOND_CLIP}")
    speak = page.get_by_role("button", name="Beep")

    play_a.click()
    expect(play_a).to_have_attribute("aria-pressed", "true")
    expect(_elapsed(page)).not_to_have_text("0:00")
    play_a.click()
    expect(play_a).to_have_attribute("aria-pressed", "false")
    paused_at = _elapsed(page).inner_text()

    # Starting clip B leaves the paused clip A where it was.
    play_b.click()
    expect(play_b).to_have_attribute("aria-pressed", "true")
    expect(play_a).to_have_attribute("aria-pressed", "false")
    expect(_elapsed(page)).to_have_text(paused_at)

    # The speak button pauses clip B, which keeps its time.
    expect(_elapsed(page, SECOND_CLIP)).not_to_have_text("0:00")
    speak.click()
    expect(speak).to_have_attribute("aria-pressed", "true")
    expect(play_b).to_have_attribute("aria-pressed", "false")
    held = _elapsed(page, SECOND_CLIP).inner_text()
    assert held != "0:00"
    page.wait_for_timeout(500)
    expect(_elapsed(page, SECOND_CLIP)).to_have_text(held)

    # Clip A resumes from where it paused, never from the start.
    play_a.click()
    expect(play_a).to_have_attribute("aria-pressed", "true")
    expect(speak).to_have_attribute("aria-pressed", "false")
    expect(_elapsed(page)).not_to_have_text("0:00")
    expect(_elapsed(page)).not_to_have_text(re.compile(r"^0:00$"))
    resumed = _elapsed(page).inner_text()
    assert _to_seconds(resumed) >= _to_seconds(paused_at)


def test_pressing_the_speak_button_stops_a_playing_clip_and_back(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    play_a = page.get_by_role("button", name=f"Play {FIRST_CLIP}")
    speak = page.get_by_role("button", name="Beep")

    play_a.click()
    expect(play_a).to_have_attribute("aria-pressed", "true")
    speak.click()
    expect(play_a).to_have_attribute("aria-pressed", "false")
    expect(play_a.locator("[data-icon='media_play']")).to_be_visible()
    expect(speak).to_have_attribute("aria-pressed", "true")

    play_a.click()
    expect(play_a).to_have_attribute("aria-pressed", "true")
    expect(speak).to_have_attribute("aria-pressed", "false")
    expect(speak.locator("[data-icon='audio_play']")).to_be_visible()


def _transcript_toggle(page: Page, title: str = FIRST_CLIP) -> Locator:
    return page.get_by_role("group", name=title).get_by_role(
        "button", name=re.compile("transcript$")
    )


def test_learner_opens_and_closes_a_transcript(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    toggle = _transcript_toggle(page)
    text = page.get_by_text(TRANSCRIPT)

    expect(toggle).to_have_text("Show transcript")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(text).to_be_hidden()
    expect(_transcript_toggle(page, SECOND_CLIP)).to_have_count(0)

    toggle.click()
    expect(toggle).to_have_text("Hide transcript")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(text).to_be_visible()

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(text).to_be_hidden()


def test_transcript_toggle_controls_the_transcript_panel(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """The toggle's aria-controls used to name an id no element had.

    The wrapper's x-id did not list the transcript id, so the toggle and the
    panel each minted a different one.
    """
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    toggle = _transcript_toggle(page)

    controlled = toggle.get_attribute("aria-controls")

    assert controlled
    panel = page.locator(f"[id='{controlled}']")
    expect(panel).to_have_count(1)
    expect(panel).to_contain_text(TRANSCRIPT)


def test_transcript_opens_at_once_with_reduced_motion(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    page.emulate_media(reduced_motion="reduce")
    _open_clips(live_server, page, logged_in_user)

    _transcript_toggle(page).click()

    # No auto-waiting: the panel must be fully open straight after the click.
    panel = page.get_by_text(TRANSCRIPT)
    assert panel.is_visible()
    height = panel.evaluate("el => el.parentElement.getBoundingClientRect().height")
    assert height >= panel.evaluate("el => el.parentElement.scrollHeight")


def test_clip_fits_every_viewport(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    _open_clips(live_server, page, logged_in_user)
    _transcript_toggle(page).click()
    expect(page.get_by_text(TRANSCRIPT)).to_be_visible()

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        expect(_seek_bar(page)).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_failed_clip_shows_an_error_and_retries_from_its_position(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _clip_course(logged_in_user)
    page.route("**/content/audio/**", lambda route: route.abort())
    page.goto(form_item_url(live_server, course, "view_course_item"))
    group = page.get_by_role("group", name=FIRST_CLIP)
    play = page.get_by_role("button", name=f"Play {FIRST_CLIP}")
    try_again = page.get_by_role("button", name=f"Try again: {FIRST_CLIP}")
    status = group.get_by_role("status")

    _seek_bar(page).fill("10")
    play.click()

    expect(status).to_have_text("This audio couldn't load.")
    expect(_seek_bar(page)).to_be_hidden()
    expect(try_again).to_be_enabled()
    expect(try_again.locator("[data-icon='retry']")).to_be_visible()
    expect(page.get_by_role("button", name="Try again", exact=True)).to_have_count(0)

    page.unroute("**/content/audio/**")
    page.route("**/content/audio/**", _serve_with_ranges)
    try_again.click()

    expect(play).to_have_attribute("aria-pressed", "true")
    expect(status).to_have_text("")
    expect(_elapsed(page)).not_to_have_text(re.compile(r"0:0\d"))
    expect(_elapsed(page)).not_to_have_text("0:00")
    assert _to_seconds(_elapsed(page).inner_text()) >= 10


def test_transcript_opens_in_the_error_state(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _clip_course(logged_in_user)
    page.route("**/content/audio/**", lambda route: route.abort())
    page.goto(form_item_url(live_server, course, "view_course_item"))

    page.get_by_role("button", name=f"Play {FIRST_CLIP}").click()
    expect(
        page.get_by_role("group", name=FIRST_CLIP).get_by_role("status")
    ).to_have_text("This audio couldn't load.")
    _transcript_toggle(page).click()

    expect(page.get_by_text(TRANSCRIPT)).to_be_visible()


def test_retry_that_fails_again_announces_the_error_again(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _clip_course(logged_in_user)
    page.route("**/content/audio/**", lambda route: route.abort())
    page.goto(form_item_url(live_server, course, "view_course_item"))
    status = page.get_by_role("group", name=FIRST_CLIP).get_by_role("status")
    try_again = page.get_by_role("button", name=f"Try again: {FIRST_CLIP}")

    page.get_by_role("button", name=f"Play {FIRST_CLIP}").click()
    expect(status).to_have_text("This audio couldn't load.")
    try_again.click()

    expect(status).to_have_text("This audio couldn't load.")
    expect(try_again).to_be_visible()


def _serve_without_ranges(route: Route) -> None:
    """Answer every media request with the whole file as a plain 200, ignoring Range."""
    route.fulfill(
        status=200,
        headers={"Content-Type": "audio/mpeg"},
        body=TONE_MP3.read_bytes(),
    )


def test_seek_before_play_gives_way_when_the_host_ignores_range(
    live_server,
    live_server_site,
    mock_site_context,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """A host that ignores Range leaves the file unseekable, so the sound starts at 0:00.

    Once the whole file has loaded the seek can never land, and the bar shows
    where the sound really is rather than staying at the chosen point.
    """
    page = logged_in_page
    course = _clip_course(logged_in_user)
    page.route("**/content/audio/**", _serve_without_ranges)
    page.goto(form_item_url(live_server, course, "view_course_item"))
    play = page.get_by_role("button", name=f"Play {FIRST_CLIP}")

    _seek_bar(page).fill("20")
    play.click()

    expect(play).to_have_attribute("aria-pressed", "true", timeout=10_000)
    expect(_elapsed(page)).to_have_text(re.compile(r"0:0\d"), timeout=5_000)
