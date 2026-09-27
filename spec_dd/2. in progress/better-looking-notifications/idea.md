# Better-looking notifications

`user-communication-1-notifications-core` shipped the bell, the panel and the notification centre.
It was meant to follow the registered Claude Design design (`spec_dd/1. next/user-communication/design.md`,
sections 1 and 2 of `User Communication.html`), and it doesn't. The structure is right, but the
screens look nothing like the design.

This spec does two things, in this order:

1. Fix how SDD carries a design through to the built UI, so this doesn't happen again.
2. Rebuild the notifications UI to match the design, using the fixed process. The rebuild tests
   whether the process fix works.

## What went wrong

Claude could read the design. `/sdd:spec_from_idea` and `/sdd:plan_from_spec` run at depth 0,
where `DesignSync` works, and both read it: the spec and plan quote component names, ARIA
attributes and copy that only the design's files contain. It was registered before the spec
started. The chain broke after the plan:

- **Nothing downstream could see the design.** The plan names the screens and states it builds,
  but it doesn't transcribe what the design draws for them. `/sdd:implement_plan` runs batches in
  subagents that can't call `DesignSync`, and its brief never mentions the design, so the batches
  built from the plan's prose.
- **Nothing ever compared the result with the design.** `/fls-dev:do_qa` and the `3. frontend_qa.md`
  it runs are entirely behavioural. Two QA passes fixed three bugs, none of them about appearance.
- **No step translated the design's styling into FLS's tokens.** FLS's tokens, cotton components
  and `c-icon` should win over the design's styling, and that rule is right. But no step maps the
  design's tints, tiles, weights and text treatments onto FLS equivalents, so the plan applied the rule
  loosely and the result came out flat. One earlier spec produced exactly this mapping without
  being asked to (`spec_dd/3. done/2026-09-08_17:31_better-form-start-page/research_design_source.md`).
  No command requires it.
- **Claude only ever reads the design as code.** `DesignSync` returns JSX and CSS. No step renders
  the design into a picture that Claude or the reviewer can put next to a screenshot of the build.

Evidence and per-step tool grants are in `research_design_fidelity_forensics.md`. Established
practice and the ranked options are in `research_design_fidelity_practices.md`.

## Part 1: carry the design through SDD

The spec decides where each change lives. The direction is settled:

- **Save the design into the spec directory.** When the spec or plan step reads the design, it
  writes the files covering this spec's screens (per `design.md`'s coverage table) next to the
  spec. Every later step and subagent can then `Read` the design without `DesignSync`.
  `design_snapshot_notifications.md` is a hand-made example of this for the current spec.
- **The plan transcribes the design for each screen and state.** It lists the elements, their
  order and hierarchy, the copy, and which controls appear in which state. It also gives a token
  mapping: which FLS token, component or icon expresses each drawn visual treatment, and what is
  lost where FLS has no equivalent. No new theme tokens are added to match a design.
- **Implementation checks against the design.** Batch briefs point at the saved design. After
  each slice that builds a designed screen, the depth-0 orchestrator compares the page with the
  design before moving on.
- **QA checks conformance with the design.** For every test that maps to a design state,
  `/fls-dev:do_qa` checks the screenshots it has already taken against the plan's per-state
  checklist. It does not pixel-diff, because FLS's theme deliberately differs from the design's.
  Conformance misses go to a human as todo items. They are not auto-fixed.
- **Try rendering the design locally.** Save the design's HTML and JSX, serve them with a local
  static server and screenshot the artboards with Playwright. This would give Claude and the
  reviewer an actual picture to compare against. It is unproven (CDN access, the 256 KiB
  `get_file` cap), so the spec treats it as a one-screen spike. If it works it becomes a step. If
  it doesn't, the checklist carries the comparison. Rendering a locally saved copy doesn't touch
  the rule against opening the claude.ai link.

## Part 2: make the notifications UI match the design

The scope is every surface `user-communication-1-notifications-core` built. That means the bell and badge,
the panel (the desktop popover and the full-width sheet at 375px) and the notification centre
(populated, all read, empty, Unread-filter empty, long list, 375px). Match the design's layout,
density, hierarchy, component shapes and every drawn state, expressed through FLS's tokens,
cotton components and `c-icon`. The design is in `design_snapshot_notifications.md`. The gap
between it and the build is listed screen by screen in `research_design_vs_built_gap.md`.

What the user called out, and what the design draws for each:

- **Rows are inbox items, not links.** Row titles are currently blue and underlined in the panel
  and the centre, and so are the All/Unread filter pills. The design draws them in the normal text
  colour with no underline. The whole row is the click target and the cursor is a pointer, but it
  still behaves as a real link. The per-row Mark read button stays clickable on top of it.
- **Unread rows are shaded.** In the panel and the centre, unread rows are tinted as well as bold,
  with the dot and label.
- **Category icons sit in tiles.** Each row's icon sits in a small rounded tile in its category's
  colour, as the design draws it. The colour is set per notification category.
- **Mark all as read** is a ghost button in the design's colour with a double-tick icon, in the
  panel and on the centre. FLS's default Heroicons set has no double tick. Pick the glyph and give
  it a semantic `c-icon` name. Never hand-draw an icon: use a semantic icon.
- **Everything else in the gap research gets the same treatment**: the day headings, the badge's
  separating ring, two-line clamping of long messages, the All/Unread filter looking like the design's segmented control (it stays a pair of filter
  links),
  and the all-read banner's icon.

The done spec deliberately left some drawn elements out, and they stay out: the Preferences gear
and button (no preferences page exists yet), the "about" line on centre rows, "Show older
notifications" (the centre keeps its pagination), `role="dialog"`/`aria-haspopup="dialog"` (the
panel is a disclosure and doesn't trap focus), and the message item. The behaviour of the built
surfaces doesn't change.
