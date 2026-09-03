"""Force 8bit transfer encoding on outgoing mail.

Lives in ``base`` because both the allauth adapter (``accounts``) and the
queueing email backend (``deployment``) apply it, and ``base`` is the only app
either of those may import without inverting a dependency.
"""

from __future__ import annotations

import email.policy
from email.mime.base import MIMEBase

from django.core.mail import EmailMessage


def set_8bit_encoding(msg: EmailMessage) -> None:
    """Set Content-Transfer-Encoding to 8bit on an EmailMessage.

    Prevents Python's email library from using quoted-printable encoding,
    which wraps lines at 76 characters and corrupts long URLs.

    Patches the bound ``message`` attribute rather than the class, so it applies
    to this message alone. Serialising a message to primitives drops the patch,
    which is why it has to be reapplied after a queued message is rebuilt.
    """
    original_message = msg.message

    def patched_message(
        *, policy: email.policy.Policy = email.policy.default
    ) -> MIMEBase:
        mime_msg: MIMEBase = original_message(policy=policy)
        for part in mime_msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                decoded_payload = part.get_payload(decode=True)
                if isinstance(decoded_payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    del part["Content-Transfer-Encoding"]
                    part["Content-Transfer-Encoding"] = "8bit"
                    part.set_payload(decoded_payload.decode(charset), charset)
                    # set_payload with charset re-encodes, so override again
                    del part["Content-Transfer-Encoding"]
                    part["Content-Transfer-Encoding"] = "8bit"
        return mime_msg

    object.__setattr__(msg, "message", patched_message)
