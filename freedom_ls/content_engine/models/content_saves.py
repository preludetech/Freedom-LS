from django.db import models
from django.utils import timezone

from freedom_ls.site_aware_models.models import SiteAwareModel


class ContentSave(SiteAwareModel):
    """One successful run of content_save for one site."""

    saved_at = models.DateTimeField(default=timezone.now)
    # True when the run wrote uuids into the source files: the recorded commits
    # were read before the run and do not contain those uuids.
    generate_uuids = models.BooleanField()

    def __str__(self) -> str:
        return f"Content save {self.saved_at:%Y-%m-%d %H:%M}"


class ContentSaveSource(models.Model):
    """One source path of a ContentSave, with the commit it was loaded from.

    No site column: it is only reached through its ContentSave. PROTECT on the
    save so a record of what was loaded is never deleted from under its sources.
    """

    content_save = models.ForeignKey(
        ContentSave, on_delete=models.PROTECT, related_name="sources"
    )
    # Position of the source path on the command line.
    order = models.PositiveIntegerField()
    # Relative to the content repo root; "" is the root itself.
    repo_path = models.CharField(max_length=500, blank=True)
    # The full sha.
    commit = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content_save", "order"],
                name="unique_content_save_source_order",
            )
        ]

    def __str__(self) -> str:
        return f"{self.repo_path or '.'} at {self.commit[:8]}"
