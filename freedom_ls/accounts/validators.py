import io

from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from freedom_ls.accounts.images import PROFILE_PICTURE_SIDE
from freedom_ls.base.images import (
    BOMB_FAILURES,
    DECODE_FAILURES,
    bomb_warnings_as_errors,
    truncated_images_rejected,
)

# MPO is a JPEG with extra frames appended (a phone's depth or portrait
# data). Pillow reports it as its own format; the first frame is the photo.
ALLOWED_FORMATS = frozenset({"JPEG", "MPO", "PNG", "WEBP"})
MAX_BYTES = 10 * 1024 * 1024
MIN_SIDE = 128
MAX_PIXELS = 50_000_000

WRONG_TYPE = "Use a JPEG, PNG or WebP image."
TOO_MANY_PIXELS = (
    "That image is too large to process. "
    f"Use one under {MAX_PIXELS // 1_000_000} megapixels."
)
UNREADABLE = "That image could not be read. Save it again or choose another file."


def _too_large(size: int) -> ValidationError:
    limit_mb = MAX_BYTES // (1024 * 1024)
    return ValidationError(
        f"That file is {size / (1024 * 1024):.1f} MB. The limit is {limit_mb} MB."
    )


def validate_profile_picture(file: UploadedFile) -> bytes:
    """Return the upload's bytes once every check has passed.

    The checks run cheapest first, so nothing large is read or decoded
    before it is refused: declared size, a bounded read, the header, then
    the full decode. No message carries the uploader's filename or
    Pillow's own text.
    """
    if (file.size or 0) > MAX_BYTES:
        raise _too_large(file.size or 0)
    file.seek(0)
    # One byte over the cap is all it takes to refuse a handle that
    # under-reported its size.
    raw: bytes = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise _too_large(len(raw))

    with bomb_warnings_as_errors(), truncated_images_rejected():
        try:
            img = Image.open(io.BytesIO(raw))
            # The decoder's verdict, never the extension or Content-Type.
            if img.format not in ALLOWED_FORMATS:
                raise ValidationError(WRONG_TYPE)
            width, height = img.size
            if width * height > MAX_PIXELS:
                raise ValidationError(TOO_MANY_PIXELS)
            if width < MIN_SIDE or height < MIN_SIDE:
                raise ValidationError(
                    f"That image is {width}\u00d7{height} pixels. "
                    f"Use one at least {MIN_SIDE}\u00d7{MIN_SIDE}."
                )
            # A header can parse cleanly over a truncated body; only a
            # full decode finds that. The draft keeps a large JPEG from
            # decoding at full size just to be checked.
            img.draft("RGB", (PROFILE_PICTURE_SIDE, PROFILE_PICTURE_SIDE))
            img.load()
        except BOMB_FAILURES as err:
            raise ValidationError(TOO_MANY_PIXELS) from err
        except Image.UnidentifiedImageError as err:
            # Pillow has no decoder for it: HEIC and SVG land here.
            raise ValidationError(WRONG_TYPE) from err
        except DECODE_FAILURES as err:
            raise ValidationError(UNREADABLE) from err
    return raw
