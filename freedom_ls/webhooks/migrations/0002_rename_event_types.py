from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# Webhook event types now carry the same code as the audit action for the
# same change. An endpoint subscribed to an old code is subscribed to every
# code it split into. Past WebhookEvent rows keep the code that was sent.
RENAMES: dict[str, tuple[str, ...]] = {
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


def _rewrite(apps: Apps, mapping: dict[str, tuple[str, ...]]) -> None:
    # _base_manager: the site-aware manager needs a request to scope by.
    endpoint_model = apps.get_model("freedom_ls_webhooks", "WebhookEndpoint")
    for endpoint in endpoint_model._base_manager.all():
        rewritten: list[str] = []
        for code in endpoint.event_types:
            for new in mapping.get(code, (code,)):
                if new not in rewritten:
                    rewritten.append(new)
        if rewritten != endpoint.event_types:
            endpoint.event_types = rewritten
            endpoint.save(update_fields=["event_types"])


def rename_forward(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    _rewrite(apps, RENAMES)


def rename_backward(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    _rewrite(apps, {new: (old,) for old, news in RENAMES.items() for new in news})


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_webhooks", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
