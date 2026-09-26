from django.http import HttpRequest

from freedom_ls.base.analytics_events import ad_pixels_allowed
from freedom_ls.meta_pixel.config import config


def meta_pixel_config(request: HttpRequest) -> dict[str, str | None]:
    """`meta_pixel_id` is None whenever the pixel must not load, so a template
    tests one variable."""
    if not ad_pixels_allowed(request):
        return {"meta_pixel_id": None}
    return {"meta_pixel_id": config.META_PIXEL_ID}
