"""The Organisation model — the tenancy layer that sits below a Site."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.base.initials import two_or_one
from freedom_ls.site_aware_models.models import SiteAwareModel

from .validators import validate_organisation_logo, validate_organisation_logo_extension


def organisation_logo_upload_to(instance: Organisation, filename: str) -> str:
    """Storage path from the pk and the extension only.

    The uploaded filename is never interpolated — that is what prevents path
    traversal, overwrite collisions and leaking the uploader's local paths.
    SiteAwareModel.id defaults at instantiation, so the pk always exists here.
    """
    ext = Path(filename).suffix.lower()
    return f"organisations/{instance.pk}{ext}"


class Organisation(SiteAwareModel):
    name = models.CharField(_("name"), max_length=150)
    slug = models.SlugField(max_length=150)
    logo = models.ImageField(
        upload_to=organisation_logo_upload_to,
        blank=True,
        validators=[validate_organisation_logo_extension, validate_organisation_logo],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_organisation_slug_per_site"
            ),
            models.UniqueConstraint(
                fields=["site", "name"], name="unique_organisation_name_per_site"
            ),
        ]

    def __str__(self) -> str:
        return self.name

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
