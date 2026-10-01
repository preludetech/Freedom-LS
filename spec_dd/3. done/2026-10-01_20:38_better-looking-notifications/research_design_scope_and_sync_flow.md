# Research: how scope answers and synced design artifacts should flow through SDD

## 1. Where scope decisions live today

The same handful of exclusions (Preferences gear, "Show older notifications", the message item,
`role="dialog"`) are recorded independently in at least four places, each restating the decision
rather than pointing at one home for it — the writing standard's "a decision stated more than
once" problem, applied to design scope specifically.

| Where | Quote |
| --- | --- |
| `register_design.md`'s `design.md` template, coverage table | `"A screen no spec owns gets `none (out of scope)`. It stays listed so nobody mistakes it for an oversight."` — a slot for effort-wide, per-screen scope, but only whole-screen granularity (no row is ever "half a screen, minus its gear icon"), and nothing in the live `spec_dd/1. next/user-communication/design.md` coverage table actually uses it yet — every screen there has a real "Built by". |
| `1. spec.md` (notifications core), Scope → Out | `"From the design: the Preferences links (gear in the panel header, button on the centre), the "Show older notifications" button (the centre paginates instead), and the message item."` |
| `2. plan.md` (notifications core), Design section | `"The design draws things the spec leaves out: the gear/Preferences links, "Show older notifications", the message item, `aria-haspopup="dialog"` and `role="dialog"`, and the "about" column on centre rows. Build none of them."` |
| `idea.md` (better-looking-notifications, this spec) | `"The done spec deliberately left some drawn elements out, and they stay out: the Preferences gear and button (no preferences page exists yet), the "about" line on centre rows, "Show older notifications" (the centre keeps its pagination), `role="dialog"`/`aria-haspopup="dialog"`... and the message item."` |

No file records the *question* that was asked (was one asked, or did the spec author simply decide?), *when* it was decided, or *which spec should revisit it*. `user-communication-2-notification-email` is the spec `design.md`'s coverage table names as the owner of the Preferences screens — nothing links "notifications core left the gear out" to "notification-email is where it comes back", so that connection currently lives only in a human's head.

## 2. Shape of a scope-decisions file

### Name

Checked `.claude/skills/domain-glossary/SKILL.md` and `claude_plugins/sdd/resources/domain_vocabulary.md`. Neither is about SDD-artifact filenames (they govern nouns *inside* specs, code identifiers, and words like "item", "grant", "learner" that already mean something else in FLS's domain), so the collision risk is against **existing SDD filenames**, not domain nouns: `design.md`, `design_brief.md`, `research_*.md`, `design_snapshot_*.md` (this spec's own hand-made example), and the practices research's proposed `design_extract/`. "Scope" itself is a spec-section heading (`## Scope`), not a domain term, so a name built on it doesn't collide with a domain word — but it should still read as a design artifact, not a spec section. Proposed name: **`design_scope.md`**, following the `design_*` naming family already established by `design.md`/`design_brief.md`/`design_snapshot_*.md`. Call each row's subject a **drawn element** (not "item" — that word is already ambiguously loaded in FLS's domain glossary for `ContentCollectionItem` rows vs. resolved children).

### Shape

One table, one row per drawn element, columns: `Element` (the control/screen-state, named the way `design.md`'s coverage table names screens, e.g. "Preferences gear (panel header)"), `Design section` (from the coverage table, so it's traceable back to `design.md`), `Question asked`, `Answer` (`build` / `leave out` / `later — <spec>`), `Decided at` (the spec or registration run that answered it), `Date`. A short prose note per row for the reasoning, matching the one-line-of-reasoning discipline the writing standard already asks of a spec's Decisions section.

### When to ask: both, at different granularity

