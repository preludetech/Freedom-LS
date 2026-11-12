import io

import pytest
from PIL import Image

from freedom_ls.accounts.images import PROFILE_PICTURE_SIDE, encode_profile_picture
from freedom_ls.accounts.tests import profile_picture_samples as samples


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def _rgb_at(img: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    red, green, blue = img.convert("RGB").crop((x, y, x + 1, y + 1)).tobytes()
    return red, green, blue


@pytest.mark.parametrize(
    "raw",
    [
        samples.jpeg_bytes(800, 400),
        samples.jpeg_bytes(400, 800),
        samples.jpeg_bytes(128, 128),
        samples.png_bytes(),
    ],
    ids=["landscape", "portrait", "minimum", "png"],
)
def test_output_is_a_square_webp(raw: bytes) -> None:
    img = _open(encode_profile_picture(raw))

    assert img.format == "WEBP"
    assert img.size == (PROFILE_PICTURE_SIDE, PROFILE_PICTURE_SIDE)


def test_gps_exif_is_not_carried_over() -> None:
    img = _open(encode_profile_picture(samples.jpeg_with_gps_exif_bytes()))

    assert not img.info.get("exif")


def test_orientation_tag_is_applied_to_the_pixels() -> None:
    img = _open(encode_profile_picture(samples.jpeg_with_orientation_bytes()))

    top_right = _rgb_at(img, PROFILE_PICTURE_SIDE - 5, 5)
    bottom_left = _rgb_at(img, 5, PROFILE_PICTURE_SIDE - 5)
    assert top_right[0] > 200
    assert top_right[2] < 60
    assert bottom_left[2] > 200
    assert bottom_left[0] < 60


def test_trailing_bytes_are_dropped() -> None:
    raw = samples.with_trailing_bytes(samples.jpeg_bytes())

    assert b"SECRET-PAYLOAD" not in encode_profile_picture(raw)


def test_animated_webp_gives_one_frame() -> None:
    img = _open(encode_profile_picture(samples.animated_webp_bytes()))

    assert getattr(img, "n_frames", 1) == 1


def test_mpo_gives_its_first_frame() -> None:
    img = _open(encode_profile_picture(samples.mpo_bytes()))

    pixel = _rgb_at(img, 200, 200)
    assert pixel[2] > 200
    assert pixel[0] < 60


def test_transparent_png_keeps_an_alpha_channel() -> None:
    img = _open(encode_profile_picture(samples.transparent_png_bytes()))

    assert "A" in img.getbands()
