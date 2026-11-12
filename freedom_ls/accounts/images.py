import io

from PIL import Image, ImageOps

PROFILE_PICTURE_SIDE = 400
WEBP_QUALITY = 80


def encode_profile_picture(raw: bytes) -> bytes:
    """The one stored rendition: a centre-cropped square WebP.

    Always re-encodes, so nothing of the upload but its pixels survives:
    no EXIF or XMP (a phone photo carries GPS), and no bytes appended
    after the image data.

    Call it only with bytes ``validate_profile_picture`` returned, which
    already decoded them under the decompression-bomb and truncation guards;
    that is why it carries none of its own.
    """
    with Image.open(io.BytesIO(raw)) as img:
        # JPEG only: decode at a reduced scale that still covers the target.
        img.draft("RGB", (PROFILE_PICTURE_SIDE, PROFILE_PICTURE_SIDE))
        # An animated upload contributes its first frame, which is the
        # frame an opened image sits on.
        upright = ImageOps.exif_transpose(img)
        has_alpha = "A" in upright.getbands() or "transparency" in upright.info
        fitted = ImageOps.fit(
            upright.convert("RGBA" if has_alpha else "RGB"),
            (PROFILE_PICTURE_SIDE, PROFILE_PICTURE_SIDE),
            Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        out = io.BytesIO()
        fitted.save(out, "WEBP", quality=WEBP_QUALITY, exif=b"", xmp=b"")
    return out.getvalue()
