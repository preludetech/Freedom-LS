"""Tests for the shared Pillow decode guards."""

from __future__ import annotations

import pytest
from PIL import ImageFile

from freedom_ls.base.images import truncated_images_rejected


class TestTruncatedImagesRejected:
    def test_the_flag_is_false_inside_the_block(self, monkeypatch) -> None:
        """WeasyPrint leaves it true for the rest of the process once the report
        renderer imports it, which is the state a decode has to survive."""
        monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)

        with truncated_images_rejected():
            assert ImageFile.LOAD_TRUNCATED_IMAGES is False

    def test_the_previous_value_is_put_back(self, monkeypatch) -> None:
        """WeasyPrint sets the flag deliberately, so the guard borrows it for
        the length of a decode rather than clamping it off for good."""
        monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)

        with truncated_images_rejected():
            pass

        assert ImageFile.LOAD_TRUNCATED_IMAGES is True

    def test_the_previous_value_is_put_back_after_a_failed_decode(
        self, monkeypatch
    ) -> None:
        """A malformed file is the case the guard exists for, so it is also the
        case where leaking the clamped value would be easiest to miss."""
        monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)

        with (
            pytest.raises(ValueError, match="decode failed"),
            truncated_images_rejected(),
        ):
            raise ValueError("decode failed")

        assert ImageFile.LOAD_TRUNCATED_IMAGES is True
