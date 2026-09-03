"""Unit tests for optimise_image: bytes in, bytes out, no database."""

from __future__ import annotations

import io
from typing import cast

import pytest
from PIL import Image

from freedom_ls.content_engine import images
from freedom_ls.content_engine.images import (
    MAX_DIMENSION_PX,
    ImageEncodeStatus,
    optimise_image,
)
from freedom_ls.tests.images import (
    already_minimal_png_bytes,
    animated_gif_bytes,
    break_png_chunk_crc,
    camera_exif_png_bytes,
    cmyk_jpeg_bytes,
    exif_orientation_jpeg_bytes,
    gps_exif_jpeg_bytes,
    icc_rgb_png_bytes,
    jpeg_bytes,
    mpo_bytes,
    palette_gif_bytes,
    palette_trns_png_bytes,
    photographic_jpeg_bytes,
    photographic_png_bytes,
    png_bytes,
    rgba_png_bytes,
    screenshot_png_bytes,
    shorten_png_ihdr,
)


def _rgb_channel_bounds(img: Image.Image) -> tuple[tuple[int, int], ...]:
    """The (min, max) pixel value of each RGB channel actually present in ``img``."""
    counted = img.convert("RGB").getcolors(maxcolors=2_000_000)
    if counted is None:
        msg = "image has more distinct colours than a test fixture should"
        raise ValueError(msg)
    colours = [
        colour for _, colour in cast("list[tuple[int, tuple[int, int, int]]]", counted)
    ]
    return tuple(
        (
            min(colour[channel] for colour in colours),
            max(colour[channel] for colour in colours),
        )
        for channel in range(3)
    )


def _within_tolerance(
    inner: tuple[tuple[int, int], ...],
    outer: tuple[tuple[int, int], ...],
    *,
    tolerance: int,
) -> bool:
    """Whether every channel of ``inner`` falls within ``outer``, widened by ``tolerance``.

    A LANCZOS resize legitimately overshoots a flat colour boundary by a few
    units (ringing), so an exact-bounds check would fail on correct output.
    A genuinely invented colour, from resampling raw palette indices instead
    of RGB values, overshoots by far more than that.
    """
    return all(
        outer_min - tolerance <= inner_min and inner_max <= outer_max + tolerance
        for (inner_min, inner_max), (outer_min, outer_max) in zip(
            inner, outer, strict=True
        )
    )


def test_large_jpeg_becomes_smaller_webp_within_the_dimension_cap():
    raw = photographic_jpeg_bytes(2000, 1500)

    decision = optimise_image(raw, ".jpg")

    assert decision.status is ImageEncodeStatus.OPTIMISED
    assert decision.mime_type == "image/webp"
    assert max(decision.stored_size) <= MAX_DIMENSION_PX
    assert len(decision.data) < len(raw)


def test_source_smaller_than_cap_keeps_its_exact_dimensions():
    raw = jpeg_bytes(900, 600)

    decision = optimise_image(raw, ".jpg")

    assert decision.stored_size == (900, 600)


def test_jpeg_source_takes_the_single_lossy_path():
    decision = optimise_image(photographic_jpeg_bytes(), ".jpg")

    assert decision.lossless is False


def test_small_screenshot_png_comes_back_lossless():
    decision = optimise_image(screenshot_png_bytes(), ".png")

    assert decision.lossless is True


@pytest.mark.parametrize(
    ("builder", "expected_lossless"),
    [
        (photographic_png_bytes, False),
        (camera_exif_png_bytes, True),
    ],
)
def test_comparison_winner_on_each_side_of_the_lossy_wins_divisor(
    builder, expected_lossless
):
    decision = optimise_image(builder(), ".png")

    assert decision.lossless is expected_lossless


def test_exif_orientation_is_applied_to_both_reported_dimensions():
    raw = exif_orientation_jpeg_bytes(width=30, height=20)

    decision = optimise_image(raw, ".jpg")

    # Orientation 6 is a 90-degree rotation: a viewer swaps the axes the
    # raw buffer stored. Both halves of the pair the author is shown are in
    # that display orientation, so the line cannot read as a ratio change.
    assert decision.stored_size == (20, 30)
    assert decision.source_size == (20, 30)


def test_icc_profile_survives_from_an_rgb_source():
    decision = optimise_image(icc_rgb_png_bytes(400, 400), ".png")

    stored = Image.open(io.BytesIO(decision.data))

    assert "icc_profile" in stored.info


def test_icc_profile_is_dropped_from_a_cmyk_source():
    decision = optimise_image(cmyk_jpeg_bytes(), ".jpg")

    stored = Image.open(io.BytesIO(decision.data))

    assert "icc_profile" not in stored.info


def test_exif_is_stripped_from_the_output():
    decision = optimise_image(photographic_jpeg_bytes(), ".jpg")

    stored = Image.open(io.BytesIO(decision.data))

    assert len(stored.getexif()) == 0


def test_gps_exif_is_stripped_from_the_output():
    decision = optimise_image(gps_exif_jpeg_bytes(), ".jpg")

    stored = Image.open(io.BytesIO(decision.data))

    assert len(stored.getexif()) == 0


