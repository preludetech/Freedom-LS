"""Image bytes shared across test suites: deliberately malformed fixtures and valid ones."""

from __future__ import annotations

import io
import random
import struct

from PIL import ExifTags, Image, ImageCms, ImageDraw
from PIL.TiffImagePlugin import IFDRational


def break_png_chunk_crc(png: bytes) -> bytes:
    """A PNG whose header still parses but whose IDAT chunk fails its checksum.

    The interesting corruption, because Pillow reports it as a SyntaxError
    rather than an OSError -- the case a decode-failure clause is most likely
    to miss. Plain ASCII or a truncated body both raise OSError subclasses and
    so prove nothing about that gap.
    """
    corrupt = bytearray(png)
    # Four bytes into the IDAT payload, past the chunk's own four-byte type.
    corrupt[png.index(b"IDAT") + 8] ^= 0xFF
    return bytes(corrupt)


def shorten_png_ihdr(png: bytes) -> bytes:
    """A PNG whose header chunk declares fewer bytes than a header needs.

    The other non-OSError way a malformed PNG surfaces: Pillow raises
    ValueError once IHDR promises less than the thirteen bytes it must carry.
    """
    short = bytearray(png)
    # The first chunk's length field, immediately after the 8-byte signature.
    # A PNG's first chunk is always IHDR.
    short[8:12] = struct.pack(">I", 12)
    return bytes(short)


def png_bytes(width: int = 20, height: int = 20) -> bytes:
    """A genuine, uncompressed-content PNG, so truncating it corrupts real data."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes(width: int = 20, height: int = 20) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(30, 90, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def gif_bytes(width: int = 20, height: int = 20, *, colors: int = 1) -> bytes:
    """A decodable image in a format the logo allowlist does not carry.

    ``colors`` splits the width into that many vertical stripes, each its own
    palette entry, so ``palette_gif_bytes`` below can ask for a resize with
    more than one colour to bleed between. The default of one colour keeps
    this the same plain fill the logo tests already rely on.
    """
    img = Image.new("P", (width, height), color=3)
    if colors > 1:
        img.putpalette(
            [
                channel
                for index in range(colors)
                for channel in (
                    (index * 47) % 256,
                    (index * 91) % 256,
                    (index * 149) % 256,
                )
            ]
        )
        stripe_width = max(1, width // colors)
        for stripe in range(colors):
            right = width if stripe == colors - 1 else (stripe + 1) * stripe_width
            img.paste(stripe, (stripe * stripe_width, 0, right, height))
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


def palette_gif_bytes(width: int = 2000, height: int = 1200) -> bytes:
    """A palette GIF over the resize cap, with enough palette entries to bleed.

    Resampling a P-mode image interpolates palette indices rather than
    colours, inventing colours the source never had. Catching that needs a
    size over the resize cap, to force the resize, and more than one colour
    for the interpolation to blend between.
    """
    return gif_bytes(width, height, colors=8)


def palette_trns_png_bytes(width: int = 20, height: int = 20) -> bytes:
    """A P-mode PNG carrying a tRNS chunk: one palette entry is transparent."""
    img = Image.new("P", (width, height), color=1)
    img.putpalette([0, 0, 0, 220, 40, 40, 40, 200, 60])
    buf = io.BytesIO()
    img.save(buf, format="PNG", transparency=1)
    return buf.getvalue()


def rgba_png_bytes(width: int = 20, height: int = 20) -> bytes:
    """An RGBA PNG with a genuinely translucent pixel, not just a bare alpha channel."""
    buf = io.BytesIO()
    Image.new("RGBA", (width, height), (200, 30, 90, 128)).save(buf, format="PNG")
    return buf.getvalue()


def _srgb_icc_profile() -> bytes:
    """A generated sRGB profile, so the fixtures below carry a real ICC profile without a committed binary file."""
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def cmyk_jpeg_bytes(width: int = 20, height: int = 20) -> bytes:
    """A CMYK JPEG tagged with an ICC profile describing a colour space the pixels leave once converted to RGB."""
    img = Image.new("RGB", (width, height), (10, 20, 30)).convert("CMYK")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", icc_profile=_srgb_icc_profile())
    return buf.getvalue()


def icc_rgb_png_bytes(width: int = 20, height: int = 20) -> bytes:
    """An RGB PNG tagged with an sRGB ICC profile that stays valid after the pixels are re-encoded."""
    img = Image.new("RGB", (width, height), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG", icc_profile=_srgb_icc_profile())
    return buf.getvalue()


def exif_orientation_jpeg_bytes(width: int = 30, height: int = 20) -> bytes:
    """A non-square JPEG tagged orientation 6, so the raw buffer's axes are swapped from what a viewer shows."""
    img = Image.new("RGB", (width, height), (10, 20, 30))
    exif = img.getexif()
    exif[ExifTags.Base.Orientation] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def camera_exif_png_bytes(width: int = 20, height: int = 20) -> bytes:
    """A PNG carrying camera Make/Model EXIF, the signal that routes a non-JPEG source into the ambiguous branch."""
    img = Image.new("RGB", (width, height), (10, 20, 30))
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Testcam"
    exif[ExifTags.Base.Model] = "Model X"
    buf = io.BytesIO()
    img.save(buf, format="PNG", exif=exif)
    return buf.getvalue()


