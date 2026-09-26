"""Django system checks for the meta_pixel app.

W001 — META_PIXEL_ID is set but VISITOR_COUNTRY_HEADER is not, so the pixel
       would never load.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import Warning, register


@register()
def check_meta_pixel_needs_visitor_country(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Warning]:
    from freedom_ls.base.checks import pixel_without_visitor_country_warning
    from freedom_ls.meta_pixel.config import config

    return pixel_without_visitor_country_warning(
        setting_name="META_PIXEL_ID",
        pixel_id=config.META_PIXEL_ID,
        check_id="freedom_ls_meta_pixel.W001",
    )
