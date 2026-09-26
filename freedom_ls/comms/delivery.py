"""The notification delivery-backend seam.

A downstream or a later spec names a subclass in NOTIFICATION_DELIVERY_BACKENDS
to act on a stored notification (email, for instance). The base class carries
no behaviour, in the manner of course_access.backends.CourseAccessBackend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freedom_ls.comms.models import Notification


class NotificationDeliveryBackend:
    def deliver(self, notification: Notification) -> None:
        raise NotImplementedError