For a cut-effort parent, `register_design.md` runs before the children exist, so it cannot ask a *child-scoped* question ("does `user-communication-2-notification-email` want this?") — there is no such spec yet to scope the answer to. But it can and should ask an **effort-wide** question for any drawn element that the coverage table would otherwise silently assign to a screen's owning child without anyone checking whether that child's *idea* (not just its screen) actually wants it — e.g. the coverage table already assigns "3 Notification preferences" wholesale to `user-communication-2-notification-email`, but the quiet-hours control belongs to the *later* four-email-option version owned by `user-communication-7-email-digests`. `register_design.md` is the only step that sees the whole design at once, so it is the right place to flag *effort-wide* candidates and note them as `later — <child>` when the coverage table already answers "which spec", or as `open — ask when <child> starts` when it doesn't.

`spec_from_idea.md` (and, for anything the spec missed, `plan_from_spec.md`) is the right place for the **per-child** pass: it already reads `design.md` and the design itself at depth 0, where `AskUserQuestion` is legal, and it is the point where "does *this* spec's stated scope actually want this control" has a spec-shaped answer. So: **both**, but they ask different things — registration flags candidates and defers what it can't yet scope; each child's `spec_from_idea` resolves what registration deferred to it, plus anything scoped to that child's own idea text that registration had no reason to flag.

### One file, updated in place, not one file per spec

`design_scope.md` lives at the **parent** (see §5) so every child reads and writes the same file, because the cross-spec case the user names — `notification-email` building the Preferences button `notifications-core` left out — is exactly a case of one row's answer changing. When `user-communication-2-notification-email` later says "build" for the row `notifications-core` marked `leave out`, that spec **edits the existing row** (`Answer` becomes `build (user-communication-2-notification-email, <date>)`, the old reasoning kept as a one-line "supersedes: <old reason>"), per the writing standard's "rewriting means replacing" — it never adds a second row for the same element. This is also how a later spec discovers the earlier decision at all: it reads `design_scope.md` before asking anything, so a question already answered (even by a different spec) is never re-asked.

### Re-registration

`register_design.md`'s Step 1 already says re-registration "rewrite[s] `design.md` whole". `design_scope.md` is a **separate file that re-registration never rewrites wholesale** — it reconciles instead: for each drawn element still present in the updated design, its row is untouched; a genuinely new element gets a new row with no answer yet (queued for the next pass); an element the update removed gets its row marked `removed from design — decision moot`, kept rather than deleted, so history of who decided what is never silently lost the way overwriting `design.md` already discards its own prior link/notes.

## 3. What generates the questions

`register_design.md` Step 2 already produces, per screen, a mapping to the design brief's section. Extend that same pass one level down, to controls within a screen, and compare each one against three things already on disk or already read in that step:

