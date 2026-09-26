"""Tests for the meta_pixel app's declared settings and their defaults."""

from __future__ import annotations

from freedom_ls.meta_pixel.config import config


class TestMetaPixelDefaults:
    def test_pixel_id_defaults_to_none(self) -> None:
        assert config.META_PIXEL_ID is None
