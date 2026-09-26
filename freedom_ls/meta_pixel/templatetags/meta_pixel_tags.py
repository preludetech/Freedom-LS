from django import template

from freedom_ls.base.analytics_events import (
    AnalyticsEventPayload,
    PixelCall,
    pixel_call,
)
from freedom_ls.meta_pixel.events import MAPPING

register = template.Library()


@register.filter
def meta_pixel_call(event: AnalyticsEventPayload) -> PixelCall | None:
    """The Meta pixel call for `event`, or None when the mapping does not cover it."""
    return pixel_call(MAPPING, event)
