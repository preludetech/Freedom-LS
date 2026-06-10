# FLS first_class theme ("Modern Altitude")

- **Name:** first_class
- **Version:** 1.1 (Phase 3 — Tier-1 + Tier-2)
- **Overrides:** Tier 1 + Tier 2 — ships `theme.css` with brand colour,
  surface, status, type and radius token redeclares (`@theme`), plus
  component-class overrides (`@layer components`, `@layer base`,
  `@layer utilities`, `@theme inline`) that apply the "Modern Altitude"
  chunkier shapes, pastel chip tints, frosted-glass header, and zero-padded
  TOC counters. No template overrides (Tier 3); all template files stay in the
  main FLS project.
- **Brand reference:**
  `spec_dd/.../themable-implementations-master-decomposed-into-phases/first-class-theme.md`.

This theme is the canary that proves the Tier-1 + Tier-2 promise: a downstream
project can rebrand FLS by writing a single `theme.css` and pointing
`FLS_THEME` at their theme directory — no template edits, no Python.
