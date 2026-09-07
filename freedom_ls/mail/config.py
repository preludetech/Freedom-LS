from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class MailSettings(AppSettings):
    EMAIL_UPSTREAM_BACKEND: str

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
    }


config = MailSettings()
