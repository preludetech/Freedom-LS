"""The queued send: what the background worker runs for each message.

``fls_run_worker`` rebuilds the message and sends it through
EMAIL_UPSTREAM_BACKEND, which is what actually talks to the mail server. Dev
settings select the queueing backend; production sends in the request unless a
deployment opts in, because choosing it commits that deployment to running a
worker. Without one the mail is accepted and never sent.
"""

from __future__ import annotations

from django.core.mail import get_connection
from django.tasks import task

from freedom_ls.mail.config import config
from freedom_ls.mail.encoding import set_8bit_encoding
from freedom_ls.mail.serialisation import SerialisedMessage, deserialise_message

# Ahead of the default 0 that webhook delivery and report rendering enqueue at.
# django-tasks-db orders its queue by priority descending, so a person waiting on
# a password reset is not stuck behind a cohort report that happened to be asked
# for first. It does not preempt a report already running -- see the deployment
# docs for the separate-worker escape hatch.
EMAIL_TASK_PRIORITY = 10


def send_serialised_email(payload: SerialisedMessage) -> None:
    """Rebuild a queued message and send it through the upstream backend.

    Failures propagate rather than being swallowed. The worker marks the task
    result FAILED and the task framework's own task_finished receiver logs that
    at ERROR with the traceback attached, which reaches the console handler and,
    where a DSN is configured, Sentry. Swallowing here would instead mark the
    task successful and drop the mail with no signal anywhere.
    """
    message = deserialise_message(payload)
    set_8bit_encoding(message)
    connection = get_connection(backend=config.EMAIL_UPSTREAM_BACKEND)
    connection.send_messages([message])


@task(priority=EMAIL_TASK_PRIORITY)
def _send_email_task(payload: SerialisedMessage) -> None:
    send_serialised_email(payload)
