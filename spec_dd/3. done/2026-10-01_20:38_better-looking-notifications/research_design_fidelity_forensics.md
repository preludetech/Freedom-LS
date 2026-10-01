# Research: forensics of the design-fidelity failure

## Verdict, up front

The chain did **not** break where the user suspected. Claude Code **could** and, on the file
evidence, **did** read the Claude Design design at both `spec_from_idea` and `plan_from_spec`
(both depth-0 steps). The break is downstream and structural, in three places:

1. **Nothing in the pipeline ever checks the built UI against the design's visuals.** QA
   (`fls-dev:do_qa`) runs a purely behavioural/accessibility test plan and never opens the design.
   Two full QA cycles on this spec found and fixed three bugs — none of them about appearance.
2. **The registered "how to treat it" policy (design.md / `register_design.md`) mandates styling
   from FLS's *existing* tokens only, and FLS's existing tokens/components render plainer and
   flatter than a Claude Design mockup.** This is a deliberate rule, working as designed, but
   nobody checks whether the *result* still reads as "a serious design built faithfully" once the
   substitution is done.
3. **The spec-writing step had no forced deliverable that translates the design's exact visual
   values (spacing, radius, shadow, density) into FLS tokens**, the way an earlier spec
   (`better-form-start-page`) happened to produce in `research_design_source.md`. Without that
   artifact, "take the structure, not the styling" is executed impressionistically rather than
   against a checklist, and detail is lost between spec and plan and between plan and
   implementation.

Below is the evidence for each step of the chain, per-step tool grants, then the ranked causes and
concrete fixes.

## Per-step verdict: could Claude see/read the design?

| Step | Command / agent | Runs at | `allowed-tools` / `tools:` frontmatter | Mentions the design? | Could it load `DesignSync`? |
| --- | --- | --- | --- | --- | --- |
| Register design | `claude_plugins/sdd/commands/register_design.md` | depth 0 | `Read, Write, Edit, Glob, Grep, Bash, Agent, Skill, ToolSearch, AskUserQuestion` | Yes — it is the command that writes `design.md` | Yes, explicitly listed |
| Write spec | `claude_plugins/sdd/commands/spec_from_idea.md` | depth 0 | `Read, Write, Edit, Glob, Grep, Bash, Agent, Skill` — **no `ToolSearch`** | Yes, Step 3: "Read the design itself the way that file says" | Yes in practice — see below |
| Write plan | `claude_plugins/sdd/commands/plan_from_spec.md` | depth 0 | `Read, Write, Edit, Glob, Grep, Bash, Skill, Agent` — **no `ToolSearch`** | Yes, Step 1: "Read the design through the Claude Design integration as that file says" | Yes in practice — see below |
| Implement plan | `claude_plugins/sdd/commands/implement_plan.md` | depth 0 orchestrator, batches at depth 1 (`subagent_type: "general-purpose"`) | orchestrator: `Read, Glob, Grep, Write, Edit, Bash, Skill, Agent` — **no `ToolSearch`**; `general-purpose` has no agent-definition file in this repo, so its tool grant is opaque | **No mention of `design.md` or DesignSync anywhere in the file** | Unknown/likely no — see caveat below |
| Frontend QA | `claude_plugins/fls-dev/commands/do_qa.md` | depth 0, spawns `sdd:sdd-worker` / `fls-dev:qa-bugfixer` at depth 1 | `Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, mcp__playwright__*, mcp__plugin_ds_playwright__*` — **no `ToolSearch`, no DesignSync** | **No mention of `design`, `design.md` or DesignSync anywhere in the file** | No |
| QA bug-fixer | `claude_plugins/fls-dev/agents/qa-bugfixer.md` | depth 1 | `tools: Bash, Read, Edit, Write, Glob, Grep, Skill` | No | No |
| SDD research worker | `claude_plugins/sdd/agents/sdd-worker.md` | depth 1 | `tools: Read, Glob, Grep, WebFetch, WebSearch, Write` | No | No (confirmed in the task brief too) |

