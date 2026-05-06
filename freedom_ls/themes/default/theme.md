# FLS default theme

- **Name:** default
- **Version:** 1.0 (Phase 1 — token resolver + finalised role tokens)
- **Overrides:** Tier 1 only — ships `theme.css` with the full role-token contract (brand, status, surface, border, muted, focus-ring, plus shape and type tokens). No template or component overrides; those defaults stay in the main FLS project (`tailwind.components.css`, `freedom_ls/base/templates/`).

This theme is the always-on baseline imported by `tailwind.input.css`. Downstream themes inherit every value declared here and only override what they want to change.
