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
  design's tints, tiles, weights and text treatments onto FLS equivalents, so the plan applied the
  rule loosely and the result came out flat. One earlier spec produced exactly this mapping without
  being asked to (`spec_dd/3. done/2026-09-08_17:31_better-form-start-page/research_design_source.md`).
  No command requires it.
- **Claude only ever read the design as code.** No step turned it into a picture. Code alone
  misleads: the design's CSS sets the day headings to 12px, but a more specific rule overrides it
  and the rendered headings are 18px. `research_design_render_spike.md` has the details.
- **Scope decisions had no single home.** The same exclusions (the Preferences gear, "Show older",
  the message item) are restated in `design.md`'s coverage table, the spec's Scope, the plan's
  Design section and this idea. None records the question asked or which later spec should revisit
  it.

Evidence and per-step tool grants are in `research_design_fidelity_forensics.md`. Established
practice and the ranked options are in `research_design_fidelity_practices.md`.

## Part 1: carry the design through SDD

### Registration syncs the design, screenshots it and settles its scope

`/sdd:register_design` does three new things after writing `design.md`. Everything it produces
lives in the directory the design is registered on: the spec itself, or a cut effort's parent.
That parent never moves as its children go from `1. next` to `3. done`, so paths stay valid.

1. **Sync the design's source.** Registration reads every text file the design is built from
   through `DesignSync` and writes each one, whole and unedited, into a `design_source/` directory
   that mirrors the project's paths. The user chose this over asking them to click Export in
   Claude Design each time. It's automatic, but DesignSync can't carry binaries (the logo came back
   cut off at the 256 KiB cap), so fonts and images are left out and renders use fallbacks. That's
   fine for FLS, which uses neither. The source is committed: implementation happens in a
   worktree, and a worktree only has what's in git. `research_claude_design_export.md` covers the
   alternatives. `research_design_render_spike.md` covers the cost of copying through the model.
2. **Screenshot every artboard.** A subagent serves `design_source/` on a local static server,
   loads it in Playwright with a flat stand-in for Claude Design's pan/zoom canvas, and screenshots
   each artboard by selector into `design_screenshots/`. The spike proved this end to end in
   about 40 seconds, and the stand-in's source is in `research_design_render_spike.md`. The
   screenshots are committed, and they are what every later comparison uses. They must not go in
   `screenshots/`, which `/fls-dev:do_qa` wipes on every run.
3. **Ask the scope questions and save the answers.** The designer didn't know FLS, so the design
   draws things nobody has asked for. Registration finds candidates, meaning drawn elements that
   the design brief, the owning spec's idea and FLS's existing code don't account for. It asks the
   user about each, for example "Build the notification Preferences gear?", with the answers
   build, leave out, or later with a named spec. It records each answer in `design_scope.md`,
   one row per drawn element: the element, its design section, the question, the answer, which
   step decided it, and the date. The row shape and the rules for finding candidates are in
   `research_design_scope_and_sync_flow.md`.

`design_scope.md` is the one home for scope decisions. Specs and plans cite it rather than
restating exclusions. A later spec that reverses a decision edits the row. It never adds a
second one. For a cut effort, registration can only settle what applies to the whole effort.
`/sdd:spec_from_idea` asks about anything still open for its own screens when the child spec
starts, and adds the answers to the same file. Re-registering after the designer changes the design
re-syncs, re-screenshots, and reconciles `design_scope.md`: existing answers stay, new elements
get asked about, and removed elements are marked as removed rather than deleted.

### Every later step builds and checks against it

- **The plan transcribes the design for each screen and state.** Using `design_source/` and
  `design_screenshots/`, it lists the elements, their order and hierarchy, the copy, and which
  controls appear in which state. It leaves out whatever `design_scope.md` says to. It also gives
  a token mapping: which FLS token, component or icon expresses each drawn visual treatment, and
  what is lost where FLS has no equivalent. No new theme tokens are added to match a design.
- **Implementation checks against the design.** Batch briefs point at the plan's transcription,
  the screenshots and `design_scope.md`, which is how a batch knows not to build a control it can
  see in the source. After each slice that builds a designed screen, the depth-0 orchestrator
  compares the page with the design screenshots before moving on.
- **QA checks conformance with the design.** For every test that maps to a design state,
  `/fls-dev:do_qa` puts its own screenshot next to the matching design screenshot and checks the
  plan's per-state checklist. It does not pixel-diff, because FLS's theme deliberately differs
  from the design's. An element the design draws but the build lacks is correct if
  `design_scope.md` says to leave it out. Any other conformance miss, including an element with
  no scope row, goes to a human as a todo item and is never auto-fixed.

## Part 2: make the notifications UI match the design

Start by re-registering `spec_dd/1. next/user-communication/` with the new registration, so
it gets `design_source/`, `design_screenshots/` and `design_scope.md`. The scope answers for
sections 1 and 2 are already settled and seed that file (see the last paragraph below). Until
then, `design_screenshots/` next to this idea holds the spike's renders of sections 1 and 2, and
`design_snapshot_notifications.md` holds the matching source excerpts.

The scope is every surface `user-communication-1-notifications-core` built. That means the bell
and badge, the panel (the desktop popover and the full-width sheet at 375px) and the notification
centre (populated, all read, empty, Unread-filter empty, long list, 375px). Match the design's
layout, density, hierarchy, component shapes and every drawn state, expressed through FLS's
tokens, cotton components and `c-icon`. The gap between the design and the build is listed screen
by screen in `research_design_vs_built_gap.md`.

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
  separating ring, two-line clamping of long messages, the All/Unread filter looking like the
  design's segmented control (it stays a pair of filter links), and the all-read banner's icon.

The done spec deliberately left some drawn elements out, and they stay out: the Preferences gear
and button (no preferences page exists yet), the "about" line on centre rows, "Show older
notifications" (the centre keeps its pagination), `role="dialog"`/`aria-haspopup="dialog"` (the
panel is a disclosure and doesn't trap focus), and the message item. The behaviour of the built
surfaces doesn't change.
