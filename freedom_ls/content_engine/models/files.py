from pathlib import Path

from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import SiteAwareModel


def file_upload_handler(instance, filepath):
    filepath = Path(filepath)
    ext = filepath.suffix
    stem = filepath.stem
    pk = instance.pk
    if not pk:
        raise ValueError("Instance must be saved before uploading files")
    return f"content_engine/{stem}{pk}{ext}"


class File(SiteAwareModel):
    """Stores files (images, documents, etc.) referenced in content."""

    class FileType(models.TextChoices):
        IMAGE = "IMAGE", _("Image")
        DOCUMENT = "DOCUMENT", _("Document")
        VIDEO = "VIDEO", _("Video")
        AUDIO = "AUDIO", _("Audio")
        OTHER = "OTHER", _("Other")

    file = models.FileField(upload_to=file_upload_handler)
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
        unique_together = ["site", "file_path"]

    def __str__(self):
        return f"{self.original_filename} ({self.get_file_type_display()})"
