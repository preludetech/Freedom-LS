from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from django.test import RequestFactory

from freedom_ls.base.context_processors import (
    branch_name_to_color,
    debug_branch_info,
    get_text_color,
)
from freedom_ls.base.git_utils import _clear_branch_cache


@pytest.fixture(autouse=True)
def _reset_branch_cache() -> Iterator[None]:
    _clear_branch_cache()
    yield
    _clear_branch_cache()


# --- Task 2: Color generation ---


class TestBranchNameToColor:
    def test_same_name_produces_same_color(self) -> None:
        assert branch_name_to_color("main") == branch_name_to_color("main")

    def test_different_names_produce_different_colors(self) -> None:
        assert branch_name_to_color("main") != branch_name_to_color("develop")

    def test_returns_valid_hex_color(self) -> None:
        color = branch_name_to_color("feature-x")
        assert color.startswith("#")
        assert len(color) == 7
        int(color[1:], 16)  # should not raise


class TestGetTextColor:
    @pytest.mark.parametrize(
        ("background", "expected_text"),
        [
            ("#ffffff", "#000000"),
            ("#000000", "#ffffff"),
            ("#aabbcc", "#000000"),
            ("#001144", "#ffffff"),
        ],
        ids=[
            "white_background_uses_black_text",
            "black_background_uses_white_text",
            "medium_light_background_uses_black_text",
            "dark_blue_background_uses_white_text",
        ],
    )
    def test_text_color_for_background(
        self, background: str, expected_text: str
    ) -> None:
        assert get_text_color(background) == expected_text


# --- Task 4: Settings isolation ---


class TestDebugBranchNotInProdSettings:
    def test_not_in_base_settings_source(self) -> None:
        from django.conf import settings

        base_settings_path = Path(settings.BASE_DIR) / "config" / "settings_base.py"
        content = base_settings_path.read_text()
        assert "debug_branch_info" not in content

    def test_not_in_prod_settings_source(self) -> None:
        from django.conf import settings

        prod_settings_path = Path(settings.BASE_DIR) / "config" / "settings_prod.py"
        content = prod_settings_path.read_text()
        assert "debug_branch_info" not in content


# --- Task 3: Context processor ---


class TestDebugBranchInfo:
    def test_returns_all_keys_when_branch_detected(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        with (
            patch("freedom_ls.base.context_processors.settings") as mock_settings,
            patch(
                "freedom_ls.base.context_processors.get_current_branch",
                return_value="my-feature",
            ),
        ):
            mock_settings.DEBUG = True
            result = debug_branch_info(request)

        assert result["debug_branch_name"] == "my-feature"
        assert result["debug_branch_color"].startswith("#")
        assert result["debug_branch_text_color"] in ("#000000", "#ffffff")

    def test_returns_empty_dict_when_no_branch(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        with (
            patch("freedom_ls.base.context_processors.settings") as mock_settings,
            patch(
                "freedom_ls.base.context_processors.get_current_branch",
                return_value=None,
            ),
        ):
            mock_settings.DEBUG = True
            result = debug_branch_info(request)

        assert result == {}

    def test_returns_empty_dict_when_debug_false(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.DEBUG = False
            result = debug_branch_info(request)

        assert result == {}
