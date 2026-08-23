# Research: upgrade-notes command

## Summary

- The current schema (`claude_plugins/fls-dev/commands/update_upgrade_notes.md:10-46`) has **no
  hard/optional distinction** for `requires_settings_change` / `changed_settings` — it's one bool
  + one free-text list, described only as "new or renamed settings keys."
- D6 ("no new schema flag needed — the field is free-text and already carries the key list") is
  **directionally correct but its own citation is weak**: it credits "Part 1's own notes" (i.e.
  `fls-test-portability-part1/upgrade_notes.md`), but that file's single `changed_settings` entry
  is a pytest-marker registration caveat, not a strong "must set or app breaks" example, and its
  hardness lives entirely in prose, not in the frontmatter list itself. The real proof of D6 is
  elsewhere in the corpus (see below) — the spec should probably re-point this citation.
- The **strongest supporting evidence for D6** is that authors have already, independently,
  embedded hard-vs-soft signal as inline YAML comments inside `changed_settings`, in the same list,
  side by side — e.g. `SECRET_KEY # now mandatory — hard-fails at boot if missing/empty` next to
  `DB_SSLMODE # new env var (default "prefer")`
  (`spec_dd/3. done/2026-07-17_09:57_.../upgrade_notes.md:6-14`), and
  `WEBHOOK_ENCRYPTION_SALT # NEW required secret in production — app fails fast on boot if unset`
  next to `DJANGO_ADMIN_URL # .env.example parity — config, default "admin/"`
  (`spec_dd/3. done/2026-07-19_07:52_more-deploy-preparation/upgrade_notes.md:6-11`). No new field
  was needed for either — free text already carried the distinction.
- The **worked example the plan cites for "changed check ID = hard settings change"** is real and
  exists: `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md` (titled
  "test_portability_3_system_checks" but living in a differently-named directory — a small
  repo-hygiene inconsistency worth flagging) sets `requires_settings_change: true` /
  `changed_settings: ["SILENCED_SYSTEM_CHECKS"]` for the `E001`→`E002` re-ID, purely on author
  judgement — **the command's own "focus on" trigger list
  (`update_upgrade_notes.md:75-82`) never mentions renamed/split check IDs as a
  `requires_settings_change` trigger.** This is a genuine, currently-uncovered gap; the planned
  guidance addition would be the first place it's written down.
- **Consumption side confirms the field is read by an LLM subagent doing judgement work, not a
  strict parser.** `claude_plugins/fls-dev/commands/concrete/update_fls.md:78` says
  `requires_settings_change` → "review and apply the listed `changed_settings`" — free text is
  fine because a human/agent reads and reasons about it. This weakens the case that a hard/soft
  *flag* would add machine value; it's consumed as prose either way. It also means D6's premise
  (no parser needs a new machine field) is correct for the one real consumer in the repo.
- `update_template_repo.md:50` and `README.md:112,124` treat `requires_settings_change` +
  `changed_settings` identically — no other consumer distinguishes hard/soft either, so there's no
  scattered-consumer risk in skipping a new flag.
- The corpus **does** let a careful reader distinguish MUST from MAY today, but only through prose
  discipline (the "Breaking changes" section, and increasingly through inline comments in the YAML
  list) — it is not guaranteed by the schema or the command's current instructions. That's exactly
  the gap Layer 5 proposes to close by adding explicit guidance rather than a flag.
- Two of fifteen existing `upgrade_notes.md` files set `requires_settings_change: true` for changes
  that are **entirely optional/parity** (e.g. `more-deploy-preparation`'s `.env.example` parity
  vars), proving the current binary flag already conflates "you must act" and "here's a new knob
  you may ignore" inside one boolean — the strongest argument *for* doing something here, even if
  the "something" is prose guidance rather than schema.

## 1. Current declared schema in `update_upgrade_notes.md`

Full schema, `claude_plugins/fls-dev/commands/update_upgrade_notes.md:14-35`:

```markdown
---
requires_migrations: false
requires_template_review: false
changed_template_paths: []          # populated when requires_template_review is true
requires_settings_change: false
changed_settings: []                # keys/settings when requires_settings_change is true
requires_package_upgrade: false
changed_packages: []                # package==version entries when true
requires_npm_install: false
changed_npm_packages: []            # package@version npm entries to add to the project's package.json
requires_tailwind_rebuild: false
---

# Upgrade notes: <spec-name>

## Breaking changes
<prose, or "None">

## Manual steps
<prose, or "None">
```

Field-by-field ("Flag semantics", `update_upgrade_notes.md:37-46`):

