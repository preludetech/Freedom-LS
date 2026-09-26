"""Tests for the tiktok_pixel app's declared settings and their defaults."""

from __future__ import annotations

from freedom_ls.tiktok_pixel.config import config


class TestTikTokPixelDefaults:
    def test_pixel_id_defaults_to_none(self) -> None:
        assert config.TIKTOK_PIXEL_ID is None
