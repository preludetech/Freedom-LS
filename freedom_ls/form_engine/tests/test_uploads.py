"""`validate_and_sanitise` is the only gate an applicant's file passes through
before it reaches storage. It decides what the file really is, refuses anything
else, and hands back bytes FLS chose rather than bytes the applicant supplied.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.form_engine.uploads import MAX_UPLOAD_BYTES, validate_and_sanitise
from freedom_ls.tests.images import gps_exif_jpeg_bytes, jpeg_bytes, png_bytes

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _upload(name: str, content: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content)


def test_no_file_at_all_is_rejected():
    with pytest.raises(ValidationError):
        validate_and_sanitise(None)


def test_an_executable_renamed_as_a_png_is_rejected():
    with pytest.raises(ValidationError):
        validate_and_sanitise(
            _upload("payload.png", b"\x7fELF\x02\x01\x01" + b"\x00" * 64)
        )


def test_a_pdf_renamed_as_a_jpg_is_stored_as_a_pdf():
    """The name an applicant's scanner chose is not evidence of anything. The
    content decides both what is accepted and the extension it is stored under.
    """
    _content, extension = validate_and_sanitise(_upload("scan.jpg", PDF_BYTES))

    assert extension == ".pdf"


def test_an_unlisted_extension_is_rejected():
    with pytest.raises(ValidationError):
        validate_and_sanitise(_upload("notes.docx", png_bytes()))


def test_a_truncated_image_is_rejected():
    with pytest.raises(ValidationError):
        validate_and_sanitise(_upload("half.png", png_bytes()[:-20]))


def test_an_image_past_the_pixel_ceiling_is_rejected(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

    with pytest.raises(ValidationError):
        validate_and_sanitise(_upload("huge.png", png_bytes(width=200, height=200)))


def test_a_file_over_the_byte_cap_is_rejected():
    oversized = png_bytes() + b"\x00" * MAX_UPLOAD_BYTES

    with pytest.raises(ValidationError):
        validate_and_sanitise(_upload("big.png", oversized))


def test_the_handle_is_rewound_after_a_rejection():
    upload = _upload("half.png", png_bytes()[:-20])

    with pytest.raises(ValidationError):
        validate_and_sanitise(upload)

    assert upload.tell() == 0


def test_a_traversal_filename_is_accepted_and_its_name_never_used():
    _content, extension = validate_and_sanitise(
        _upload("../../etc/passwd.png", png_bytes())
    )

    assert extension == ".png"


def test_a_jpeg_masquerading_under_a_png_name_keeps_its_real_extension():
    _content, extension = validate_and_sanitise(_upload("photo.png", jpeg_bytes()))

    assert extension == ".jpg"


def test_gps_metadata_does_not_survive_a_jpeg_upload():
    content, _extension = validate_and_sanitise(
        _upload("holiday.jpg", gps_exif_jpeg_bytes())
    )

    reopened = Image.open(io.BytesIO(content.read()))
    assert reopened.getexif().get_ifd(0x8825) == {}


def test_a_pdf_is_stored_byte_for_byte():
    content, extension = validate_and_sanitise(_upload("scan.pdf", PDF_BYTES))

    assert extension == ".pdf"
    assert content.read() == PDF_BYTES
