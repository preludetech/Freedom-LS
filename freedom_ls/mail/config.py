from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class MailSettings(AppSettings):
    EMAIL_UPSTREAM_BACKEND: str
    EMAIL_MAX_ATTEMPTS: int
    EMAIL_RETRY_DELAYS: list[int]
    EMAIL_RETRY_JITTER_RATIO: float
    HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS: int
    HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE: int
    HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS: int

    declared_settings = {
        # The backend the worker actually sends through, once QueuedEmailBackend has
        # taken the message off the request. FLS's own setting, not one of Django's:
        # Read only where EMAIL_BACKEND names the queue: that setting names the queue,
        # this one names what is behind it. SMTP by default because a deployment that
        # has opted into queueing is sending real mail -- dev included, where Mailpit
        # is SMTP on localhost. Pointing this back at the queueing backend would
        # re-enqueue every message forever, which E001 catches.
        "EMAIL_UPSTREAM_BACKEND": Setting(
            default="django.core.mail.backends.smtp.EmailBackend"
        ),
        # Total sends tried for one message, the first included, before it is
        # dead-lettered.
        "EMAIL_MAX_ATTEMPTS": Setting(default=6),
        # Seconds to wait after each failed attempt, in order. A failure past the
        # end of the list reuses the last entry. The full ladder must finish well
        # inside the window after which finished task results are pruned.
        "EMAIL_RETRY_DELAYS": Setting(default=[60, 300, 900, 1800, 3600]),
        # Upper bound on the random extra wait added to each delay, as a fraction
        # of that delay.
        "EMAIL_RETRY_JITTER_RATIO": Setting(default=0.2),
        # How far past its due time a pending or failed row must be before
        # housekeeping enqueues it again. Longer than the worker's usual pickup
        # delay, so a row whose task is merely queued is not enqueued twice.
        "HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS": Setting(default=300),
        # Most rows one housekeeping run enqueues, oldest first, so a long
        # outage cannot flood the queue in one run.
        "HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE": Setting(default=500),
        # How long a row may stay in sending before housekeeping decides its
        # worker died and sends it again. Keep it at or above
        # WORKER_MAX_TASK_SECONDS plus WORKER_HEARTBEAT_MAX_AGE_SECONDS plus one
        # watchdog poll, or a send still in flight is recovered out from under
        # its worker and the message goes out twice.
        "HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS": Setting(default=3600),
    }


config = MailSettings()