- `requires_migrations` (bool) — "the feature adds or alters models; downstream must run
  `migrate`." (line 39)
- `requires_template_review` (bool) + `changed_template_paths` (list) — "one or more templates
  that downstream projects typically override were changed." (line 40)
- `requires_settings_change` (bool) + `changed_settings` (list) — **"new or renamed settings
  keys. List them in `changed_settings`."** (line 41) — this is the entire current description.
  No mention of required-vs-optional, no mention of check IDs, no mention of
  `SILENCED_SYSTEM_CHECKS` as a category.
- `requires_package_upgrade` (bool) + `changed_packages` (list) — "new or updated Python
  packages... `package==version` entries." (line 42)
- `requires_npm_install` (bool) + `changed_npm_packages` (list) — npm packages, with a note that
  downstream `package.json` is not auto-synced. (line 43)
- `requires_tailwind_rebuild` (bool) — Tailwind source changed. (line 44)
- Closing rule: "Set every unused list to `[]` and every unused flag to `false`." (line 46)

`requires_settings_change` / `changed_settings` are mentioned in exactly one other place in the
file — the Step 2 trigger list, `update_upgrade_notes.md:79`:

> New or changed `settings` keys or `config/` files → `requires_settings_change` +
> `changed_settings`

That is the **complete** current guidance surface for this flag pair. There is no language
anywhere in the file distinguishing a hard/required change from an optional/informational one,
and no mention of system-check IDs, `SILENCED_SYSTEM_CHECKS`, or Layer-4-style checks at all.

The plan's ground-truth claim (`2. plan.md:17-20`) that these are documented "at lines ~19-20,
~41, ~79" is accurate against the current file — verified above.

## 2. Structure of the command file

- **Front matter** (`update_upgrade_notes.md:1-4`): `description` and `allowed-tools: Read,
  Write, Glob, Edit, Bash, Agent`. No `argument-hint`, no other frontmatter keys.
- **Intro** (lines 6-8): one-sentence purpose statement, then a "depth 0 / no fan-out" note —
  this command is explicitly lean/single-agent, unlike fan-out commands.
- **`## upgrade_notes.md schema`** (lines 10-46): the schema code block plus the "Flag semantics"
  bullet list. This is the authoritative artifact contract and the section D6's guidance most
  naturally extends — either as new bullets under "Flag semantics" or as a new subsection
  immediately after it.
- **`## Step 1: Locate the spec directory`** (lines 48-56): a 3-step branch-name/AskUserQuestion
  resolution procedure, worded almost identically to the same step in sibling commands
  (`update_template_repo.md:12-18`) — house style is to repeat this verbatim across commands.
- **`## Step 2: Gather inputs`** (lines 58-82): read spec/plan, run two `git` commands
  (`git log main..HEAD --oneline`, `git diff main..HEAD`), then a "Focus on" bulleted trigger
  list mapping diff categories to flags (lines 77-82). This is where a new "how to recognise a
  hard settings change" bullet would slot in most naturally, right after the existing
  `requires_settings_change` trigger line (79) and the check-ID note the plan wants
  (39-44 of `2. plan.md`) would sit as a related bullet or sub-note here too.
