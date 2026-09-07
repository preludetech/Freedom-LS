"""Thin, pure module of mail-settings primitives consumed by
config/settings_prod.py.

Flat constants and small functions only. Only stdlib at module top — nothing that
touches the app registry — so this is safe to import at settings-load time before
the registry is ready (matching freedom_ls/deployment/settings_defaults.py).
Unit-tested in freedom_ls/mail/tests/test_settings_defaults.py.
"""

from __future__ import annotations

# Socket timeout for each SMTP operation, in seconds. Unset, smtplib inherits Python's
# global default of None and a black-holed connection hangs forever -- holding the
# request open when mail is sent in the request, and stalling every other queued task
# behind it when a deployment has opted into QueuedEmailBackend. Ten seconds absorbs a
# slow TLS handshake without failing legitimate sends, and stays far inside
# WORKER_MAX_TASK_SECONDS.
EMAIL_TIMEOUT_SECONDS: int = 10
