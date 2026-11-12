import pytest
from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.accounts import validators
from freedom_ls.accounts.tests import profile_picture_samples as samples
from freedom_ls.accounts.validators import validate_profile_picture

UPLOAD_STEM = "holiday-secret-name"


def _upload(data: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(f"{UPLOAD_STEM}.png", data)


def _oversized_upload(declared_size: int) -> SimpleUploadedFile:
    upload = _upload(b"\0" * (validators.MAX_BYTES + 1))
    upload.size = declared_size
    return upload


@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (_oversized_upload(validators.MAX_BYTES + 1), "The limit is 10 MB."),
        (_oversized_upload(10), "The limit is 10 MB."),
        (_upload(b"<svg xmlns='http://www.w3.org/2000/svg'/>"), validators.WRONG_TYPE),
        (
            _upload(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heic"),
            validators.WRONG_TYPE,
        ),
        (_upload(samples.gif_bytes()), validators.WRONG_TYPE),
        (_upload(samples.jpeg_bytes(127, 400)), "127\u00d7400"),
        (_upload(samples.png_bytes(8000, 6500)), validators.TOO_MANY_PIXELS),
        (_upload(samples.truncated_jpeg_bytes()), validators.UNREADABLE),
        (_upload(samples.truncated_png_bytes()), validators.UNREADABLE),
    ],
    ids=[
        "declared-too-big",
        "under-reported-size",
        "svg",
        "heic",
        "gif",
        "too-narrow",
        "over-50-megapixels",
        "truncated-jpeg",
        "truncated-png",
    ],
)
def test_rejected_upload_names_the_reason(
    upload: SimpleUploadedFile, message: str
) -> None:
    with pytest.raises(ValidationError) as err:
        validate_profile_picture(upload)

    assert message in err.value.messages[0]
    assert UPLOAD_STEM not in err.value.messages[0]


def test_decompression_bomb_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100_000)
    monkeypatch.setattr(validators, "MAX_PIXELS", 10**9)

    with pytest.raises(ValidationError) as err:
        validate_profile_picture(_upload(samples.png_bytes(600, 400)))

    assert err.value.messages == [validators.TOO_MANY_PIXELS]


@pytest.mark.parametrize(
    "data",
    [
        samples.jpeg_bytes(4032, 3024),
        samples.jpeg_bytes(8000, 6000),
        samples.png_bytes(),
        samples.webp_bytes(),
        samples.mpo_bytes(),
    ],
    ids=["12mp-jpeg", "48mp-jpeg", "png", "webp", "mpo"],
)
def test_accepted_upload_returns_its_bytes(data: bytes) -> None:
    assert validate_profile_picture(_upload(data)) == data