def gps_exif_jpeg_bytes(width: int = 20, height: int = 20) -> bytes:
    """A JPEG carrying a GPS IFD, the location data a phone attaches to a photo and that has no business leaving the device."""
    img = Image.new("RGB", (width, height), (10, 20, 30))
    exif = img.getexif()
    exif[ExifTags.Base.GPSInfo] = {
        ExifTags.GPS.GPSLatitudeRef: "N",
        ExifTags.GPS.GPSLatitude: (
            IFDRational(51, 1),
            IFDRational(30, 1),
            IFDRational(0, 1),
        ),
    }
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def animated_gif_bytes(width: int = 10, height: int = 10, *, frames: int = 3) -> bytes:
    """A multi-frame GIF, so a caller can prove animation is passed through rather than flattened to one frame."""
    colours = [(220, 30, 30), (30, 220, 30), (30, 30, 220)]
    images = [
        Image.new("RGB", (width, height), colours[index % len(colours)]).convert("P")
        for index in range(frames)
    ]
    buf = io.BytesIO()
    images[0].save(
        buf, format="GIF", save_all=True, append_images=images[1:], disposal=2
    )
    return buf.getvalue()


def mpo_bytes(width: int = 10, height: int = 10) -> bytes:
    """A two-frame MPO, the multi-picture JPEG container phone cameras save stereo and burst shots in.

    Real phone photos open as MPO with ``n_frames == 2``, which is why an
    animation guard keyed on frame count alone would mistake one for an
    animated image.
    """
    first = Image.new("RGB", (width, height), (10, 20, 30))
    second = Image.new("RGB", (width, height), (200, 210, 220))
    buf = io.BytesIO()
    first.save(buf, format="MPO", save_all=True, append_images=[second])
    return buf.getvalue()


def _photographic_image(width: int, height: int) -> Image.Image:
    """A photograph stand-in: a colour gradient with real per-pixel noise blended in.

    A bare gradient compresses losslessly to almost nothing, which would
    never land on the lossy side of a lossy-versus-lossless size comparison.
    Blending in noise gives it the entropy an actual camera photo has, so a
    caller comparing encode sizes gets a realistic result rather than one
    that only holds for flat test images.
    """
    gradient = Image.new("RGB", (2, 2))
    for corner, colour in zip(
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(10, 10, 200), (200, 10, 10), (10, 200, 10), (200, 200, 10)],
        strict=True,
    ):
        gradient.putpixel(corner, colour)
    gradient = gradient.resize((width, height), Image.Resampling.BILINEAR)
    noise = Image.merge(
        "RGB", [Image.effect_noise((width, height), 40) for _ in range(3)]
    )
    return Image.blend(gradient, noise, 0.5)


def photographic_jpeg_bytes(width: int = 2000, height: int = 1500) -> bytes:
    """A large photograph in the container that says the author already accepted lossy compression."""
    buf = io.BytesIO()
    _photographic_image(width, height).save(buf, format="JPEG")
    return buf.getvalue()


def photographic_png_bytes(width: int = 2000, height: int = 1500) -> bytes:
    """The same photograph in a lossless container, where the format alone no longer settles the encode.

    A JPEG source is compressed lossily once and never compared. Photographic
    content in a PNG is the case where the two candidates have to be measured
    against each other, and the only one where the lossy candidate wins.
    """
    buf = io.BytesIO()
    _photographic_image(width, height).save(buf, format="PNG")
    return buf.getvalue()


def screenshot_png_bytes(width: int = 2000, height: int = 1500) -> bytes:
    """A large screenshot stand-in: flat colour blocks and hard edges, the shape lossless WebP handles far better than a photograph."""
    img = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width, height // 8), fill=(30, 60, 120))
    draw.rectangle((0, height // 8, width // 6, height), fill=(225, 225, 225))
    draw.rectangle(
        (width // 3, height // 2, 2 * width // 3, height // 2 + 60), fill=(20, 20, 20)
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def already_minimal_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """A tiny PNG whose pixel data carries enough entropy that a lossless WebP re-encode cannot beat it.

    A flat fill compresses too well in both formats to prove anything --
    WebP's container is smaller than PNG's down at that end, so the never-
    grow guardrail needs a source that already wins on its own terms. The
    fixed seed keeps this fixture the same image on every run.
    """
    generator = random.Random(0)  # noqa: S311 -- fixture bytes, not a security use
    img = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            img.putpixel(
                (x, y),
                (
                    generator.randrange(256),
                    generator.randrange(256),
                    generator.randrange(256),
                ),
            )
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
