"""Django system checks for the mail app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate, test, and
``manage.py check``, except a check registered with ``deploy=True``, which runs
only under ``manage.py check --deploy``.

E001 — EMAIL_UPSTREAM_BACKEND resolves to the queueing backend itself, so the
       worker would re-enqueue every message instead of sending it. Runs
       everywhere, not only under ``--deploy``, because it fires wherever the
       queueing backend is selected, dev included.
E002 — EMAIL_RETRY_DELAYS, EMAIL_MAX_ATTEMPTS or EMAIL_RETRY_JITTER_RATIO
       holds a value the retry ladder cannot use. Runs everywhere.
W001 — The queueing backend is selected but the task backend cannot defer a
       task, so each retry waits for the next ``fls_run_housekeeping`` run.
       Only runs under ``--deploy``.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error, Warning, register


def _is_the_queue(dotted_path: str) -> bool:
    """Whether a backend path resolves to QueuedEmailBackend or a subclass.

    Resolved rather than string-compared so a downstream subclass counts. An
    unimportable path raises on the first send and that is Django's error to
    report, so it is treated as "not the queue" here: one id, one meaning.
    """
    from django.utils.module_loading import import_string

    from freedom_ls.mail.backends import QueuedEmailBackend

    try:
        backend = import_string(dotted_path)
    except ImportError:
        return False
    return isinstance(backend, type) and issubclass(backend, QueuedEmailBackend)


@register()
def check_email_upstream_backend_is_not_the_queue(
    **kwargs: object,
) -> list[CheckMessage]:
    """Error when the backend behind the queue is the queue.

    QueuedEmailBackend hands each message to the task queue; the worker sends it
    through EMAIL_UPSTREAM_BACKEND. Point the second at the first and every send
    enqueues a fresh copy of itself -- under the database backend the task table
    grows until the disk does not, under the immediate backend it recurses on the
    spot. No mail is delivered either way, and nothing else reports it.

    Not a --deploy check: it only fires where the queueing backend is actually
    selected, which is dev and, unless EMAIL_BACKEND overrides it, production, so
    a developer should meet this at runserver rather than at release time.
    """
    from django.conf import settings

    from freedom_ls.mail.config import config

    # Nothing to get wrong when the queue is not in use -- which includes the whole
    # test suite, where Django forces EMAIL_BACKEND to locmem.
    if not _is_the_queue(getattr(settings, "EMAIL_BACKEND", "")):
        return []

    if not _is_the_queue(config.EMAIL_UPSTREAM_BACKEND):
        return []

    return [
        Error(
            f"EMAIL_UPSTREAM_BACKEND ({config.EMAIL_UPSTREAM_BACKEND!r}) is the "
            f"queueing email backend, so the worker would re-enqueue every message "
            f"instead of sending it and no mail would ever be delivered.",
            hint=(
                "Set EMAIL_UPSTREAM_BACKEND to the backend that actually sends — "
                "django.core.mail.backends.smtp.EmailBackend, or your provider's. "
                "EMAIL_BACKEND is the one that names the queue."
            ),
            id="freedom_ls_mail.E001",
        )
    ]


@register()
def check_email_retry_settings_are_usable(
    **kwargs: object,
) -> list[CheckMessage]:
    """Error when the retry ladder's settings cannot drive a retry.

    They are first read inside the worker's failure handling, after the row is
    claimed. A value that raises there leaves the row in sending with no cause
    recorded, and only the stuck-email sweep moves it on, an hour at a time.
    """
    from freedom_ls.mail.config import config

    problems: list[str] = []
    delays = config.EMAIL_RETRY_DELAYS
    if not isinstance(delays, list) or not delays:
        problems.append("EMAIL_RETRY_DELAYS must be a non-empty list of seconds")
    elif not all(
        isinstance(delay, int) and not isinstance(delay, bool) and delay >= 0
        for delay in delays
    ):
        problems.append("every EMAIL_RETRY_DELAYS entry must be a whole number ≥ 0")
    if config.EMAIL_MAX_ATTEMPTS < 1:
        problems.append("EMAIL_MAX_ATTEMPTS must be at least 1")
    if config.EMAIL_RETRY_JITTER_RATIO < 0:
        problems.append("EMAIL_RETRY_JITTER_RATIO must not be negative")
    if not problems:
        return []
    return [
        Error(
            f"The email retry settings cannot schedule a retry: {'; '.join(problems)}.",
            hint=(
                "Leave these settings unset to use FreedomLS's defaults, or fix "
                "the values named above."
            ),
            id="freedom_ls_mail.E002",
        )
    ]


@register(deploy=True)
def check_task_backend_can_defer_email_retries(
    **kwargs: object,
) -> list[CheckMessage]:
    """Warn when the queue is in use on a task backend that cannot defer a task.

    A retry is enqueued to run after a delay. A backend that cannot defer runs it
    at once or ignores the delay, so each retry waits for the next
    ``fls_run_housekeeping`` run to be re-driven instead of running on its backoff.
    """
    from django.conf import settings
    from django.tasks import default_task_backend

    if not _is_the_queue(getattr(settings, "EMAIL_BACKEND", "")):
        return []

    if default_task_backend.supports_defer:
        return []

    return [
        Warning(
            "The task backend cannot defer tasks, so each email retry waits for "
            "the next fls_run_housekeeping run instead of running after its "
            "backoff delay.",
            hint="Use the database task backend (django_tasks_db.DatabaseBackend).",
            id="freedom_ls_mail.W001",
        )
    ]
