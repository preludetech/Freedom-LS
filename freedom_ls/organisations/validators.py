"""Logo upload validation.

Two layers: a fast extension allowlist, and a byte-level check that is the
authoritative one. The extension check alone is a filter, not a security
boundary — it would happily let an SVG renamed to ``.png`` through, and SVG
is XML that can carry ``<script>``, ``on*`` handlers and ``<foreignObject>``
HTML. ``validate_organisation_logo`` decodes the actual bytes with Pillow and
asserts the real format, which is what catches that case.
"""

from __future__ import annotations

import warnings

from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator

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
    # to the byte-level check below, which rejects it as unreadable.
    size = file.size or 0
    if size > MAX_BYTES:
        raise ValidationError(
            f"Image file is too large ({size / 1024 / 1024:.1f}MB; maximum is 2MB)."
        )

    with warnings.catch_warnings():
        # Pillow signals a bomb in two bands and neither reaches the caller on
        # its own: past MAX_IMAGE_PIXELS it only warns, which does nothing in
        # production unless escalated; past twice that it raises
        # DecompressionBombError, which subclasses Exception rather than
        # OSError and so would sail past the unreadable-image clause below as a
        # 500. Both have to land on the same ValidationError.
        # MAX_IMAGE_PIXELS stays at Pillow's default — never None.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            file.seek(0)
            Image.open(file).verify()  # destroys the object it is called on
            file.seek(0)
            img = Image.open(file)  # re-open on a rewound handle
            width, height = img.size
            image_format = img.format
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as err:
            raise ValidationError("Image is too large to process safely.") from err
        except (OSError, Image.UnidentifiedImageError) as err:
            raise ValidationError("File is not a readable image.") from err
        finally:
            file.seek(0)

    if image_format not in ALLOWED_FORMATS:
        raise ValidationError(
            f"Image format {image_format} is not supported. Use PNG, JPEG or WebP."
        )
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValidationError(
            f"Image is too large ({width}x{height}px; maximum is 4000x4000px)."
        )
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise ValidationError(
            f"Image is too small ({width}x{height}px; minimum is 64x32px)."
        )
