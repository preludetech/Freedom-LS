# Idea: A landing page component kit

## What

A set of cotton components and page layouts for building marketing landing pages out of FLS's theme
roles: sections and section headings, hero variants (split, banner, image), card grids, split
sections, feature rows and cards, step timelines, FAQ and objection lists, trust lists, a form card,
a closing call-to-action band, and a call-to-action carrier that a view passes to a layout so the
same buttons render in the hero and in the closing band. Every colour comes from a theme role
(primary, secondary, accent), never a brand value, so the kit looks right under any theme.

## Why

A concrete project needs landing pages for its courses and campaigns, and FLS gives it nothing to
build them from, so each project writes its own kit. First-Class-LMS has written a complete one,
token-driven and tested on structure, with almost no brand content in it. A second project would
write the same thing again.

## Reference implementation

First-Class-LMS: `apps/landing_pages/templates/cotton/lp/` (the components),
`apps/landing_pages/templates/landing_pages/layouts/` (the layouts),
`apps/landing_pages/templatetags/lp_tags.py` (the class maps: every prop-dependent Tailwind class is
a whole literal in Python, because Tailwind v4 reads source as text and an interpolated class
generates no CSS) and `apps/landing_pages/cta.py` (the `Cta` carrier). Left out on purpose:
`apps/landing_pages/price.py`, the `price` and `price-card` components and `festive.py`, which hold
rand-denominated, project-specific data; a price component would need a currency setting first. The
project's own page views and page templates stay in the project. The project would delete the kit
and keep its pages.

## Open question

Whether FLS wants to own marketing pages at all, or whether this belongs in a separate optional app
a project installs only when it builds landing pages. That decision comes before a spec.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-11-08).
