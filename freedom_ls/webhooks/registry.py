from django.conf import settings


def get_event_type_registry() -> dict[str, str]:
    """Return {value: label} dict from WEBHOOK_EVENT_TYPES setting."""
    return dict(settings.WEBHOOK_EVENT_TYPES)


def validate_event_type(event_type: str) -> None:
    """Raise ValueError if event_type is not in the registry."""
    registry = get_event_type_registry()
    if event_type not in registry:
        raise ValueError(
            f"Unknown webhook event type: {event_type!r}. "
            f"Valid types: {sorted(registry.keys())}"
        )
