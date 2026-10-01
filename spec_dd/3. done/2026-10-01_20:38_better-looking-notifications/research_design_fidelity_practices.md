# Research: practices that make AI-built UI faithful to a design

## What actually happened in the pipeline (read directly)

Traced the four commands and the one worked example (`spec_dd/1. next/user-communication/design.md`):

- `register_design.md` writes `design.md`: link, entry file, "made of" file list, a per-screen/state
  coverage table, and a "how to treat it" policy (build faithfully, but FLS's theme tokens/cotton
  components/`c-icon` win over the design's colours/fonts). This is good policy prose, and it is the
  **only** artifact that survives from the design into the repo. Nothing from the design's actual
  JSX/CSS ever gets written to disk.
- `spec_from_idea.md` and `plan_from_spec.md` (Step 1) both re-read the design live through
  `DesignSync`, at depth 0, and `plan_from_spec.md` already asks the plan to "name, per slice, the
  design screens and states it builds and the `design.md` path" — so the plan does carry a pointer,
  not just prose paraphrase. But naming a screen ("populated, empty, long list") is not the same as
  carrying what the design actually drew for it (exact copy, element order, which controls appear in
  which state) into a form a later, DesignSync-less step can read.
- `implement_plan.md` batches the plan into `general-purpose` subagents, one per vertical slice. These
  subagents have **no `DesignSync`** (only depth-0 sessions reliably have it, per your brief) and no
  Playwright MCP either — just `Read/Glob/Grep/Write/Edit/Bash/Skill`. Whatever the plan's prose says
  about a screen is the *entire* design signal an implementer subagent gets. If the plan's per-slice
  "design screens and states" line is a short pointer rather than a transcription, the implementer is
  building from memory of what depth-0 saw minutes/hours earlier in a different context window, filtered
  through however faithfully the plan's prose captured it.
- `claude_plugins/fls-dev/commands/do_qa.md` (1200+ lines) is thorough on functional QA — smoke gate,
  desktop/mobile/tablet matrix, bug triage, auto-fix loop — but **never mentions `design.md`, artboards,
  or comparing a screenshot to the design at all**. QA screenshots (Step 7-9) are compared only against
  the test plan's prose expectations ("what you expect to see"), which itself was written by
  `plan_from_spec.md` without necessarily transcribing the design's visual detail. So there is no point
  in the whole pipeline, currently, where a rendered page is put next to what the design actually drew.

This is the concrete mechanism behind "came out plainer than the design": the design's structure and
density live only in the depth-0 session's transient read of `DesignSync`, get compressed into however
much of it the plan's prose captured, and every downstream consumer (implementer subagents, QA) works
from that compression, not from the design.

## Recommendations, ranked by leverage

Each is labelled **established** (a documented practice from Anthropic or the wider design-to-code
literature) or **inference** (my reasoning about this repo's specific pipeline, applying an established
principle to it).

### 1. Persist a verbatim design extract into the spec directory — highest leverage

**What:** When `register_design.md` (or `plan_from_spec.md` Step 1, which already reads the design)
reads the design through `DesignSync`, also write what it read to disk:
`<spec-dir>/design_extract/<file-name>` — the raw `get_file` output for the entry file and every file
that covers *this spec's* screens (per the coverage table), plus a short
`design_extract/README.md` mapping screen/state → which saved file/component holds it. This makes the
design readable with a plain `Read` by any later step or subagent, permanently, without `DesignSync`.

**Where exactly:** `register_design.md` Step 3, right after building the coverage table — for each row
whose "Built by" is a real spec (not `none (out of scope)`), also copy the file(s) that draw that
screen into that spec's future `design_extract/`. Since `register_design.md` runs before child specs
necessarily exist (cut-effort case), do it lazily instead in `plan_from_spec.md` Step 1: the depth-0
plan-writer already reads the design live, so add "write `<spec-dir>/design_extract/`" there as a
concrete sub-step, scoped to the screens this spec's coverage-table rows name.

**Rationale (established):** this is the same principle as Claude Code's own guidance to give rich
context — "reference files with `@`... paste images... give URLs" — rather than a paraphrase, and the
Superdesign write-up's core diagnosis: "Claude's vision is genuinely good at reading a screenshot and
reproducing its structure, spacing, and type pairings" *if it's given the reference*, not a description
of it. Applying that to subagents-without-DesignSync is inference, but it's the direct fix for the
concrete architectural gap found above.

**Cost:** low. One extra write per registration/plan run, bounded by the screens actually in scope
(the coverage table already exists to bound it). Respects the existing 256 KiB per-file `get_file` cap
— a file that hits the cap should be flagged, not silently truncated (see recommendation 5's caveat).

### 2. A "Design conformance" section in the plan, per slice — strengthens what already half-exists

**What:** `plan_from_spec.md` Step 1 already requires naming, per slice, "the design screens and states
it builds and the `design.md` path." Strengthen this into an explicit, transcribed checklist per
screen/state, written into `2. plan.md` itself (not just a pointer): what elements the design draws in
that state, their order/hierarchy, the exact copy strings, and which controls appear only in which
state (e.g. "populated: shows the 'Mark all read' link; empty: does not"). Explicitly separate this from
styling: the checklist is structure/copy/state-presence only, never colour/font/spacing values, per
`design.md`'s existing "how to treat it" rule.

**Where exactly:** `plan_from_spec.md` Step 1 (the paragraph that already says to name screens/states) —
extend it to say the plan transcribes structural detail, not just names, per slice; Step 3's "shape"
guidance for slices should reference `design_extract/` (recommendation 1) as the source to transcribe
from, so the plan-writer is reading the saved file, not re-querying `DesignSync` from a stale mental
model.

**Rationale:** this is what makes the design survive into `implement_plan.md`'s batch subagents, which
have no `DesignSync` and (per the current plan format) only a screen-name pointer. A checklist an
implementer can literally tick off is cheaper to act on precisely than a paraphrase of "looks like the
mockup." **Inference** — applies the established "give a concrete, checkable target, not an adjective"
principle (Claude Code docs: "give Claude a check it can run"; Superdesign: "trade adjectives for
constraints") to this pipeline's plan format specifically.

**Cost:** low-medium. Adds length to the plan (offset by the writing standard's cut-list discipline);
requires the plan-writer to actually read `design_extract/` per slice rather than skimming the coverage
table once.

### 3. A design-conformance pass in QA, checklist-based, not pixel-diff

**What:** Add a step to `do_qa.md` — after Step 7 (desktop) and mirrored at Step 8 (mobile) where the
test plan's case maps to a design screen/state — that, for each such test, opens the plan's Design
Conformance checklist (recommendation 2) for that screen/state and confirms each item against what was
actually rendered (Step 7 already takes screenshots; this reuses them). Record a `design_conformance`
scratch record analogous to the existing `test` record, and surface unmet items in the report as a
distinct category from functional bugs (a conformance gap is not necessarily a "bug" needing the
bugfixer's green lane — Step 13's triage gate already requires "no product or UX decision," and a
conformance miss is often exactly a judgement call, so route it to the red lane / a todo item by
default rather than auto-fixing).

**Why not pixel-diff (Playwright `toHaveScreenshot` + pixelmatch):** established critique — pixelmatch
does fast, deterministic pixel comparison but "can't distinguish between a meaningful layout change and
a harmless anti-aliasing difference," and needs a stored baseline image of the *correct* render to diff
against. Here the "correct" render is a different theme (FLS's tokens) than the artboard (the design's
own colours/fonts), so a pixel/colour diff between the design's PNG and FLS's rendered page would fail
loudly and *correctly* on colour and font on every single screen — exactly the differences `design.md`
says must NOT transfer. Pixel-diff tooling is built for "did this same-themed page regress," not "did
this differently-themed page inherit the right structure." A closer fit in principle is a numeric,
per-element delta tool that compares geometry/spacing/typography/colour independently with tolerances
(e.g. the `Hi-Fidelity-Design` Claude Code skill: geometry ±2%, font size ±1px, colour via ΔE — and even
that still expects a shared visual language, would need per-element correspondence between the design's
DOM and FLS's rendered DOM, and is a standalone tool this project has not adopted). For one feature at a
time, a human-legible checklist (recommendation 2) reviewed by the same visual judgement `do_qa.md`
Step 7 already reserves for a human/agent ("MUST NOT be delegated") is the cheapest fit and requires no
new tooling.

**Rationale:** established (the pixel-diff critique, and Claude Code's own doc naming "a browser
screenshot compared against a design" as a legitimate verification check) + inference (the specific
checklist-not-pixel-diff design for *this* project, given its intentional theme divergence).

**Cost:** medium. Extra QA time per screen; requires recommendation 2 to exist first (nothing to check
against otherwise).

### 4. Feasibility: render the design's own artboards to local reference PNGs

Assessed honestly, since this would materially strengthen recommendation 3 (a real reference image
instead of "read the checklist and judge") — but it rests on assumptions this research cannot verify
without the design's actual file contents (only depth-0 has `DesignSync`).

**What it would take:**
1. Depth-0 (with `DesignSync`) `get_file`s the entry file and every file it loads, and writes them
   verbatim into a local directory (e.g. `<spec-dir>/design_extract/raw/`), preserving relative paths.
2. **Do not open via `file://`.** Chromium blocks cross-origin `fetch`/`import`/script loading from
   `file://` to `file://` by default (CORS + MIME-type restrictions on local files), so a saved
   multi-file canvas will not load its sibling `.jsx`/`.css` files that way even though there is no
   claude.ai login involved. Instead, serve the saved directory with a throwaway static server (e.g.
   `python3 -m http.server <port>`, a solo Bash call per `do_qa.md`'s own batching rules) and navigate
   Playwright MCP to `http://127.0.0.1:<port>/<entry-file>`.
3. **This is categorically different from the existing "never open with WebFetch/browser/Playwright"
   rule** in `register_design.md` — that rule is about the *live, authenticated* claude.ai page. A
   locally saved static copy needs no login. Worth stating explicitly in `design.md`'s "how to read it"
   so nobody either (a) assumes rendering is banned outright, or (b) assumes the ban's absence means
   it's proven to work.
4. **Real, unverified risks:**
   - *Module format.* If the canvas's script tags are `<script type="text/babel" src="…">` (Babel
     Standalone, no bundler), a static file server is enough. If the files use ES `import`/`export`
     expecting a bundler, a plain static server will not execute them and this approach fails outright
     without adding a build step — out of scope for a "render what was saved" spike.
   - *Outbound network.* These canvases typically bootstrap React/Babel Standalone from a public CDN
     (e.g. unpkg). Rendering therefore needs the sandbox to allow outbound fetches to that CDN at
     render time — plausible (it's a public, unauthenticated URL, not claude.ai) but not something this
     research can confirm from outside the tool sandbox's network policy.
   - *The 256 KiB `get_file` cap* (`register_design.md` Step 2) could truncate a large component file
     mid-save with no visible error, silently breaking the render. Any adoption of this idea needs a
     truncation check, not an assumption that every file fits.

**Verdict:** plausible, not proven. Recommend a **bounded spike** — one screen, one artboard, done once
by hand — before treating this as a standard step. If the spike fails on module resolution or network
policy, fall back to recommendation 2/3 (checklist against transcribed structure, no rendered
reference), which needs none of these assumptions. **Inference throughout** — no published guidance
covers this specific Claude-Design-canvas case; the CORS/file:// and Babel-Standalone-vs-bundler
reasoning is general web-platform knowledge applied to an unverified artifact format.

### 5. Keep and tighten the theme-override language already in `design.md` — cheap, already mostly right

**What exists:** `design.md`'s "how to treat it" already says the project's theme wins, names the
concrete FLS mechanisms (role tokens, cotton components, `c-icon`), and forbids copying raw colour/
font/spacing values or adding new tokens to match the design. This matches established practice
(Superdesign: "lock fonts/colors/8px spacing... forbid defaults out loud" in a file the agent reads
every session) almost exactly, and is a good example of that pattern already in place.

**What to add (inference, small):** name the specific defaults Claude tends to fall back to in *this*
project when a design doesn't fully pin something down (e.g. if the plainer notification build reached
for a generic Tailwind grey/blue instead of FLS's role tokens, or a default sans stack instead of the
project's chosen font) — one line in `design.md` or the `brand-guidelines` skill naming the two or three
concrete "don't reach for X, use Y" pairs actually observed. This is speculative without inspecting the
notification feature's specific regressions (out of this topic's scope), so treat it as a prompt to
that inspection rather than a ready-made list.

**Cost:** trivial once the concrete defaults are identified.

### 6. In-loop screenshot verification during implementation (lower priority, cost caveat)

**What:** Claude Code's own best-practices doc names a concrete pattern: "\[paste screenshot] implement
this design. take a screenshot of the result and compare it to the original. list differences and fix
them" as a first-class verification check, on par with tests/build/lint, and explicitly frames a
"browser screenshot compared against a design" as one of the checks worth gating a Stop hook or `/goal`
on. Applied here, an `implement_plan.md` batch subagent building a slice with a design screen could
render its own work and diff it against the extract (recommendation 1) *before* committing, rather than
waiting for the separate `do_qa` pass afterward.

**Cost/blocker:** `implement_plan.md`'s batch subagents are `general-purpose` with
`Read/Glob/Grep/Write/Edit/Bash/Skill` — no Playwright MCP today. Giving them browser access is a
bigger, riskier change (more tool surface in an unattended batch subagent, plus whatever `do_qa.md`'s
Rule 1 says about which Playwright server is safe to use) than the QA-time check in recommendation 3.
Flagging this as available established practice, not recommending it be adopted immediately — it's the
right shape for a project that already gives implementers a browser; FLS's implementers currently don't.

## Summary of concrete file edits, if adopted in order

1. `plan_from_spec.md` Step 1 — read design via `DesignSync` as today, but also write
   `<spec-dir>/design_extract/` (raw files + a screen→file README) scoped to this spec's coverage-table
   rows.
2. `plan_from_spec.md` Step 1/3 — per-slice "design screens and states" becomes a transcribed
   per-state checklist (structure/copy/state-presence, explicitly not styling), sourced from
   `design_extract/`, not a name-only pointer.
3. `claude_plugins/fls-dev/commands/do_qa.md` — new design-conformance sub-check after Steps 7/8 for
   test-plan cases that map to a design screen, checking the plan's checklist against the already-taken
   screenshots; a new `design_conformance` scratch record type; conformance misses default to the red
   lane in Step 13's triage (a judgement call, not an auto-fixable functional bug) unless clearly
   mechanical.
4. Optional, spike first: a rendering step (local static server + Playwright MCP) producing reference
   PNGs to make step 3 a real side-by-side rather than a checklist-only read.

## References

- [Claude Code best practices — official docs](https://code.claude.com/docs/en/best-practices) — "Give
  Claude a way to verify its work" table, explicitly naming "a browser screenshot compared against a
  design" and the paste-screenshot/compare/fix-differences pattern.
- [How to Make Claude Code UI Look Good and Better (Fix-It Guide) — Superdesign](https://superdesign.dev/blog/how-to-make-claude-code-ui-look-good) — visual-reference-first, lock
  design decisions in a persistent file, trade adjectives for constraints, name forbidden defaults,
  screenshot-compare-refine loop.
- [Claude Code for Designers — Builder.io](https://www.builder.io/blog/claude-code-for-designers)
- [Everything You Need to Know About Claude Design — Push to Prod](https://getpushtoprod.substack.com/p/everything-you-need-to-know-about)
- [Get started with Claude Design — Claude Help Center](https://support.claude.com/en/articles/14604416-get-started-with-claude-design)
- [Hi-Fidelity-Design (Claude Code skill) — numeric per-element deltas, not pixel-diff](https://github.com/gbechtold/Hi-Fidelity-Design) — geometry/typography/colour tolerance-based
  comparison instead of pixel diffing, and why pixel diffing is a poor match for intentional rendering
  differences.
- [Playwright — Visual comparisons (`toHaveScreenshot`)](https://playwright.dev/docs/test-snapshots)
- [Playwright Visual Regression Testing guide — Bug0](https://bug0.com/knowledge-base/playwright-visual-regression-testing) — pixelmatch mechanics, `maxDiffPixels`/`maxDiffPixelRatio`
  tolerances, and baseline update discipline.
- [From Claude Code to Figma — Figma Blog](https://www.figma.com/blog/introducing-claude-code-to-figma/)
- [How to structure Figma files for MCP and AI-powered code generation — LogRocket](https://blog.logrocket.com/ux-design/design-to-code-with-figma-mcp/) — design-token mapping and
  per-state/variant documentation as a fidelity aid.
- [Workflow Lab: Moving Between Design and Code With Agents — Figma Blog](https://www.figma.com/blog/workflow-lab-moving-between-design-and-code-with-agents/)

## Sources read directly in this repo (not web)

- `claude_plugins/sdd/commands/register_design.md`
- `claude_plugins/sdd/commands/spec_from_idea.md`
- `claude_plugins/sdd/commands/plan_from_spec.md`
- `claude_plugins/sdd/commands/implement_plan.md`
- `claude_plugins/fls-dev/commands/do_qa.md`
- `spec_dd/1. next/user-communication/design.md` (worked example of a registered design)

status: ok
