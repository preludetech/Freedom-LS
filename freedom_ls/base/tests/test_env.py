from __future__ import annotations

import pytest

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.base.env import env_bool, env_float, env_int, env_str, first_set_name


class TestEnvBool:
    @pytest.mark.parametrize("raw", ["true", "TRUE", " True ", "1", "yes", "on"])
    def test_truthy_values(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("FLS_TEST_BOOL", raw)

        assert env_bool("FLS_TEST_BOOL", False) is True

    @pytest.mark.parametrize("raw", ["false", "FALSE", " False ", "0", "no", "off"])
    def test_falsy_values(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("FLS_TEST_BOOL", raw)

        assert env_bool("FLS_TEST_BOOL", True) is False

    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLS_TEST_BOOL", raising=False)

        assert env_bool("FLS_TEST_BOOL", True) is True

    def test_default_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_BOOL", "   ")

        assert env_bool("FLS_TEST_BOOL", True) is True

    def test_invalid_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_BOOL", "maybe")

        with pytest.raises(ImproperlyConfigured):
            env_bool("FLS_TEST_BOOL", False)


class TestEnvInt:
    def test_valid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_INT", "7200")

        assert env_int("FLS_TEST_INT", 3600) == 7200

    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLS_TEST_INT", raising=False)

        assert env_int("FLS_TEST_INT", 3600) == 3600

    def test_default_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_INT", "")

        assert env_int("FLS_TEST_INT", 3600) == 3600

    def test_invalid_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_INT", "notanumber")

        with pytest.raises(ImproperlyConfigured):
            env_int("FLS_TEST_INT", 3600)


class TestEnvFloat:
    def test_valid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_FLOAT", "0.25")

        assert env_float("FLS_TEST_FLOAT", None) == 0.25

    def test_zero_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_FLOAT", "0")

        assert env_float("FLS_TEST_FLOAT", 0.1) == 0.0

    def test_default_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLS_TEST_FLOAT", raising=False)

        assert env_float("FLS_TEST_FLOAT", None) is None

    def test_invalid_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_FLOAT", "notanumber")

        with pytest.raises(ImproperlyConfigured):
            env_float("FLS_TEST_FLOAT", None)


class TestEnvStr:
    def test_stripped_value_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_STR", "  hello  ")

        assert env_str("FLS_TEST_STR") == "hello"

    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLS_TEST_STR", raising=False)

        assert env_str("FLS_TEST_STR", "fallback") == "fallback"

    def test_default_when_whitespace_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FLS_TEST_STR", "   ")

        assert env_str("FLS_TEST_STR", "fallback") == "fallback"


class TestFirstSetName:
    def test_returns_first_set_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLS_TEST_FIRST", "value")
        monkeypatch.setenv("FLS_TEST_SECOND", "value")

        assert first_set_name("FLS_TEST_FIRST", "FLS_TEST_SECOND") == "FLS_TEST_FIRST"

    def test_skips_blank_name_and_picks_next(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FLS_TEST_FIRST", "   ")
        monkeypatch.setenv("FLS_TEST_SECOND", "value")

        assert first_set_name("FLS_TEST_FIRST", "FLS_TEST_SECOND") == "FLS_TEST_SECOND"

    def test_none_when_no_name_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLS_TEST_FIRST", raising=False)
        monkeypatch.delenv("FLS_TEST_SECOND", raising=False)

        assert first_set_name("FLS_TEST_FIRST", "FLS_TEST_SECOND") is None
