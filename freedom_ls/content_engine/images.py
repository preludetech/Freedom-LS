"""Re-encode an author's content image to WebP, or decide to leave it alone.

Pure bytes in, bytes out: no Django or ORM imports, so this is testable on
raw image bytes with no database.
"""

from __future__ import annotations

import dataclasses
import io
from enum import StrEnum

from PIL import ExifTags, Image, ImageOps

from freedom_ls.base.images import BOMB_FAILURES, DECODE_FAILURES


class ImageEncodeStatus(StrEnum):
    OPTIMISED = "optimised"
    KEPT_SOURCE = "kept source"
    PASSTHROUGH = "passthrough"
    UNDECODABLE = "could not decode"


@dataclasses.dataclass(frozen=True)
class ImageEncodeDecision:
    """What to store, and what to tell the author. Always returned.

    ``data is None`` means "store the original bytes unchanged" and covers
    SVG, animation, undecodable input, an already-small WebP and the
    never-grow guardrail alike, so a caller has exactly one branch and can
    never pair one status's bytes with another status's name. ``data``,
    ``suffix``, ``mime_type``, ``lossless`` and ``stored_size`` are set
    together or not at all, and are ``None`` unless ``status`` is
    ``OPTIMISED``. ``error`` is the mirror of that: set only when ``status``
    is ``UNDECODABLE``. ``source_format`` and ``source_size`` are filled in
    whenever Pillow decoded far enough to know them, and are both ``None``
    when it did not.
    """

    status: ImageEncodeStatus
    source_format: str | None
    source_size: tuple[int, int] | None
    data: bytes | None
    suffix: str | None
    mime_type: str | None
    lossless: bool | None
    stored_size: tuple[int, int] | None
    error: str | None


# Longest edge, in pixels. Covers the lightbox rendering at 2x pixel density.
MAX_DIMENSION_PX = 1600

# Fidelity dial, 0-100, used only on the lossy branch.
LOSSY_QUALITY = 80

# Passed as quality= when lossless=True. Under lossless encoding this number
# is encode *effort*, not fidelity: the output pixels are bit-exact
# regardless of its value, so it is not commensurable with LOSSY_QUALITY
# even though both flow through the same parameter.
LOSSLESS_EFFORT = 100

# libwebp's compression effort, 0 fast to 6 slowest and smallest. Each image
# is encoded once at ingest and read many times after, so the slow end pays
# for itself.
ENCODE_METHOD = 6

# The lossless size, in bytes, above which a second, lossy encode is worth
# running for comparison.
SECOND_ENCODE_BYTES = 250 * 1024

# The margin a lossy encode must beat a lossless one by before it wins the
# comparison. Integer arithmetic on both sides, never floats.
LOSSY_WINS_DIVISOR = 3

# The EXIF orientations whose transform swaps the two axes: transpose,
# rotate 90, transverse and rotate 270. The other four leave them alone.
TRANSPOSED_ORIENTATIONS = frozenset({5, 6, 7, 8})

# .svgz is deliberately absent: get_file_type_from_extension does not list
# it, so a .svgz is never File.FileType.IMAGE and cannot reach this module.
SVG_SUFFIXES = {".svg"}


def _store_source(
    status: ImageEncodeStatus,
    *,
    source_format: str | None = None,
    source_size: tuple[int, int] | None = None,
    error: str | None = None,
) -> ImageEncodeDecision:
    """A decision to store the original bytes: everything the encode would have filled in stays None.

    Every outcome other than OPTIMISED lands here, so the five encode fields
    can only ever be blanked as a group rather than one call site at a time.
    """
    return ImageEncodeDecision(
        status=status,
        source_format=source_format,
        source_size=source_size,
        data=None,
        suffix=None,
        mime_type=None,
        lossless=None,
        stored_size=None,
        error=error,
    )


# Pillow's WebP _save reads exif, xmp and icc_profile from encoderinfo only,
# never from img.info, and Image.save() does not merge the two. So *not*
# passing exif= is what drops EXIF, including the GPS coordinates phones
# attach to photos, and icc_profile is the one thing that has to be passed
# back deliberately or it is lost the same way. This is WebP-specific: the
# JPEG and PNG save paths both read from img.info. Do not "fix" this to
# match libwebp's own -mixed behaviour, which dual-encodes and keeps
# whichever bitstream is smaller — that suits animation frames, where either
# candidate is acceptable, but the two candidates here are not interchangeable.
def _encode(img: Image.Image, icc: bytes | None, *, lossless: bool) -> bytes:
    buf = io.BytesIO()
    img.save(
        buf,
        format="WEBP",
        lossless=lossless,
        quality=LOSSLESS_EFFORT if lossless else LOSSY_QUALITY,
        method=ENCODE_METHOD,
        icc_profile=icc,
    )
    return buf.getvalue()