**On "yes in practice" for spec/plan:** neither command's frontmatter lists `ToolSearch`, yet both
artifacts contain content that could only come from actually reading the design's files, not from
guessing:

- `1. spec.md`, Decision 9: *"The design's `role="dialog"` is not used either, because the panel
  does not trap focus."* — naming an exact ARIA attribute drawn in the design.
- `1. spec.md`, "Open questions": *"The row marker reads 'Unread' (the design draws 'New')..."* —
  a specific copy difference between the design and the spec's own wording.
- `2. plan.md`, "Design" section: names the exact component/file names — `uc/uc-shell.jsx` (`Bell`,
  `Header`, `NotifItem`, `NotifPanel`), `uc/uc-notify.jsx` (`HeaderStates`, `NotifOpen`, `NCentre`,
  `NRow`), `uc/uc-data.jsx` — and explicitly lists what to leave out: *"the gear/Preferences links,
  'Show older notifications', the message item, `aria-haspopup="dialog"` and `role="dialog"`, and
  the 'about' column on centre rows."*

This is consistent with the task brief's established fact that DesignSync works in the **main
(depth-0) session** regardless of a command file's `allowed-tools` list — `allowed-tools` in a
slash-command's frontmatter reads as a pre-approval list for the interactive session (avoiding
permission prompts), not a hard capability gate the way an *agent's* `tools:` frontmatter is for a
spawned subagent. The evidence for the harder gate on subagents is direct: `sdd-worker.md`'s
`tools:` line has no DesignSync and the task brief confirms it cannot load it; `qa-bugfixer.md`'s
`tools:` line is similarly exhaustive and excludes it. So: **register_design, spec_from_idea and
plan_from_spec, run at depth 0, could and did read the design. Everything spawned as a subagent
(research workers, QA bug-fixer, and — most likely, though its definition is not in this repo to
confirm directly — the `general-purpose` implementation batches) could not.**

**Caveat on implementation batches:** `implement_plan.md` spawns `subagent_type: "general-purpose"`
for every batch. There is no `claude_plugins/*/agents/general-purpose.md` in this repo — it is a
built-in Claude Code agent type, so its tool grant can't be read from a file here. What *can* be
said from the files: (a) `implement_plan.md` never tells the batch subagent to consult the design
at all, so even if it had DesignSync, nothing in its brief would trigger using it; (b) the
orchestrating command's own frontmatter has no `ToolSearch`, and if tool grants for spawned
subagents are scoped from the spawning command's frontmatter (as they visibly are for every
*custom* agent in this repo), the batches likely can't load it either. This second point is
**speculation** — flagged as such — because I have no file that states the inheritance rule or
`general-purpose`'s actual grant.

## Was the design translated into concrete structure, or only named?

Concretely, not just named — the plan is unusually specific:

- `2. plan.md`, Slice 6: exact Tailwind classes for the panel —
  `class="fixed inset-0 z-50 bg-surface sm:absolute sm:inset-auto sm:right-0 sm:top-full sm:mt-2
  sm:w-96 sm:rounded-lg sm:border sm:border-border sm:shadow-lg"` — translating the design's
  dropdown-panel structure (rounded corners, elevation, fixed width) into FLS's own token
  vocabulary (`bg-surface`, `border-border`, role-token focus rings).
- Slice 3 and 5 give literal row markup, badge markup, colours (`text-on-surface`, `text-muted`,
  `bg-surface`, `bg-error text-on-error`), and states drawn from the design's brief sections
  ("all read", "empty", "Unread filter empty").

So the spec → plan leg of the chain is the strongest part of the pipeline, not the weakest. This
narrows the likely failure to *after* the plan (implementation fidelity to the plan's own
specified classes) and to *the absence of any check* that would have caught a gap either way.

## Did QA compare against the design?

