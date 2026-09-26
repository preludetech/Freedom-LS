from django import template

from freedom_ls.google_tag.config import config
from freedom_ls.google_tag.google_ads import conversion_send_to

register = template.Library()


@register.filter
def google_ads_send_to(event_name: str) -> str | None:
    """The Ads conversion `send_to` for an event, worked out at render time so a
    label change in the environment applies to events already in a session."""
    return conversion_send_to(
        config.GOOGLE_ADS_CONVERSION_ID, config.GOOGLE_ADS_CONVERSION_LABELS, event_name
    )
