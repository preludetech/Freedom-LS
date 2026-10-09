from __future__ import annotations

from django.test import override_settings

from freedom_ls.google_tag.templatetags.google_tag_tags import google_ads_send_to


class TestGoogleAdsSendTo:
    @override_settings(
        GOOGLE_ADS_CONVERSION_ID="AW-TEST",
        GOOGLE_ADS_CONVERSION_LABELS={"sign_up": "QAsignup"},
    )
    def test_a_mapped_event_carries_its_send_to(self) -> None:
        assert google_ads_send_to("sign_up") == "AW-TEST/QAsignup"

    @override_settings(
        GOOGLE_ADS_CONVERSION_ID="AW-TEST",
        GOOGLE_ADS_CONVERSION_LABELS={"course_registered": "QAregistered"},
    )
    def test_an_unmapped_event_has_no_send_to(self) -> None:
        assert google_ads_send_to("sign_up") is None

    @override_settings(
        GOOGLE_ADS_CONVERSION_ID=None,
        GOOGLE_ADS_CONVERSION_LABELS={"sign_up": "QAsignup"},
    )
    def test_a_label_without_a_conversion_id_gives_no_send_to(self) -> None:
        assert google_ads_send_to("sign_up") is None
