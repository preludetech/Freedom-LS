"""Shared Pillow decode guard, used by anything that opens an untrusted or
author-supplied image.

Pillow's plugins report a malformed structure with whatever exception the
parser reached for, not one family: a PNG whose chunk checksum fails raises
SyntaxError, one whose IHDR is too short raises ValueError, and only an
unrecognisable or truncated body raises OSError. Catching OSError alone lets
the first two through as an unhandled exception.

Seeking a truncated animated GIF's frames adds two more, because the plugin
reads the fragment's remaining bytes without checking there are enough: a
two-byte duration field goes through struct.unpack_from and raises
struct.error, and a one-byte block label is read by index and raises
IndexError. Which of the two a given truncation reaches depends on where it
stops, so both belong in the family.

A decompression bomb is a second, separate failure mode, signalled in two
bands: past ``Image.MAX_IMAGE_PIXELS`` Pillow only warns, which does nothing
in production unless escalated to an exception; past twice that it raises
``DecompressionBombError``, which subclasses ``Exception`` rather than
``OSError`` and so needs catching by name.
"""

from __future__ import annotations

import contextlib
import struct
import warnings
from collections.abc import Iterator

from PIL import Image

DECODE_FAILURES = (
    OSError,
    Image.UnidentifiedImageError,
    SyntaxError,
    ValueError,
    struct.error,
    IndexError,
)
BOMB_FAILURES = (Image.DecompressionBombWarning, Image.DecompressionBombError)


@contextlib.contextmanager
def bomb_warnings_as_errors() -> Iterator[None]:
    """Escalate ``DecompressionBombWarning`` to an exception for the duration of the block.

    A caller that decodes an image without this is choosing to decode the
    warning band rather than reject it. The two callers in this repo choose
    differently on purpose: ``check_logo_safety`` is refusing an untrusted
    upload, so it escalates and rejects anything past ``MAX_IMAGE_PIXELS``.
    ``optimise_image`` is processing an author's own file, where escalating
    would classify a legitimate 90-179 megapixel photo as unprocessable and
    store it at full size instead, so it lets the warning band decode and
    only catches ``DecompressionBombError``.

    ``Image.MAX_IMAGE_PIXELS`` stays at Pillow's default for both callers,
    and ``ImageFile.LOAD_TRUNCATED_IMAGES`` is never set anywhere in this
    repo: it is a global flag, and ``check_logo_safety`` depends on a
    truncated file failing to decode.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        yield
