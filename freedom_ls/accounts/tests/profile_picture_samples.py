"""Builders for profile-picture test inputs.

Every sample is made with Pillow when the test runs, so no binary file is
committed. Large samples are flat colour, which compresses to a few kilobytes
and keeps the tests fast.
"""

import io

from PIL import Image

RED = (255, 0, 0)
BLUE = (0, 0, 255)

GPS_IFD_POINTER = 0x8825
ORIENTATION_TAG = 0x0112


def _save(img: Image.Image, fmt: str, **options: object) -> bytes:
    out = io.BytesIO()
    img.save(out, fmt, **options)
    return out.getvalue()


def jpeg_bytes(width: int = 600, height: int = 400) -> bytes:
    return _save(Image.new("RGB", (width, height), BLUE), "JPEG")


def png_bytes(width: int = 600, height: int = 400) -> bytes:
    return _save(Image.new("RGB", (width, height), BLUE), "PNG")


def webp_bytes(width: int = 600, height: int = 400) -> bytes:
    return _save(Image.new("RGB", (width, height), BLUE), "WEBP")


def gif_bytes(width: int = 600, height: int = 400) -> bytes:
    return _save(Image.new("P", (width, height)), "GIF")


def transparent_png_bytes(width: int = 600, height: int = 400) -> bytes:
    return _save(Image.new("RGBA", (width, height), (0, 255, 0, 0)), "PNG")


def jpeg_with_gps_exif_bytes() -> bytes:
    exif = Image.Exif()
    exif.get_ifd(GPS_IFD_POINTER).update(
        {1: "S", 2: (33.0, 55.0, 0.0), 3: "E", 4: (18.0, 25.0, 0.0)}
    )
    return _save(Image.new("RGB", (600, 400), BLUE), "JPEG", exif=exif)


def jpeg_with_orientation_bytes() -> bytes:
    """A 300x200 JPEG with a red top-left block and EXIF orientation 6.

    Orientation 6 means the stored pixels are displayed rotated 90 degrees
    clockwise, so the red block shows at the top-right of a 200x300 image.
    """
    img = Image.new("RGB", (300, 200), BLUE)
    img.paste(Image.new("RGB", (100, 100), RED), (0, 0))
    exif = Image.Exif()
    exif[ORIENTATION_TAG] = 6
    return _save(img, "JPEG", exif=exif, quality=95)


def mpo_bytes(width: int = 600, height: int = 400) -> bytes:
    first = Image.new("RGB", (width, height), BLUE)
    second = Image.new("RGB", (width, height), RED)
    return _save(first, "MPO", save_all=True, append_images=[second])


def truncated(data: bytes, keep: float = 0.5) -> bytes:
    return data[: int(len(data) * keep)]


def truncated_jpeg_bytes() -> bytes:
    noisy = Image.effect_noise((600, 400), 80).convert("RGB")
    return truncated(_save(noisy, "JPEG"))


def truncated_png_bytes() -> bytes:
    noisy = Image.effect_noise((600, 400), 80).convert("RGB")
    return truncated(_save(noisy, "PNG"))


def with_trailing_bytes(data: bytes, payload: bytes = b"SECRET-PAYLOAD") -> bytes:
    return data + payload


def animated_webp_bytes() -> bytes:
    frames = [Image.new("RGB", (600, 400), colour) for colour in (RED, BLUE)]
    return _save(
        frames[0], "WEBP", save_all=True, append_images=frames[1:], duration=100
    )