No, at any point. `3. frontend_qa.md` (produced by `plan_from_spec.md` Step 5, which only instructs
"explain how to check that the feature works using a browser... what you expect to see") describes
every check in behavioural terms: "a panel opens under it: heading 'Notifications' with 'N
unread', the eight newest rows, and a footer with..." — never "compare this screenshot against the
design's artboard for section 1." `do_qa.md` itself has no step, rule or tool grant that touches
`design.md` or DesignSync anywhere in its ~640 lines. `qa_report.md`'s own methodology section
lists only "Diff scoping", "Smoke gate", desktop/mobile/tablet functional pass/fail rows, and
"General notes" — again nothing about visual comparison.

This is corroborated by the spec's own `todo.md`, section 9 (QA): a prior QA cycle found and fixed
three bugs before the clean run we read —

- *"notification row lists indented 24px by the global ul base style..."*
- *"...whether notification centre page and filter changes should push the URL (hx-push-url)..."*
- *"...where keyboard focus should land after Mark all as read..."*

All three are legitimate bugs, and all three are **functional/behavioural**, not appearance. Two
full QA passes on this spec never flagged "this looks flatter/plainer than the mockup" as a
category of defect, because nothing in the QA test plan or the `do_qa.md` process asks that
question.

## Why "faithful structure" still looks worse

`spec_dd/1. next/user-communication/design.md` ("How to treat it") and the template it comes from
in `register_design.md` are explicit and, on the plan's evidence, followed:

> *"The project's existing design system wins over the design. Use its theme tokens, components,
> widgets and icons... Never copy a raw colour, font or spacing value out of the design, never add
> a theme token to match it, and never build a new component where the project already has one that
> does the job."*

The built screenshots (`screenshots/page-3-1-panel-open.png`, `page-4-centre-p1.png`,
`page-4-8-all-read.png`, `page-9-tablet-panel.png`) show exactly what that rule produces here: a
correct structure (bell → panel → eight rows → footer with "Mark all as read" / "See all"; centre →
toolbar → day-grouped rows → pagination; all-read banner; unread markers) rendered in FLS's plain
default look — thin borders, default-blue link-styled row titles, a flat grey category icon, no
card elevation beyond a hairline border. This matches a design built for *density, hierarchy and
polish* (per the brief) mapped onto a token set that, at least as used here, doesn't carry much
elevation or colour variety for this kind of list UI.

This is the part of the failure that is **not** a broken instruction-following chain: every command
did what it was told. It is a **policy gap**: nothing after "take structure, not styling" checks
whether the *resulting* screen still reads as a serious, faithfully-built interface once the
substitution happens. The earlier `better-form-start-page` spec's `research_design_source.md`
(`spec_dd/3. done/2026-09-08_17:31_better-form-start-page/research_design_source.md`) shows what
closing that gap looks like: an explicit "Token mapping" table (design var → FLS token, with a
"**Radius caveat**" and a "**Shadow caveat**" that reason about the *loss* when a design value has
no FLS equivalent, e.g. *"FLS exposes `--fls-radius-sm/md/lg/pill` only... reserve literal
`rounded-xl` for the few places where the larger radius is load-bearing"*), plus an icon-mapping
table and a "what the design shows that FLS has no data for" section. Nothing this detailed exists
for `user-communication-1-notifications-core`; the spec's own research fan-out
(`spec_from_idea.md` Step 1) only ever spawns three fixed, generic research tasks — "Analyse the
existing codebase", "Research relevant best practices", "Examine reference implementations" — none
of which is "map this registered design's visual values onto FLS's tokens." The
`better-form-start-page` research file is not a required output of any command; it happened because
that idea's `idea.md` apparently pushed hard enough on fidelity ("*you must not make new
functionality based on the design. The point is to copy the look and feel*", quoted inside that
research file) that the model produced it anyway. For notifications, the idea and spec both cite
`design.md` but never demand that kind of literal mapping, and no command forces one.

