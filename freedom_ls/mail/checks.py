"""Django system checks for the mail app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate, test, and
``manage.py check``, except a check registered with ``deploy=True``, which runs
only under ``manage.py check --deploy``.

E001 — EMAIL_UPSTREAM_BACKEND resolves to the queueing backend itself, so the
       worker would re-enqueue every message instead of sending it. Runs
       everywhere, not only under ``--deploy``, because it fires wherever the
       queueing backend is selected, dev included.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error, register


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
    selected, which is dev by default and production once a deployment opts in, so
    a developer should meet this at runserver rather than at release time.
    """
    from django.conf import settings
    from django.utils.module_loading import import_string

    from freedom_ls.mail.backends import QueuedEmailBackend
    from freedom_ls.mail.config import config

    def is_the_queue(dotted_path: str) -> bool:
        """Whether a backend path resolves to QueuedEmailBackend or a subclass.

        Resolved rather than string-compared so a downstream subclass counts. An
        unimportable path raises on the first send and that is Django's error to
        report, so it is treated as "not the queue" here: one id, one meaning.
        """
        try:
            backend = import_string(dotted_path)
        except ImportError:
            return False
        return isinstance(backend, type) and issubclass(backend, QueuedEmailBackend)

    # Nothing to get wrong when the queue is not in use -- which includes the whole
    # test suite, where Django forces EMAIL_BACKEND to locmem.
    if not is_the_queue(getattr(settings, "EMAIL_BACKEND", "")):
        return []

    if not is_the_queue(config.EMAIL_UPSTREAM_BACKEND):
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
