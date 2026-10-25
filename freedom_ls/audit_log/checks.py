"""Django system checks for the audit_log app.

E001 — An AUDIT_LOG_EXTRA_ACTIONS code that is already an FLS action code, or
       is not a lower-case `noun.verb` string.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register

from freedom_ls.audit_log.actions import FLS_AUDIT_ACTIONS
from freedom_ls.audit_log.config import config

_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


@register()
def check_extra_audit_actions(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    fls_codes = {action.code for action in FLS_AUDIT_ACTIONS}
    errors: list[CheckMessage] = []
    for code in config.AUDIT_LOG_EXTRA_ACTIONS:
        if code in fls_codes:
            problem = "is already an FLS audit action code"
        elif not _CODE_PATTERN.match(code):
            problem = "is not a lower-case noun.verb code"
        else:
            continue
        errors.append(
            Error(
                f"AUDIT_LOG_EXTRA_ACTIONS code {code!r} {problem}.",
                hint="Use a code like 'invoice.sent' that no FLS action uses.",
                id="freedom_ls_audit_log.E001",
            )
        )
    return errors