- **`## Step 3: Write upgrade_notes.md`** (lines 84-95): four prose-authoring rules ("Facts
  only," "Right altitude," what "Breaking changes" vs "Manual steps" should each contain) plus a
  closing "keep it short, honest 'no action needed' is fine" line. The rule at line 92
  ("Breaking changes — list anything a downstream project must change in their own code to stay
  working (renamed settings, removed template blocks, changed URLs, altered model fields)")
  is the closest existing analogue to a hard/soft distinction, but it is about *what belongs in
  the Breaking-changes prose section*, not about how to set the frontmatter flag, and it does not
  mention settings at all beyond "renamed settings" — nothing about "a setting that must be set or
  the app fails to boot" vs "a setting with a safe default."
- **`## Step 4: Tick the todo`** (lines 97-105): delegates to `sdd:sdd-mechanic` via a quoted
  instruction block, unrelated to the schema.
- **Tone/format**: terse, imperative, heavily bulleted; inline code for every field/flag name;
  em-dashes used for "field — one-line description" pattern throughout. Any new guidance should
  match this — short bullets, not new prose paragraphs, and reuse the `**`field`**` bold-code
  convention already used for every other flag.
- **Length**: 106 lines total, of which schema+semantics is 37 lines (10-46), Step 2 is 25 lines
  (58-82). A hard/soft guidance addition of a similar 5-10 line bullet block would keep the file's
  proportions consistent with its current density.

## 3. Real-world usage — every existing `upgrade_notes.md`

Fifteen files exist under `spec_dd/`, all under `spec_dd/3. done/` (none under `2. in progress/`
or elsewhere yet — this slice's own notes are "authored later in the SDD flow," per
`1. spec.md:40`, `2. plan.md:43`). Table below: spec, `requires_settings_change`, and
`changed_settings` content.

| Spec directory | `requires_settings_change` | `changed_settings` |
|---|---|---|
| `2026-07-09_09:37_fls-test-portability-part1` | `true` | 1 string: pytest marker registration note (`upgrade_notes.md:6-7`) |
| `2026-07-11_16:01_support-concrete-project-deployment-external-requirements-config` | `true` | 7 descriptive strings (INSTALLED_APPS, context processors, 6 env vars) (`:6-14`) |
| `2026-07-17_09:57_support-concrete-project-deployment-1-prod-settings` | `true` | 8 entries, several with inline `#` comments distinguishing "now mandatory — hard-fails at boot" (`SECRET_KEY`) from plain "new env var (default …)" entries (`:5-14`) |
| `2026-07-17_13:56_support-concrete-project-deployment-2-health-module` | `true` | 3 entries (`INSTALLED_APPS`, `SECURE_REDIRECT_EXEMPT`, optional `HEALTH_READINESS_CHECKS`) (`:6-9`) |
| `2026-07-17_14:02_course-details-page-accessable-to-registered-learners` | `false` | `[]` |
| `2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks` | `true` | `[TASKS, DATABASE_TASKS, INSTALLED_APPS]` — bare names, no comments (`:6`) |
| `2026-07-18_13:35_test_portability_2_conformance_suite` | `false` | `[]` |
| `2026-07-18_17:09_support-concrete-project-deployment-5-template-repo-scaffolding` | `false` | `[]` |
| `2026-07-19_07:52_more-deploy-preparation` | `true` | 5 entries, first marked "NEW required secret in production — app fails fast on boot if unset," rest marked "`.env.example` parity" with defaults (`:6-11`) |
| `2026-07-28_23:40_split-claude-plugin` | `false` | `[]` |
| `2026-08-21_09:09_organisations` | `true` | 1 entry (`INSTALLED_APPS`, conditional on maintaining own list) (`:11-12`) |
| `2026-08-21_14:12_make-qa-more-efficient` | `false` | `[]` |
| `2026-08-21_20:12_basic_reports` | `true` | 9 entries mixing one conditional `INSTALLED_APPS` line, one hard `STORAGES` requirement ("or reports land in `MEDIA_ROOT`"), and 6 plain "new, default …" config knobs (`:12-21`) |
| `2026-08-22_15:42_learner-terminology-rename` | `true` | 7 entries, all renames (`:42-49`) |
| `2026-08-23_16:23_fls-integration-system-checks` | `true` | 1 entry: `["SILENCED_SYSTEM_CHECKS"]` — no per-check-ID breakdown in the list itself, all detail lives in prose (`:5-6`) |

**Judgement: does the corpus already let a reader distinguish MUST from MAY?**

Yes, but only via **author discipline in prose and increasingly via inline YAML comments** — not
via anything the schema or command enforces. Evidence both ways:

- **Strongest supporting example**: `support-concrete-project-deployment-1-prod-settings` and
  `more-deploy-preparation` both put a hard entry and one-or-more soft entries in the *same*
  `changed_settings` list, distinguished only by a trailing `#` comment (`SECRET_KEY # now
  mandatory — hard-fails at boot if missing/empty` vs `DB_SSLMODE # new env var (default
  "prefer")`; `WEBHOOK_ENCRYPTION_SALT # NEW required secret...` vs `DJANGO_ADMIN_URL #
  .env.example parity...`). This is exactly the pattern D6 says is "sufficient" — and it already
  exists in the wild, unprompted by any command guidance. It is real proof the free-text field
  *can* carry the distinction.
- **Strongest contradicting/weak example**: `support-concrete-project-deployment-3-background-tasks`
  lists `[TASKS, DATABASE_TASKS, INSTALLED_APPS]` as three bare, uncommented names — despite the
  same file's prose stating one of the most operationally dangerous breaking changes in the whole
  corpus ("A worker process is now required in production... background work is accepted but
  never executes" — `upgrade_notes.md:26-29`). A reader who only skims the frontmatter list (which
  is exactly what `update_fls.md`'s automated preview table does — see §4) gets **zero** signal
  that this is a hard requirement; they'd have to read the prose in full. This shows the "free
  text already carries it" premise is **not currently reliable across authors** — it depends
  entirely on whether the individual author chose to annotate, and nothing in the current command
  tells them to.
- A second contradicting data point: `more-deploy-preparation` sets `requires_settings_change:
  true` for a list that is 4/5 purely optional parity additions with safe defaults ("no behaviour
  change if you leave them at their defaults" — `upgrade_notes.md:56-57`) alongside one genuinely
  hard entry. The boolean flag alone cannot distinguish "this spec has a hard requirement" from
  "this spec merely documented some new optional knobs" — a downstream reading only the flag (as
  `update_fls.md`'s preview table does) sees `requires_settings_change: true` in both a
  must-act case and a no-action-required case, with identical urgency implied.

**Verifying the "Part 1's own notes prove it" claim (`1. spec.md:32-35`):**

Read literally, "Part 1" = `fls-test-portability-part1` (confirmed as the sibling slice referenced
throughout this spec's revision note and idea.md's dependency list). Its `upgrade_notes.md`
(`spec_dd/3. done/2026-07-09_09:37_fls-test-portability-part1/upgrade_notes.md`) sets:

```yaml
requires_settings_change: true
changed_settings:
  - "pyproject.toml [tool.pytest.ini_options] markers: register the new fls_internal marker"
```

This is a **weak** proof of the specific claim. It shows `changed_settings` can hold a free-text,
non-bare-key description (true) — but it is not a hard-vs-soft example at all: the entry itself
carries no "required/optional" signal, and the file's own "Breaking changes" prose actually frames
the requirement as *conditional* ("if your downstream project collects the vendored `freedom_ls/`
test subtree... **and** your own `pyproject.toml` does **not** register `fls_internal`," line
22-24) rather than unconditionally hard. **Verdict: the citation is inaccurate/misleading as
written.** The claim that "the field is free-text and already carries the key list" is true of the
corpus in general, but the *specific* file cited is not where that's best demonstrated — the
`support-concrete-project-deployment-1-prod-settings` and `more-deploy-preparation` files (§3
above) are far stronger evidence, and the author of the guidance edit should probably cite those
instead, or at minimum verify which "Part 1" they mean before publishing the guidance text (this
research assumed `fls-test-portability-part1`, matching every other cross-reference in this
spec's own idea.md/spec.md; if a different "Part 1" was intended, the claim should be re-checked
against that file instead).

## 4. Consumption side

Grepped `requires_settings_change`, `changed_settings`, `upgrade_notes` across `claude_plugins/`.
Three consumers:

1. **`claude_plugins/fls-dev/commands/concrete/update_fls.md`** — the primary consumer, and the
   real test of D6.
   - Step 2 (lines 12-33): builds a **preview table** — "one row per spec — listing the spec name
     and the flags its notes set" (line 31). This is where a bare `requires_settings_change: true`
     with no hard/soft signal is most exposed: the preview is explicitly meant to let "the
     operator... see what is about to happen" (line 13) *before* touching anything, i.e. it is a
     risk-triage step, and today it cannot distinguish a must-act row from a some-day-optional row
     without the operator opening every `upgrade_notes.md` to read the prose.
   - Step 3a (lines 39-43): "Read... and parse its frontmatter flags. These drive which of the
     steps below actually run." Explicit fallback: if the file is absent, warn and fall back to
     prose-inference from spec/plan/diff (lines 43).
   - Step 3e (line 78): **the actual action** —
     `**`requires_settings_change`** → review and apply the listed `changed_settings` to the
     concrete project's `config/`.` This is deliberately vague/agentic: "review and apply" is a
     judgement instruction to whatever subagent runs this loop, not a mechanical `if key in dict`
     parse. The per-spec loop pseudocode at line 162 confirms this: `if
     notes.requires_settings_change: apply notes.changed_settings` — again, "apply," not any more
     specific machine action.
   - **Conclusion**: the one real consumer treats `changed_settings` as **prose read by an
     LLM/agent**, not as a structured list a script indexes into. This directly supports D6's
     premise — no parser in the repo needs the list machine-shaped, so a new flag would not unlock
     any new automation. The one place a new bool *could* help mechanically (Step 2's preview
     table, to sort/highlight must-act rows) is presentational, not functional, and could be
     achieved by asking the same subagent to read the prose and annotate the row — no schema
     change required.

2. **`claude_plugins/fls-dev/commands/update_template_repo.md`** — Step 3 (lines 37-60) reads
   `upgrade_notes.md` and maps `requires_settings_change` / changes under `config/` to specific
   template-repo files to edit (line 50). Same non-mechanical treatment — "map the changes," a
   judgement call for the subagent running the command.

3. **`claude_plugins/sdd/commands/README.md`** — pure documentation of the schema
   (lines 15, 112, 122, 124), no independent consumption logic. Line 124 already distinguishes
   `requires_template_review` (Django templates) from a *different* "template repo" concept —
   evidence the project is comfortable adding clarifying prose notes to this README/command family
   without adding new schema fields, i.e. precedent for exactly the kind of edit D6 proposes.

No other file in the repo (outside `spec_dd/*/upgrade_notes.md` bodies themselves) reads or
parses these fields. There is no Python code, no CI job, no test that consumes
`upgrade_notes.md` programmatically — everything is Claude-Code-agent prose consumption.

## 5. Gaps and risks

- **The "changed check ID is a hard settings change" case is genuinely uncovered today.** Neither
  the schema description (`update_upgrade_notes.md:41`) nor the Step 2 trigger list (lines 77-82)
  mentions system-check IDs, `SILENCED_SYSTEM_CHECKS`, or check re-IDs/splits as a category that
  should set `requires_settings_change`. The one existing precedent
  (`fls-integration-system-checks/upgrade_notes.md`, presumably "test_portability_3_system_checks")
  got this right, but purely through ad hoc author judgement, not because the command told them
  to. The plan's proposed guidance (`2. plan.md:39-41`) would be the **first place this is written
  down**, so it closes a real gap rather than restating existing guidance.
- **Directory/title mismatch on the worked-example spec.** The spec this slice's plan cites as the
  "E001 → E002" worked example lives at
  `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/`, but its own
  `upgrade_notes.md` is titled "Upgrade notes: test_portability_3_system_checks"
  (`upgrade_notes.md:14`). This spec's own idea.md/1. spec.md consistently refer to the dependency
  as "`test_portability_3_system_checks` (Layer 4)" (`idea.md:58`) and "that slice" — worth
  double-checking, when this slice's own guidance edit references the worked example, that it
  points at the right directory (the `2026-08-23_16:23_fls-integration-system-checks` one) rather
  than a literal `test_portability_3_system_checks` directory that does not exist under `3. done/`.
  Low risk (the content is unambiguous once found), but a stale/wrong path reference in the new
  guidance text would be embarrassing and easy to avoid by checking before writing it.
- **The preview-table risk noted in §4**: if the guidance only tells *authors* how to write hard
  vs soft distinctions into prose/comments, but `update_fls.md`'s Step 2 preview table still just
  prints "flags the notes set" without reading that nuance, the guidance could be *authored*
  correctly and still be invisible at the one point (the pre-flight preview) where it matters most
  for an operator deciding whether to proceed unattended. This slice's own scope explicitly
  excludes editing `update_fls.md`'s Step 2 preview logic — Layer 6 only adds a `manage.py check`
  / conformance-suite step to Step 3h/verification (`2. plan.md:49-53`), not a preview-table
  enrichment. That's a legitimate scope boundary, but worth the author being aware it's a gap they
  are consciously *not* closing in this slice.
- **The flag is still a single boolean even after this guidance lands.** D6 explicitly accepts
  this: a spec with one hard entry and four soft entries in the same list still reports
  `requires_settings_change: true` with no way to say "1 of these is mandatory, 4 are optional" at
  the frontmatter level — a downstream skimming just the boolean (rather than the annotated list)
  still can't triage severity without reading `changed_settings` in full. The guidance mitigates
  this by asking authors to annotate *within* the list (as the two strong precedent files already
  do informally) but does not — and, per D6, deliberately will not — expose severity as a separate
  machine field.
- **No enforcement mechanism.** Nothing checks that an author actually applies the new "mark
  hard vs soft" guidance — like the rest of this command, it's advisory prose for whichever agent
  runs `/update_upgrade_notes`, with no test or lint verifying frontmatter/prose consistency (e.g.
  no check that every `changed_settings` entry accompanied by "mandatory"/"required"/"fails at
  boot" language also appears named in the "Breaking changes" prose section, or vice versa).

## Open questions for the user

- Confirm which spec "Part 1" refers to in `1. spec.md:34` ("Part 1's own notes prove it"). This
  research assumed `fls-test-portability-part1` based on every other cross-reference in this
  slice's own `idea.md`/`1. spec.md`, and found that file's notes to be a weak/misleading citation
  for the specific claim being made (see §3). If a different file was intended, it should be
  re-verified; if `fls-test-portability-part1` was indeed intended, the guidance-writing step
  should consider citing `support-concrete-project-deployment-1-prod-settings` and/or
  `more-deploy-preparation` instead, since those are the files that actually demonstrate the
  hard-vs-soft-in-free-text pattern D6 relies on.

status: ok