## Ranked causes (most to least likely, each with evidence)

1. **No design-fidelity check exists anywhere downstream of the plan.** Evidence: `do_qa.md` (no
   mention of `design`/DesignSync in ~640 lines), `3. frontend_qa.md` (purely behavioural test
   steps), `qa_report.md` (purely behavioural results, 0 bugs), `todo.md` §9 (two QA cycles, three
   bugs found, none about appearance). This is the single most certain, most consequential gap: a
   plan that under- or over-specifies visual density has no safety net.

2. **The "existing tokens win" policy has no accompanying instruction to preserve the design's
   *density/hierarchy/polish* independent of its literal colours** — `design.md`'s "How to treat
   it" asks for faithfulness to "layout, density, hierarchy, component shapes" in one sentence and
   then, in the very next section, forbids copying any raw value, with no worked method (a token
   mapping table, a "what can't be reproduced" list) for reconciling the two. `better-form-start-page`
   solved this ad hoc with `research_design_source.md`; `user-communication-1-notifications-core`
   did not reproduce that pattern because nothing requires it.

3. **`spec_from_idea.md`'s fixed 3-task research fan-out has no design-specific slot.** Evidence:
   Step 1 names exactly "Analyse the existing codebase / Research relevant best practices / Examine
   reference implementations", and the seven `research_*.md` files this spec actually produced
   (badge polling, category registry, delivery backend seam, prior notification UX, read state and
   retention, first events edge cases, notification content and targets) cover every backend
   concern but none is a design-token mapping. Contrast with `better-form-start-page`'s
   `research_design_source.md`, which is exactly that kind of artifact but is not a named,
   repeatable step in any command.

4. **Implementation never re-consults the design.** Evidence: `implement_plan.md` contains no
   mention of `design.md` or DesignSync; it only says "Implement each step in the batch exactly as
   written in the plan." Where the plan's own markup was under-specified (it gives Tailwind classes
   for the panel wrapper and badge, but not, for example, row padding/spacing rhythm, icon tinting,
   or hover/elevation treatment for centre rows), there was no mechanism for the implementer to go
   back to the source. This compounds cause 1: if the implementer drifts from the plan's own
   classes, or the plan's classes render flatter than intended, nothing catches it either at
   implementation or at QA time.

5. **(Speculative, flagged as such) The `general-purpose` implementation batches likely cannot load
   DesignSync even if instructed to.** No agent-definition file for `general-purpose` exists in
   this repo to confirm its tool grant; the inference rests on the pattern shown by every *custom*
   agent in this repo (`sdd-worker`, `qa-bugfixer`) of an exhaustive `tools:` list that omits
   DesignSync, and on `implement_plan.md`'s own command frontmatter lacking `ToolSearch`. This is a
   secondary cause even if true, because cause 4 (nobody tells it to check) would make it moot
   regardless.

## Git history

Verified at depth 0 with `git log --date=iso`. The design was registered before any spec work
started, so every step after registration could have used it:

| When (2026-09-26, +0200) | Commit |
| --- | --- |
| 07:03 | `fbdcf22e` add `/sdd:register_design`; `eb1d5cbb` register the Claude Design design |
| 07:06 | `13307778` start the spec |
| 07:22 / 07:28 | `9ffee905` write the spec; `bfafc338` review and tighten it |
| 08:03 | `d809437d` write the implementation plan |
| 16:25 | implementation finished (`7f43f74a`, `38ce64db`) |
| 17:42 and 21:33 | two frontend QA passes (`1a0f59d4`, `ca035938`) |
| 2026-09-27 00:26 | `50b336b7` close out the worktree |

## Concrete fixes (files to change, and what to change — no code given)

