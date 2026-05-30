"""Per-course accent palette.

The palette is a **separate, themeable colour series** — not the semantic UI
role tokens (``primary``/``secondary``/…) — so card vibrancy can be tuned
without touching button/badge colours. Each slot key maps to
``--fls-course-accent-<slot>`` tokens in the theme.

Slot assignment is persisted on ``Course.accent_slot`` (chosen at row creation
time from the per-site course count modulo the palette size) so a course
keeps the same colour everywhere it appears and distribution stays balanced
across the catalogue. Reordering :data:`PALETTE` would remap every existing
course — never reorder.
"""

from __future__ import annotations

# Order is fixed. Reordering would remap every existing course's accent.
# Neutral slot keys (not role names) — the resolved colours live in the
# `--fls-course-accent-<slot>` token series, keeping cards decoupled from the
# semantic UI roles. Each slot must have matching `--fls-course-accent-<slot>*`
# tokens in the theme and `.course-accent-<slot>` / `.course-progress-<slot>`
# component classes; the three stay in lockstep.
PALETTE: tuple[str, ...] = ("1", "2", "3", "4", "5")