def test_palette_png_with_trns_keeps_transparency():
    decision = optimise_image(palette_trns_png_bytes(), ".png")

    stored = Image.open(io.BytesIO(decision.data))

    assert stored.has_transparency_data


def test_rgba_png_keeps_transparency():
    decision = optimise_image(rgba_png_bytes(), ".png")

    stored = Image.open(io.BytesIO(decision.data))

    assert stored.has_transparency_data


def test_resized_palette_source_has_no_colour_bleed_beyond_source_gamut():
    raw = palette_gif_bytes()
    source_bounds = _rgb_channel_bounds(Image.open(io.BytesIO(raw)))

    decision = optimise_image(raw, ".gif")

    stored_bounds = _rgb_channel_bounds(Image.open(io.BytesIO(decision.data)))
    assert _within_tolerance(stored_bounds, source_bounds, tolerance=12)


def _small_webp_bytes(width: int = 20, height: int = 20) -> bytes:
    """A WebP already within the dimension cap, so re-encoding it buys nothing."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(10, 20, 30)).save(buf, format="WEBP")
    return buf.getvalue()


def test_svg_passes_through_by_suffix_alone():
    decision = optimise_image(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", ".svg")

    assert decision.status is ImageEncodeStatus.PASSTHROUGH
    assert decision.data is None
    assert decision.source_format == "SVG"


def test_animated_gif_passes_through_unchanged():
    decision = optimise_image(animated_gif_bytes(), ".gif")

    assert decision.status is ImageEncodeStatus.PASSTHROUGH
    assert decision.data is None


def test_already_small_webp_passes_through_unchanged():
    decision = optimise_image(_small_webp_bytes(), ".webp")

    assert decision.status is ImageEncodeStatus.PASSTHROUGH
    assert decision.data is None


def test_mpo_jpeg_is_optimised_not_mistaken_for_animation():
    decision = optimise_image(mpo_bytes(width=2000, height=1500), ".jpg")

    assert decision.status is ImageEncodeStatus.OPTIMISED


def test_png_with_short_ihdr_is_undecodable_before_any_format_is_known():
    decision = optimise_image(shorten_png_ihdr(png_bytes()), ".png")

    assert decision.status is ImageEncodeStatus.UNDECODABLE
    assert decision.data is None
    assert decision.source_format is None
    assert decision.error is not None
    assert "ValueError" in decision.error


def test_png_with_broken_chunk_crc_is_undecodable_after_the_format_is_known():
    decision = optimise_image(break_png_chunk_crc(png_bytes()), ".png")

    assert decision.status is ImageEncodeStatus.UNDECODABLE
    assert decision.data is None
    assert decision.source_format == "PNG"
    assert decision.error is not None
    assert "OSError" in decision.error


def test_no_truncation_of_an_animated_gif_escapes_as_an_exception():
    """Every prefix of a multi-frame GIF comes back as a decision.

    Counting a GIF's frames seeks through all of them, and Pillow's GIF
    plugin reports a seek that runs off the end of the buffer as whichever
    exception the read reached for: struct.error from a two-byte duration
    field, IndexError from a one-byte block label. Every cut is tried
    because which of the two a prefix hits depends on where it stops.
    """
    raw = animated_gif_bytes()

    statuses = {optimise_image(raw[:cut], ".gif").status for cut in range(1, len(raw))}

    assert statuses <= set(ImageEncodeStatus)
    assert ImageEncodeStatus.UNDECODABLE in statuses


def test_an_encode_failure_is_a_decision_rather_than_an_exception(monkeypatch):
    """A failure on the way out is caught the same way as one on the way in.

    libwebp reports a write it cannot complete as an OSError, which would
    otherwise leave the encode as the one step of the pipeline still able to
    abort a run over a whole content repository.
    """

    def fail(*args, **kwargs):
        raise OSError("encoder error")

    monkeypatch.setattr(images, "_encode", fail)

    decision = optimise_image(photographic_jpeg_bytes(), ".jpg")

    assert decision.status is ImageEncodeStatus.UNDECODABLE
    assert decision.data is None
    assert decision.source_format == "JPEG"
    assert decision.source_size == (2000, 1500)
    assert decision.error is not None
    assert "OSError" in decision.error


def test_tiny_already_minimal_png_is_kept_unchanged():
    decision = optimise_image(already_minimal_png_bytes(), ".png")

    assert decision.status is ImageEncodeStatus.KEPT_SOURCE
    assert decision.data is None


@pytest.mark.parametrize(
    ("raw", "suffix"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", ".svg"),
        (animated_gif_bytes(), ".gif"),
        (already_minimal_png_bytes(), ".png"),
        (photographic_jpeg_bytes(), ".jpg"),
    ],
)
def test_non_undecodable_decisions_carry_no_error(raw, suffix):
    decision = optimise_image(raw, suffix)

    assert decision.error is None


def test_optimise_image_is_deterministic_across_runs():
    raw = photographic_jpeg_bytes()

    assert optimise_image(raw, ".jpg").data == optimise_image(raw, ".jpg").data
