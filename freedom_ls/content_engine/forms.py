"""Admin form for File."""

from __future__ import annotations

from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

from .models import File


class FileAdminForm(ConstraintValidationFormMixin):
    """Admin form for File.

    ``site`` is un-excluded from validation so unique_file_path_per_site is
    checked while cleaning rather than failing at the database. It is still
    never rendered.
    """

    class Meta:
        model = File
        exclude = ["site"]
