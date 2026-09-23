"""Google Ads conversion tracking, layered on the GA4 tag.

Ads shares the gtag.js loader `_base.html` already loads for GA4 and adds a
second `config` call. A conversion is a separate `gtag('event', 'conversion',
{send_to: 'AW-ID/LABEL'})` call, where the label identifies one conversion
action in the operator's Ads account. FLS learns the labels from one setting
that maps event names to them, so a mapped event sends its conversion beside
the GA4 event and an unmapped one sends nothing extra.

No Django model imports: `config/settings_base.py` calls the parser while the
settings module is still being built.
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


def parse_conversion_labels(raw: str) -> dict[str, str]:
    """`"sign_up=AbCdEf,course_registered=GhIjKl"` as `{event_name: label}`.

    Whitespace around pairs and sides is ignored, as is a trailing comma. A
    pair without `=` or with an empty side raises, so a typo in the deployment
    environment fails at boot rather than sending nothing for months.
    """
    labels: dict[str, str] = {}
    for pair in raw.split(","):
        if not pair.strip():
            continue
        event_name, separator, label = pair.partition("=")
        event_name = event_name.strip()
        label = label.strip()
        if not separator or not event_name or not label:
            raise ImproperlyConfigured(
                f"GOOGLE_ADS_CONVERSION_LABELS entry {pair.strip()!r} is not of the "
                f"form event_name=label."
            )
        labels[event_name] = label
    return labels


def conversion_send_to(
    conversion_id: str | None, labels: dict[str, str], event_name: str
) -> str | None:
    """The `send_to` for an event's Ads conversion, or None when it has none."""
    label = labels.get(event_name)
    if conversion_id is None or label is None:
        return None
    return f"{conversion_id}/{label}"
