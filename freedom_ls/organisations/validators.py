"""Logo upload validation.

Two layers: a fast extension allowlist, and a byte-level check that is the
authoritative one. The extension check alone is a filter, not a security
boundary — it would happily let an SVG renamed to ``.png`` through, and SVG
is XML that can carry ``<script>``, ``on*`` handlers and ``<foreignObject>``
HTML. ``validate_organisation_logo`` decodes the actual bytes with Pillow and
asserts the real format, which is what catches that case.
"""

from __future__ import annotations

import dataclasses
import io

from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator

from freedom_ls.base.images import (
    BOMB_FAILURES,
    DECODE_FAILURES,
    bomb_warnings_as_errors,
)

ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg", "webp"]
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_BYTES = 2 * 1024 * 1024  # 2 MiB
MAX_DIMENSION = 4000  # px, each axis
MIN_WIDTH, MIN_HEIGHT = 64, 32

# Pillow's format name -> the mediatype to label those decoded bytes with.
# Keyed by the same names ALLOWED_FORMATS holds, so a format added or removed
# there cannot silently disagree with what a consumer of an already-uploaded
# logo will accept.
LOGO_MIME_TYPES: dict[str, str] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}

validate_organisation_logo_extension = FileExtensionValidator(ALLOWED_EXTENSIONS)


@dataclasses.dataclass(frozen=True)
class SafeLogo:
    """A logo that cleared every safety check, and what decoding it found."""

    mime_type: str
    width: int
    height: int


def check_logo_safety(raw: bytes) -> SafeLogo:
    """Decode ``raw`` and return what it is, or raise ValidationError saying why not.

    The safety half of logo validation, kept in one place because it has two
    callers that must not drift: the upload validator here, and the report
    pipeline reading an already-stored logo back out. Field validators only run
    under ``full_clean()``, so an unvalidated file can reach storage regardless
    of what the upload form would have rejected — which makes the read side a
    second enforcement point rather than a formality.

    Size, decodability, both decompression-bomb bands and the format allowlist
    are all safety: getting them wrong means an unrenderable or memory-hostile
    file reaching the renderer. The minimum-dimension rule is not — a small
    logo renders fine, it is merely poor — so it stays with the upload path,
    which is the only place worth refusing it.
    """
    if len(raw) > MAX_BYTES:
        raise ValidationError(
            f"Image file is too large ({len(raw) / 1024 / 1024:.1f}MB; maximum is 2MB)."
        )

    with bomb_warnings_as_errors():
        try:
            # verify() decodes the whole stream rather than only the header,
            # and it destroys the object it is called on — hence the second
            # open below. A header can parse cleanly over a truncated body,
            # and that file would then be embedded as an image the renderer
            # silently fails to draw.
            Image.open(io.BytesIO(raw)).verify()
            img = Image.open(io.BytesIO(raw))
            width, height = img.size
            image_format = img.format
        except BOMB_FAILURES as err:
            raise ValidationError("Image is too large to process safely.") from err
        except DECODE_FAILURES as err:
            raise ValidationError("File is not a readable image.") from err

    mime_type = LOGO_MIME_TYPES.get(image_format or "")
    if image_format not in ALLOWED_FORMATS or mime_type is None:
        raise ValidationError(
            f"Image format {image_format} is not supported. Use PNG, JPEG or WebP."
        )
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValidationError(
            f"Image is too large ({width}x{height}px; maximum is 4000x4000px)."
        )
    return SafeLogo(mime_type=mime_type, width=width, height=height)


def validate_organisation_logo(file: UploadedFile) -> None:
    """Reject anything that is not a genuine, safely-sized PNG/JPEG/WebP.

    EXIF is deliberately not stripped. Stripping means re-encoding, and
    re-encoding a transparent WebP risks a visible regression in exactly the
    asset class this validator targets. The usual motivation for stripping —
    location metadata in personal photos — does not apply to an
    admin-uploaded corporate logo.
    """
    # size is None only for a File that was never actually uploaded (not a
    # real case for an ImageField's UploadedFile); 0 makes that fall through
    # to the byte-level check below, which rejects it as unreadable. Checked
    # before reading so an enormous upload is never pulled into memory.
    size = file.size or 0
    if size > MAX_BYTES:
        raise ValidationError(
            f"Image file is too large ({size / 1024 / 1024:.1f}MB; maximum is 2MB)."
        )

    try:
        file.seek(0)
        # Bounded by the cap plus one, so an unknown-size handle still cannot
        # read unboundedly: one byte over is all check_logo_safety needs to
        # reject it.
        logo = check_logo_safety(file.read(MAX_BYTES + 1))
    finally:
        file.seek(0)

    if logo.width < MIN_WIDTH or logo.height < MIN_HEIGHT:
        raise ValidationError(
            f"Image is too small ({logo.width}x{logo.height}px; minimum is 64x32px)."
        )