1. **`claude_plugins/fls-dev/commands/do_qa.md`** — add `ToolSearch` to the frontmatter
   `allowed-tools` line, and add a new step (after the desktop pass, before "Generate a report")
   that: if the spec directory's `1. spec.md` or `idea.md` cites a `design.md`, load `DesignSync`,
   `get_file` the artboards/components covering the screens this run's test plan touches, and
   compare them against 2–3 of the screenshots already captured in Step 7/8/9 — not pixel-diffing,
   but the same kind of judgement call Step 7 already makes for behaviour ("exploratory visual
   judgement... MUST NOT be delegated to a subagent"). Record a mismatch as a `bug` record with a
   new `category: "design-fidelity"` field, and route every such bug to the **red lane** in Step 13
   unconditionally (it is definitionally a product/UX decision — condition 3 of the existing green
   lane already excludes this) so it becomes a `todo.md` item for a human rather than a silent
   auto-fix or a silent pass.

2. **`claude_plugins/sdd/commands/plan_from_spec.md`** — Step 5 (frontend_qa.md) currently says
   only "explain how to check that the feature works using a browser... what you expect to see."
   Add: when the spec cites a `design.md`, add one QA step per design-covered screen/state that
   names the specific artboard/component to open via DesignSync and asks the reviewer to judge
   layout density, hierarchy and component shape against it, not just presence of the right text
   and controls. Also strengthen the plan's own "## Design" section (currently a good but ad hoc
   pattern, see Slice 6's Tailwind classes) into a required subsection modelled on
   `research_design_source.md`'s "Token mapping" table: for every drawn colour, spacing, radius and
   shadow value that has no FLS role-token equivalent, name the FLS stand-in chosen and say
   explicitly what is lost by the substitution, the way that file's "Radius caveat" and "Shadow
   caveat" paragraphs do.

3. **`claude_plugins/sdd/commands/spec_from_idea.md`** — Step 1's fan-out recipe should add a
   conditional fourth research unit, alongside the fixed three: "If the idea's directory (or its
   cut-effort parent) has a `design.md`, spawn one additional `sdd:sdd-worker`-class research task
   at depth 0 (since only depth 0 can load `DesignSync`) producing `research_design_tokens.md`:
   read the design, and for every screen this spec owns (per `design.md`'s coverage table), map its
   drawn colours, spacing, radii, shadows and icons onto FLS's existing tokens/components, flagging
   anything the design shows that has no faithful FLS equivalent." This turns the
   `better-form-start-page` pattern into policy rather than a one-off.

4. **`claude_plugins/sdd/commands/implement_plan.md`** — currently contains no mention of the
   design at all. Add, to Step 2 ("Batch and Execute"): when a slice's plan text names `design.md`
   and specific screens/states (as this plan's Slices 3–6 do), the depth-0 orchestrator — which can
   load DesignSync, unlike the spawned batch subagent — should, immediately after that batch's
   commit and before moving to the next batch, open the relevant design artboard and spot-check it
   against one screenshot or a quick look at the rendered page, the same way Step 3 already checks
   functional success criteria. This catches drift one slice at a time instead of only at the very
   end (or never, per cause 1 above).

## References

- `spec_dd/1. next/user-communication/design.md`
- `spec_dd/1. next/user-communication/design_brief.md`
- `claude_plugins/sdd/commands/register_design.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/idea.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/1. spec.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/2. plan.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/3. frontend_qa.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/qa_report.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/todo.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/screenshots/page-3-1-panel-open.png`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/screenshots/page-4-centre-p1.png`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/screenshots/page-4-8-all-read.png`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/screenshots/page-9-tablet-panel.png`
- `spec_dd/3. done/2026-09-08_17:31_better-form-start-page/research_design_source.md`
- `claude_plugins/sdd/commands/spec_from_idea.md`
- `claude_plugins/sdd/commands/plan_from_spec.md`
- `claude_plugins/sdd/commands/implement_plan.md`
- `claude_plugins/fls-dev/commands/do_qa.md`
- `claude_plugins/fls-dev/agents/qa-bugfixer.md`
- `claude_plugins/sdd/agents/sdd-worker.md`

status: ok
