from __future__ import annotations

from freedom_ls.base.analytics_events import AnalyticsEventPayload, PixelCall
from freedom_ls.meta_pixel.templatetags.meta_pixel_tags import meta_pixel_call


class TestMetaPixelCall:
    def test_a_mapped_event_gives_the_mappings_row(self) -> None:
        event: AnalyticsEventPayload = {
            "name": "sign_up",
            "params": {"method": "email"},
        }

        assert meta_pixel_call(event) == PixelCall("trackCustom", "SignUp")

    def test_an_unmapped_event_gives_none(self) -> None:
        event: AnalyticsEventPayload = {"name": "course_started", "params": {}}

        assert meta_pixel_call(event) is None