def optimise_image(raw: bytes, suffix: str) -> ImageEncodeDecision:
    """Decide what to store for one content image.

    Nothing raises out of this function, from the decode through to the
    encode: one bad file must neither abort a run over a whole content
    repository nor vanish from it. See freedom_ls/base/images.py for why the
    decompression-bomb warning band is allowed to decode here rather than
    escalated as check_logo_safety does.
    """
    if suffix.lower() in SVG_SUFFIXES:
        # Pillow has no SVG codec. get_file_type_from_extension lowercases
        # the same suffix before classifying a file as IMAGE, so this check
        # has to lowercase too or DIAGRAM.SVG would fall through to a decode
        # it cannot survive.
        return _store_source(ImageEncodeStatus.PASSTHROUGH, source_format="SVG")

    # Both stay None when Image.open itself raises: a PNG with a too-short
    # IHDR fails before there is a format to name.
    source_format: str | None = None
    source_size: tuple[int, int] | None = None
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            source_format = opened.format
            # Read before draft() and thumbnail() below, both of which
            # mutate .size in place.
            source_size = opened.size

            if source_format != "MPO" and getattr(opened, "n_frames", 1) > 1:
                # getattr, not is_animated: JpegImageFile and BmpImageFile
                # define neither. MPO is excluded because phone .jpg files
                # open as format MPO with n_frames == 2, and a bare frame
                # count would pass real photos through untouched.
                return _store_source(
                    ImageEncodeStatus.PASSTHROUGH,
                    source_format=source_format,
                    source_size=source_size,
                )

            if source_format == "WEBP" and max(source_size) <= MAX_DIMENSION_PX:
                # Re-encoding buys nothing here and spends a generation of
                # quality for no benefit.
                return _store_source(
                    ImageEncodeStatus.PASSTHROUGH,
                    source_format=source_format,
                    source_size=source_size,
                )

            # A no-op for non-JPEG formats. For JPEG, libjpeg DCT scaling
            # cuts the decode buffer 4-64x. Must run before exif_transpose()
            # below: draft() only works on an unloaded image, and
            # exif_transpose() loads it.
            opened.draft(None, (MAX_DIMENSION_PX * 2, MAX_DIMENSION_PX * 2))

            # Returns a new image, never None, and calls load() as its
            # first statement, which is where a corrupt body raises.
            img = ImageOps.exif_transpose(opened)

            icc = opened.info.get("icc_profile")
            # getexif(), never opened.info["exif"], so a PNG carrying EXIF
            # in a text chunk is still read.
            tags = opened.getexif()
            camera_exif = bool(
                tags.get(ExifTags.Base.Make) or tags.get(ExifTags.Base.Model)
            )
            if tags.get(ExifTags.Base.Orientation) in TRANSPOSED_ORIENTATIONS:
                # exif_transpose has just swapped the axes on img, and
                # source_size was read off the raw buffer. Swap it too, or
                # the author-facing line pairs a sideways source with an
                # upright output and reads as an aspect-ratio change.
                source_size = (source_size[1], source_size[0])

        source_mode = img.mode
        if source_mode not in ("RGB", "RGBA"):
            # Resampling a P-mode image interpolates palette indices,
            # inventing colours the source never had, so this has to happen
            # before the resize rather than waiting for the encoder's own
            # conversion.
            img = img.convert("RGBA" if img.has_transparency_data else "RGB")
            if source_mode not in {"RGB", "RGBX", "RGBA", "RGBa", "P", "PA"}:
                # Image._new copies info through convert(), so a CMYK or
                # greyscale profile would otherwise ride along describing a
                # colour space the pixels have already left.
                icc = None

        # A square box makes this a longest-edge cap with no orientation
        # branch. thumbnail() returns early when the image already fits, which
        # is where "never upscale" comes from; ImageOps.contain has no such
        # guard. Both default to BICUBIC, so LANCZOS is passed explicitly.
        img.thumbnail((MAX_DIMENSION_PX, MAX_DIMENSION_PX), Image.Resampling.LANCZOS)

        if source_format in ("JPEG", "MPO"):
            # The pixels are already lossily compressed, so a lossless encode
            # would preserve the existing artefacts bit-exactly at several
            # times the bytes: not worth comparing.
            encoded, lossless = _encode(img, icc, lossless=False), False
        else:
            candidate = _encode(img, icc, lossless=True)
            if not camera_exif and len(candidate) <= SECOND_ENCODE_BYTES:
                encoded, lossless = candidate, True
            else:
                # Lossy WebP always chroma-subsamples, which is what smears
                # coloured text and thin lines, so raising LOSSY_QUALITY never
                # fixes a screenshot. Gating this comparison behind the size
                # floor above keeps screenshots out of it entirely and leaves
                # the ratio below to arbitrate only large images, which are
                # overwhelmingly photographs.
                lossy = _encode(img, icc, lossless=False)
                if len(lossy) * LOSSY_WINS_DIVISOR <= len(candidate):
                    encoded, lossless = lossy, False
                else:
                    encoded, lossless = candidate, True
    except BOMB_FAILURES + DECODE_FAILURES as err:
        # Deliberately spans the encode as well as the decode: libwebp
        # reports a write it cannot complete as an OSError, and an
        # unexpected mode conversion as a ValueError, so leaving the guard
        # around Image.open alone would leave two ways to abort a run.
        return _store_source(
            ImageEncodeStatus.UNDECODABLE,
            source_format=source_format,
            source_size=source_size,
            error=f"{type(err).__name__}: {err}",
        )

    if len(encoded) >= len(raw):
        # Strict: a tie keeps the source rather than churning the extension
        # and MIME type for nothing.
        return _store_source(
            ImageEncodeStatus.KEPT_SOURCE,
            source_format=source_format,
            source_size=source_size,
        )

    return ImageEncodeDecision(
        status=ImageEncodeStatus.OPTIMISED,
        source_format=source_format,
        source_size=source_size,
        data=encoded,
        suffix=".webp",
        mime_type="image/webp",
        lossless=lossless,
        stored_size=img.size,
        error=None,
    )
