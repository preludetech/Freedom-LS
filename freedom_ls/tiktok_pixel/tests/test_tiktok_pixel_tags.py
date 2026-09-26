from __future__ import annotations

from freedom_ls.base.analytics_events import AnalyticsEventPayload, PixelCall
from freedom_ls.tiktok_pixel.templatetags.tiktok_pixel_tags import tiktok_pixel_call


class TestTikTokPixelCall:
    def test_a_mapped_event_gives_the_mappings_row(self) -> None:
        event: AnalyticsEventPayload = {
            "name": "sign_up",
            "params": {"method": "email"},
        }

        assert tiktok_pixel_call(event) == PixelCall("track", "SignUp")

    def test_an_unmapped_event_gives_none(self) -> None:
        event: AnalyticsEventPayload = {"name": "course_started", "params": {}}

        assert tiktok_pixel_call(event) is None
