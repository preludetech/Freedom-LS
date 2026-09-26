from django.http import HttpRequest

from freedom_ls.base.analytics_events import ad_pixels_allowed
from freedom_ls.tiktok_pixel.config import config


def tiktok_pixel_config(request: HttpRequest) -> dict[str, str | None]:
    """`tiktok_pixel_id` is None whenever the pixel must not load, so a
    template tests one variable."""
    if not ad_pixels_allowed(request):
        return {"tiktok_pixel_id": None}
    return {"tiktok_pixel_id": config.TIKTOK_PIXEL_ID}