1. **The design brief** (`design_brief.md`) — does its prose for this screen's section call for this control? The brief's own "What not to draw" section is the negative space; a control that isn't in either the positive prose or the negative list is the interesting case.
2. **The spec or idea text** — for a screen already assigned to a child in the coverage table, does that child's `idea.md` (or `1. spec.md` if it exists) mention the control at all?
3. **What FLS already has** — `Glob`/`Grep` for a matching URL name, view, or model (e.g. does a "preferences" URL or model exist under `content_engine`/`comms`/wherever the effort's app lives?). A control with no brief mention, no spec mention, and no matching code is the strongest scope-creep candidate; one that fails only one of the three checks is a weaker candidate but still worth a row.

Only elements that fail at least one check become candidates — for the notifications design that narrows section 3 alone (Preferences, all four screens) from "every control drawn" down to a handful: the gear icon (no matching FLS URL, not in the notifications-core idea), the four-option email control and quiet hours (brief says "which ship later", not in this pass's scope), and the "about" column (present in the JSX, absent from the brief's plain-English description). That is small enough to fit `AskUserQuestion`'s 2–4-questions-per-call, 2–4-options-each limit directly: one question per element or small cluster of related elements, options `Build now (in <this spec>)` / `Leave out for now` / `Later — <named future spec, if the coverage table already names one>` / `Not sure — default: leave out`, with the default pre-selected the way `spec_from_idea.md`'s existing "take the default, list it under Open questions" rule already works for un-asked questions.

## 4. Consumers

| Step | Reads from the synced design directory / `design_scope.md` | Does with it |
| --- | --- | --- |
| `spec_from_idea.md` | `design_scope.md` (all rows touching this spec's screens); the parent's synced design directory (see §5) for this spec's own curated excerpt | Writes Scope → Out citing `design_scope.md` by path instead of re-listing reasons (removes the duplication in §1); runs the per-child `AskUserQuestion` pass for anything not yet answered (§2/§3), then appends the new rows itself |
| `plan_from_spec.md` | `design_scope.md` and the spec's own curated excerpt (not `DesignSync` again, since the excerpt is already a faithful, cheaper copy) | Plan's "Design" section points at `design_scope.md` rather than re-stating "build none of them"; if implementation-level detail surfaces a new candidate the spec never saw, asks about it the same way Step 1 already asks about contradictions, and appends the row |
| `implement_plan.md` batches | The synced design directory and `design_scope.md`, passed as paths in the batch brief | Batch subagents have neither `DesignSync` nor `AskUserQuestion`; `design_scope.md` is their only way to know that a control visible in the synced JSX (e.g. the gear icon in `uc-shell.jsx`) is deliberately excluded, so they don't build it just because the source shows it |
| `do_qa.md` design-conformance step (proposed in the forensics/practices research) | `design_scope.md`, keyed by element, before filing any gap as a bug | An element present in the design artboard but absent from the build: check `design_scope.md` first. `leave out`/`later` → not a bug, it's correct; no row at all → file as a distinct `undecided scope` red-lane item (a human decision, not a QA finding), never silently pass or silently fail it as a fidelity bug. The comparison itself happens after Step 7/8/9's screenshots exist, against the design's own screenshots (§5) or the design's synced source if no render exists yet — always red-lane, never auto-fixed, per the forensics research's condition 3 (a product/UX decision). |

## 5. Repo hygiene

### Where synced files go

The done spec's own plan still reads `spec_dd/1. next/user-communication/design.md` — the parent directory `user-communication/` never moves; only the numbered children (`user-communication-1-notifications-core`, now living under `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/`) progress through `1. next/` → `2. in progress/` → `3. done/`. `roadmap.md`'s cut mode (C6) confirms this is deliberate: the parent keeps living material ("Nested directories the cut does not cover stay where they are") and is never itself classified as `next`/`in progress`/`done`.

That makes the parent (`spec_dd/1. next/user-communication/`) the right home for anything **shared across children**: a full raw sync of the design's source (all of `uc/*.jsx`, `uc.css`) done **once**, at registration, rather than once per child — avoiding eight repeated `DesignSync` fetches of the same files and eight copies of the same source in the repo. Each child then keeps only its **own curated excerpt** — the pattern this spec already hand-built as `design_snapshot_notifications.md`: a markdown file with just the JSX/CSS fragments and copy this spec's screens use, written by that spec's own `spec_from_idea.md`/`plan_from_spec.md` run by reading the parent's full sync with a plain `Read`, never `DesignSync` again. Because the excerpt lives with the child, it travels with it through `1. next/` → `2. in progress/` → `3. done/`, while the full sync and `design_scope.md` stay put in the permanent parent directory, so no path ever needs rewriting when a child moves — exactly the behaviour already observed for `design.md` itself.

For a single, uncut spec (no effort parent), there is no separate "parent" location: the full sync, `design_scope.md`, and the curated excerpt all simply live in that one spec directory.

Screenshots (item 2 of the requested extension — a subagent renders the design and shoots each artboard) should **not** reuse the directory name `screenshots/`: `do_qa.md` Step 1 runs `qa_cleanup.sh` which deletes and regenerates `<spec-dir>/screenshots/` on every QA pass, and would delete the design reference images along with the QA run's own. Use a distinct name, e.g. `<spec-dir>/design_screenshots/`, so `qa_cleanup.sh`'s scope (already spec-dir-qualified) never touches it.

### Pre-commit and `.gitignore`

`.pre-commit-config.yaml` has no prettier, no eslint, and the one HTML formatter (`djlint`) is commented out — so synced JSX/CSS/HTML pass through untouched; nothing will reformat or mangle the design's own markup. The hooks that do apply to every file type: `trailing-whitespace` and `end-of-file-fixer` (both skip binary files by design, so TTF/PNG are unaffected; JSX/CSS/HTML/markdown just get a trailing newline, harmless) and, the one with teeth, `check-added-large-files` (`--maxkb=1024`, i.e. 1 MB per file). Given the notifications design project's actual size — about 10 TTF fonts, a few PNGs, roughly 10 JSX/CSS files — the JSX/CSS/markdown excerpts are plain text and comfortably under 1 MB each; screenshots need the same treatment `do_qa.md` already gives its own QA screenshots (`compress_screenshots.sh`, run via `sdd:sdd-mechanic`, "scans `spec_dd/**` for oversized PNGs" — already covers any directory under `spec_dd/`, so `design_screenshots/` needs no new tooling). Fonts are the one risk: TTFs commonly run 20–150 KB each, so ten of them are unlikely to individually trip the 1 MB limit, but there is no reason to commit them at all — nothing downstream reads a font file directly; only a rendered screenshot or the JSX/CSS naming a font family matters, and both survive without shipping the binary.

### What should be committed

- **Commit**: the curated per-child excerpts (`design_snapshot_*.md`-style markdown), `design_scope.md`, and the compressed design reference screenshots. These are small, text or already-compressed-PNG, and are exactly the reference material later QA and implementation runs need permanently — the same argument `do_qa.md` Step 17 already makes for committing its own `screenshots/` directory.
- **Do not commit**: the full raw multi-file sync at the parent (`uc/*.jsx`, `uc.css` verbatim, and especially the ~10 TTF fonts) as a permanent repo artifact. It exists only to be read once, when writing curated excerpts and, if the render spike (practices research §4) is attempted, to be served locally. Treat it the way `qa-screenshots/` and `.playwright-mcp/` are already treated: a working directory, `.gitignore`d (add an entry, e.g. `design_sync/` or whatever the raw-sync directory is named), regenerable from `DesignSync` at any time by re-running registration, and never carried into a PR. This keeps the repo's permanent record to the small, human-legible artifacts (`design_scope.md`, excerpts, screenshots) that later steps actually read, and keeps the large, disposable binary payload out of git entirely.

## References

- `claude_plugins/sdd/commands/register_design.md`
- `claude_plugins/sdd/commands/spec_from_idea.md`
- `claude_plugins/sdd/commands/plan_from_spec.md`
- `claude_plugins/sdd/commands/implement_plan.md`
- `claude_plugins/fls-dev/commands/do_qa.md`
- `claude_plugins/sdd/commands/roadmap.md`
- `claude_plugins/sdd/commands/next.md`
- `claude_plugins/sdd/commands/protected/setup_todo_list.md`
- `claude_plugins/sdd/resources/writing_standard.md`
- `claude_plugins/sdd/resources/domain_vocabulary.md`
- `.claude/skills/domain-glossary/SKILL.md`
- `spec_dd/1. next/user-communication/design.md`
- `spec_dd/1. next/user-communication/design_brief.md`
- `spec_dd/2. in progress/better-looking-notifications/idea.md`
- `spec_dd/2. in progress/better-looking-notifications/research_design_fidelity_forensics.md`
- `spec_dd/2. in progress/better-looking-notifications/research_design_fidelity_practices.md`
- `spec_dd/2. in progress/better-looking-notifications/design_snapshot_notifications.md`
- `spec_dd/2. in progress/better-looking-notifications/todo.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/1. spec.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/2. plan.md`
- `.pre-commit-config.yaml`
- `.gitignore`

status: ok
