"""Tests for organisation logo validation — one case per rejection path."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.organisations.validators import (
    validate_organisation_logo,
    validate_organisation_logo_extension,
)

FIXTURE_LOGO = Path(__file__).parent / "fixtures" / "RT-logo.webp"


def _png_upload(width: int, height: int, name: str = "logo.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (width, height)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def test_reference_logo_is_accepted():
    """The RT-logo.webp fixture used elsewhere in this suite passes validation."""
    upload = SimpleUploadedFile(
        "RT-logo.webp", FIXTURE_LOGO.read_bytes(), content_type="image/webp"
    )
    validate_organisation_logo_extension(upload)
    validate_organisation_logo(upload)


def test_disallowed_extension_is_rejected():
    """A .gif upload fails the extension allowlist."""
    upload = SimpleUploadedFile(
        "logo.gif", FIXTURE_LOGO.read_bytes(), content_type="image/gif"
    )
    with pytest.raises(ValidationError):
        validate_organisation_logo_extension(upload)


def test_svg_renamed_to_png_is_rejected():
    """An SVG's XML content fails the byte-level check even with a .png name."""
    svg_bytes = (
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    )
    upload = SimpleUploadedFile("logo.png", svg_bytes, content_type="image/png")
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)


def test_oversized_dimensions_are_rejected():
    """An image wider than 4000px on either axis is rejected."""
    upload = _png_upload(4001, 100)
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)


def test_undersized_dimensions_are_rejected():
    """An image smaller than the 64x32 minimum is rejected."""
    upload = _png_upload(10, 10)
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)


def test_oversized_file_is_rejected():
    """A file over 2MiB is rejected on size alone, before any image decoding."""
    upload = SimpleUploadedFile(
        "logo.png", b"0" * (2 * 1024 * 1024 + 1), content_type="image/png"
    )
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)


def test_corrupt_bytes_are_rejected():
    """Bytes that are not a decodable image are rejected."""
    upload = SimpleUploadedFile("logo.png", b"not an image", content_type="image/png")
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)


def test_decompression_bomb_is_rejected(monkeypatch):
    """A pixel count over Pillow's configured ceiling is rejected, not silently decoded."""
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    upload = _png_upload(
        15, 10
    )  # 150px > 100, but <= 2x100 (stays a warning, not a hard error)
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)


def test_rejected_file_leaves_handle_rewound():
    """A rejected upload's handle is left at position 0 for Django's later reads."""
    upload = _png_upload(10, 10)
    with pytest.raises(ValidationError):
        validate_organisation_logo(upload)
    assert upload.tell() == 0
