# FLS first_class theme ("Modern Altitude")

- **Name:** first_class
- **Version:** 1.0 (Phase 2 — Tier-1 canary)
- **Overrides:** Tier 1 only — ships `theme.css` with brand colour, surface,
  status, type and radius overrides. No template or component-class overrides
  (Tier 2 lands in Phase 3, Tier 3 in Phase 4).
- **Brand reference:**
  `spec_dd/.../themable-implementations-master-decomposed-into-phases/first-class-theme.md`.

This theme is the canary that proves the Tier-1 promise: a downstream project
can rebrand FLS by writing a single `theme.css` and pointing `FLS_THEME` at
their theme directory — no template edits, no Python.
