"""Deterministic per-course accent role.

Hashes a course title to one of a curated palette of theme-token roles.
The mapping is **stable across processes** because we use SHA-256, not
Python's randomised :func:`hash` builtin. Reordering :data:`PALETTE` would
remap every existing course — never reorder.
"""

from __future__ import annotations

import hashlib

# Order is fixed. Reordering would remap every existing course's accent.
PALETTE: tuple[str, ...] = ("primary", "secondary", "accent", "info", "success")


def course_accent_role(title: str) -> str:
    """Return one of :data:`PALETTE` for the given course title.

    Pure function; deterministic across processes and platforms.
    """
    digest = hashlib.sha256(title.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % len(PALETTE)
    return PALETTE[bucket]
