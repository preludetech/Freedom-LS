"""The Organisation model — the tenancy layer that sits below a Site."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from django.core.files.storage import Storage
from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.base.initials import two_or_one
from freedom_ls.base.storage import storage_for_alias
from freedom_ls.site_aware_models.models import SiteAwareModel

from .config import config
from .validators import validate_organisation_logo, validate_organisation_logo_extension


def organisation_logo_upload_to(instance: Organisation, filename: str) -> str:
    """Storage path from the pk and the extension only.

    The uploaded filename is never interpolated — that is what prevents path
    traversal, overwrite collisions and leaking the uploader's local paths.
    SiteAwareModel.id defaults at instantiation, so the pk always exists here.
    """
    ext = Path(filename).suffix.lower()
    return f"organisations/{instance.pk}{ext}"


def get_organisation_logo_storage() -> Storage:
    """The alias named by ORGANISATION_LOGO_STORAGE_ALIAS."""
    return storage_for_alias(
        config.ORGANISATION_LOGO_STORAGE_ALIAS, "ORGANISATION_LOGO_STORAGE_ALIAS"
    )


class Organisation(SiteAwareModel):
    name = models.CharField(_("name"), max_length=150)
    slug = models.SlugField(max_length=150)
    logo = models.ImageField(
        upload_to=organisation_logo_upload_to,
        storage=get_organisation_logo_storage,
        blank=True,
        validators=[validate_organisation_logo_extension, validate_organisation_logo],
    )
    #: Marks the one Organisation a Site falls back to when nothing narrower is
    #: in scope. Set only by the post_save receiver on Site — never exposed in
    #: the admin, so the flag cannot be moved to a different Organisation.
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_organisation_slug_per_site"
            ),
            models.UniqueConstraint(
                fields=["site", "name"], name="unique_organisation_name_per_site"
            ),
            # Partial, so the many non-default Organisations on a Site do not
            # collide with each other. This is what lets the receiver key its
            # get_or_create on (site, is_default) and get exactly one row.
            models.UniqueConstraint(
                fields=["site"],
                condition=models.Q(is_default=True),
                name="one_default_organisation_per_site",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        """Save, then remove the logo object this save superseded.

        Overwriting only replaces an object at the same key, and the key carries
        the uploaded file's extension. Four extensions are allowed, so replacing a
        PNG logo with a JPEG writes a second object and abandons the first — in a
        bucket whose whole purpose is anonymous read, which would leave the old
        logo publicly fetchable indefinitely. Deleting is the fix rather than
        normalising the extension away, because the key's extension is what gives
        the object its Content-Type.
        """
        superseded = self._stored_logo_name()
        super().save(*args, **kwargs)
        if superseded and superseded != self.logo.name:
            self.logo.storage.delete(superseded)

    def _stored_logo_name(self) -> str:
        """The logo name the database currently holds, or '' for an unsaved row.

        Read through the base manager, because `objects` filters to the current
        request's Site and this has to see the row whatever Site it belongs to.
        Read from the database rather than tracked on the instance, because
        `logo.save()` mutates and saves an instance that was never loaded.
        """
        if self._state.adding:
            return ""
        return (
            Organisation._base_manager.filter(pk=self.pk)
            .values_list("logo", flat=True)
            .first()
            or ""
        )

    @property
    def initials(self) -> str | None:
        """Two-letter (or single-grapheme) monogram derived from the name.

        Mirrors User.initials (base.initials.two_or_one), but there is no
        email to fall back to here: a name with no alphabetic characters at
        all yields None, so the template can fall back to a generic icon.
        """
        name = unicodedata.normalize("NFC", self.name).strip()
        if not any(ch.isalpha() for ch in name):
            return None
        tokens = name.split()
        if len(tokens) >= 2:
            return two_or_one(tokens[0][0], tokens[1][0])
        return two_or_one(name[0], name[1] if len(name) > 1 else "")
