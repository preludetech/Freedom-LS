"""Unit tests for content_save's author-facing image formatting helpers.

No database: both helpers take plain values, and the decisions here are
constructed by hand rather than run through `optimise_image`.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.images import ImageEncodeDecision, ImageEncodeStatus
from freedom_ls.content_engine.management.commands.content_save import (
    _format_bytes,
    _format_image_decision_line,
)


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1024, "1.0 KB"),
        (10240, "10 KB"),
        (120832, "118 KB"),
        (421888, "412 KB"),
        (5348147, "5.1 MB"),
        (2147483648, "2.0 GB"),
    ],
    ids=[
        "zero_bytes",
        "just_under_a_kb",
        "exactly_one_kb",
        "ten_kb_no_decimal",
        "118_kb",
        "412_kb",
        "5_point_1_mb",
        "two_gb",
    ],
)
def test_format_bytes_renders_human_readable_size(num_bytes, expected):
    assert _format_bytes(num_bytes) == expected


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.OPTIMISED,
                source_format="JPEG",
                source_size=(4032, 3024),
                data=b"x",
                suffix=".webp",
                mime_type="image/webp",
                lossless=False,
                stored_size=(1600, 1200),
                error=None,
            ),
            "JPEG 4032x3024 -> WebP lossy 1600x1200",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.OPTIMISED,
                source_format="PNG",
                source_size=(1840, 1120),
                data=b"x",
                suffix=".webp",
                mime_type="image/webp",
                lossless=True,
                stored_size=(1600, 974),
                error=None,
            ),
            "PNG 1840x1120 -> WebP lossless 1600x974",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.PASSTHROUGH,
                source_format="SVG",
                source_size=None,
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error=None,
            ),
            "SVG, passthrough.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.PASSTHROUGH,
                source_format="GIF",
                source_size=(800, 600),
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error=None,
            ),
            "GIF 800x600, passthrough.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.KEPT_SOURCE,
                source_format="PNG",
                source_size=(200, 120),
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error=None,
            ),
            "PNG 200x120, re-encode not smaller, kept source.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.UNDECODABLE,
                source_format=None,
                source_size=None,
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error="ValueError: not enough image data",
            ),
            "could not decode.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.UNDECODABLE,
                source_format="PNG",
                source_size=(100, 100),
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error="SyntaxError: broken PNG file",
            ),
            "PNG 100x100, could not decode.",
        ),
    ],
    ids=[
        "optimised_lossy_jpeg",
        "optimised_lossless_png",
        "passthrough_svg_no_dimensions",
        "passthrough_animated_gif_with_dimensions",
        "kept_source_names_the_reason",
        "undecodable_before_format_known",
        "undecodable_after_format_known",
    ],
)
def test_format_image_decision_line_from_decision_alone(decision, expected):
    assert _format_image_decision_line(decision) == expected
