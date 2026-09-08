"""The one gate an applicant's file passes before it reaches storage.

Nothing the applicant supplies is trusted: not the filename, not the extension,
not the declared size. An image is decoded and re-encoded, so what lands in the
bucket is bytes Pillow wrote rather than bytes the applicant did -- which also
takes the EXIF, and with it any GPS fix, off a phone photo. A PDF is not
re-encoded (there is no safe general rewrite of one), so it is stored as
supplied and never served to anyone but its owner until it is scanned.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile

from freedom_ls.base.images import (
    BOMB_FAILURES,
    DECODE_FAILURES,
    bomb_warnings_as_errors,
)

MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_UPLOAD_LABEL = "6 MB"
ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".pdf"})
ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png"}
ACCEPT_ATTRIBUTE = ",".join(sorted(ALLOWED_EXTENSIONS))
PDF_MAGIC = b"%PDF-"

TOO_LARGE = f"That file is larger than {MAX_UPLOAD_LABEL}. Choose a smaller one."
WRONG_KIND = "Upload a JPEG, PNG or PDF."


def validate_and_sanitise(
    uploaded_file: UploadedFile | None,
) -> tuple[ContentFile, str]:
    """Return the bytes to store and the extension to store them under.

    The returned extension is the one detected from the content, so a file named
    `.png` carrying a JPEG is stored as `.jpg` and the applicant's own filename
    never reaches a storage key.
    """
    if uploaded_file is None:
        raise ValidationError("Choose a file to upload.")
    if Path(uploaded_file.name or "").suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError(WRONG_KIND)
    # Checked before reading, so an enormous upload is never pulled into memory.
    if (uploaded_file.size or 0) > MAX_UPLOAD_BYTES:
        raise ValidationError(TOO_LARGE)

    try:
        uploaded_file.seek(0)
        # Bounded by the cap plus one, so a handle of unknown size still cannot
        # read unboundedly: one byte over is all it takes to refuse it.
        raw = uploaded_file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        uploaded_file.seek(0)

    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationError(TOO_LARGE)

    if raw.startswith(PDF_MAGIC):
        return ContentFile(raw), ".pdf"
    return _reencode_image(raw)


def _reencode_image(raw: bytes) -> tuple[ContentFile, str]:
    with bomb_warnings_as_errors():
        try:
            # verify() decodes the whole stream rather than only the header, and
            # destroys the object it is called on -- hence the second open. A
            # header can parse cleanly over a truncated body, and that file would
            # then be stored as an image nothing can draw.
            Image.open(io.BytesIO(raw)).verify()
            opened = Image.open(io.BytesIO(raw))
            image_format = opened.format
            opened.load()
        except BOMB_FAILURES as err:
            raise ValidationError("Image is too large to process safely.") from err
        except DECODE_FAILURES as err:
            raise ValidationError("File is not a readable image or PDF.") from err

    extension = ALLOWED_IMAGE_FORMATS.get(image_format or "")
    if extension is None:
        raise ValidationError(WRONG_KIND)

    # Apply the orientation tag before dropping the metadata that carries it, so
    # a phone photo is stored the way up it was taken.
    image: Image.Image = ImageOps.exif_transpose(opened)
    if image_format == "JPEG":
        image = image.convert("RGB")

    buffer = io.BytesIO()
    # No exif= kwarg, so the EXIF block -- GPS fix included -- is not carried over.
    image.save(buffer, format=image_format)
    return ContentFile(buffer.getvalue()), extension
