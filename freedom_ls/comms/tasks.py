"""Background tasks for comms.

Each configured delivery backend gets its own task per stored notification, so
one backend failing affects neither the row nor another backend's task.
"""

from __future__ import annotations

from django.tasks import task
from django.utils.module_loading import import_string

from freedom_ls.comms.models import Notification


@task()
def deliver_notification(backend_path: str, notification_id: str, site_id: int) -> None:
    # _base_manager, filtered explicitly by site_id: a task has no request
    # context for SiteAwareManager to read, the same reason
    # webhooks.events.dispatch_event filters WebhookEvent explicitly.
    notification = (
        Notification._base_manager.select_related("user")
        .filter(site_id=site_id)
        .get(pk=notification_id)
    )
    import_string(backend_path)().deliver(notification)
