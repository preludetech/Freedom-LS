# Panel framework components

Spec 4 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The cotton components the mockups are made of, built once in `panel_framework` on FLS role tokens so that specs 6 to 10 assemble screens instead of styling them. Each component owns its own styling, can be overridden by a theme at the same loader path, and works in the default theme and in dark mode.

## Why

The mockups in `../educator-interface-full-polish/Educator LMS Interface Design/` were drawn for the first-class brand with Phosphor icons and their own CSS. They are the design: the layouts, densities and component shapes are what we build to. But nothing in them is FLS markup, and if each feature spec styles its own cards and badges the interface will look like four people built it. The wayfinder pass concluded the mockups needed no further design work; what they need is an FLS implementation.

## What is settled

**Inventory.** Read from the mockups, screen by screen. At least:

- Page header with title, subtitle, status badge and an action group (mockup 03, 05).
- Stat tile with value, label and optional delta or sub-line, in a responsive row (01, M01).
- Status badge with a fixed vocabulary mapped to semantic tokens. The vocabulary comes from the domain, not the mockup: active, inactive, pending, complete, in progress, stalled. Spec 10 decides how "stalled" is computed; this spec only styles it.
- Avatar chip with initials and name, optionally with email or role under it (02, 05).
- Attention list: a row per learner with a reason, a badge and one action (01, M01).
- Progress bar with percentage and optional label (01, 03).
- Section card with a heading, optional description, a body and an actions footer, replacing the framework's panel container styling where they overlap.
- Definition list for label and value pairs, responsive (03 "Learner details").
- Toolbar with search, filter chips and primary actions (02).
- Empty state with an icon, a sentence and one action.
- Tab bar styling shared with the framework's tab container (03, 05).
- Skeleton blocks for loading states used by spec 3.

**Tokens and icons.** FLS role tokens only, per `fls-dev:frontend-styling`. `c-icon` only, per `fls-dev:icon-usage`; pick the closest icons in the existing set and do not add Phosphor. Radius, spacing and shadow follow the existing FLS scale, not the first-class README.

**Where.** Components live under `freedom_ls/panel_framework/templates/cotton/`. Cotton's namespace is flat, so names are prefixed to avoid colliding with `base` (for example `panel-stat-tile`, or a namespace decided in the spec). Any component that turns out to be general enough for the learner interface is noted for a later move, not moved now.

**Styling rules.** Utilities on the markup; an `@layer components` block inside the component only where no utility exists; nothing in `tailwind.components.css`. Every markup change sets `requires_tailwind_rebuild` in the upgrade notes.

**A reference page.** A dev-only page (behind `DEBUG`, or in the framework's test templates) rendering every component in every state, so the Playwright visual check in spec 12 has something to look at and so a downstream developer can see the kit.

**Accessibility.** Badges carry text, not just colour. Stat tiles are readable by a screen reader as label then value. The attention list is a list.

## Open until the spec

- The exact status vocabulary and which token each maps to. Coordinate with spec 10, which computes the statuses, and with the `brand-guidelines` skill.
- Whether the section card replaces the framework's panel container outright or wraps it.

## Out of scope

- Charts. If spec 10 wants a chart, it uses the `dataviz` skill then.
- Changes to `base` components. If one needs changing, note it and leave it.
- Marketing or learner-facing pages.

## Resources

- `../educator-interface-full-polish/Educator LMS Interface Design/`, all screens. The `_ds/README.md` in there describes the first-class system and is context, not instruction.
- `claude_plugins/fls-dev/resources/templates_and_cotton.md`, with `cotton/flashcard.html` as the reference implementation.
- Skills: `brand-guidelines`, `fls-dev:frontend-styling`, `fls-dev:icon-usage`, `fls-dev:template`, `ds:frontend-styling`.
