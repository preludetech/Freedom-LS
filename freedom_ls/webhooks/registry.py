from freedom_ls.webhooks.config import config

# Event types that were renamed to the audit action code for the same change,
# each mapped to the code or codes it became. dispatch_event matches an event
# still carrying an old code against the new subscriptions, so an event queued
# before migration 0002_rename_event_types rewrote them is not dropped. The
# migration holds its own frozen copy of this map; a test keeps the two equal.
# Keep an entry for as long as a WebhookEvent with its old code might still be
# waiting to be dispatched.
RENAMED_EVENT_TYPES: dict[str, tuple[str, ...]] = {
    "user.registered": ("user.signed_up",),
    "course.registered": ("registration.added", "registration.reactivated"),
    "course.unregistered": ("registration.deactivated",),
    "cohort.course_registered": (
        "cohort_registration.added",
        "cohort_registration.reactivated",
    ),
    "cohort.course_unregistered": ("cohort_registration.deactivated",),
    "cohort.member_added": ("cohort_membership.added",),
    "cohort.member_removed": ("cohort_membership.removed",),
}


def get_event_type_registry() -> dict[str, str]:
    """Return {value: label} dict from WEBHOOK_EVENT_TYPES setting."""
    return dict(config.WEBHOOK_EVENT_TYPES)


def validate_event_type(event_type: str) -> None:
    """Raise ValueError if event_type is not in the registry."""
    registry = get_event_type_registry()
    if event_type not in registry:
        raise ValueError(
            f"Unknown webhook event type: {event_type!r}. "
            f"Valid types: {sorted(registry.keys())}"
        )
