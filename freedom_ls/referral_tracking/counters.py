"""The daily first-touch tally and the attribution-key digest it is keyed on."""

from __future__ import annotations

import hashlib

KEY_SEPARATOR = "\x1f"
OVERFLOW_SENTINEL = "\x00overflow"


def attribution_key_hash(*values: str) -> str:
    return hashlib.sha256(KEY_SEPARATOR.join(values).encode("utf-8")).hexdigest()
