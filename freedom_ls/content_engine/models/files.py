from pathlib import Path

from django.core.files.storage import Storage
from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.base.storage import storage_for_alias
from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel

from ..config import config


def file_upload_handler(instance, filepath):
    filepath = Path(filepath)
    ext = filepath.suffix
    stem = filepath.stem
    pk = instance.pk
    if not pk:
        raise ValueError("Instance must be saved before uploading files")
    return f"content_engine/{stem}{pk}{ext}"


def get_content_media_storage() -> Storage:
    """The alias named by CONTENT_MEDIA_STORAGE_ALIAS."""
    return storage_for_alias(
        config.CONTENT_MEDIA_STORAGE_ALIAS, "CONTENT_MEDIA_STORAGE_ALIAS"
    )


class File(SiteAwareModel, TimestampedModel):
    """Stores files (images, documents, etc.) referenced in content."""

    class FileType(models.TextChoices):
        IMAGE = "IMAGE", _("Image")
        DOCUMENT = "DOCUMENT", _("Document")
        VIDEO = "VIDEO", _("Video")
        AUDIO = "AUDIO", _("Audio")
        OTHER = "OTHER", _("Other")

    file = models.FileField(
        upload_to=file_upload_handler, storage=get_content_media_storage
    )
    file_type = models.CharField(
        max_length=20, choices=FileType.choices, default=FileType.OTHER
    )
    file_path = models.CharField(
        max_length=500,
        help_text=_("Relative path to the source file"),
    )
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "file_path"], name="unique_file_path_per_site"
            )
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.get_file_type_display()})"
