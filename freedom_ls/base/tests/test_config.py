"""Tests for the base app's declared settings and their defaults."""

from __future__ import annotations

from freedom_ls.base.config import config


class TestVisitorCountryHeaderDefault:
    def test_defaults_to_none(self) -> None:
        assert config.VISITOR_COUNTRY_HEADER is None
