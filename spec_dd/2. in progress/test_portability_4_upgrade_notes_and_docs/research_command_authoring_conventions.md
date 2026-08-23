# Research: command authoring conventions

## Summary

- The `sdd:claude-code-authoring` skill (`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`) is
  almost entirely about **subagent/fan-out/model-tiering mechanics** (no nesting, no `SlashCommand` in
  subagents, model resolution order, the depth-0 fan-out recipe). It says **nothing** about command
  front-matter fields, `$ARGUMENTS`, imperative voice, or length — those conventions have to be read off
  the repo's existing command files by example, not off this skill's prose.
- Both target files need **no fan-out** and run at **depth 0 with no subagents** — `update_upgrade_notes.md`
  says this explicitly (`update_upgrade_notes.md:8`); `update_fls.md` uses a per-spec **subagent loop**
  ("use a subagent to do the following", `update_fls.md:37`), so its per-spec body is *itself* the kind of
  helper a subagent reads-and-follows, not a slash command a subagent could invoke — no skill rule is
  implicated by adding two verification steps inside that loop.
- **Front-matter convention observed across every top-level `fls-dev` command:** `description:` +
  `allowed-tools:` (see e.g. `update_upgrade_notes.md:1-4`, `update_template_repo.md:1-4`,
  `plan_structure_review.md:1-4`). `argument-hint:` appears only on commands that take arguments
  (`do_qa.md:3`, `update_todo.md:4`). **No top-level command sets `model:`** — that field lives only on
  spawnable **agent** `.md` files (`sdd-worker.md`, `sdd-mechanic.md`, `qa-data-helper.md`, etc.), per the
  skill's "Inline-execution caveat" (`SKILL.md:50-52`): a file that is read-and-followed, not spawned,
  keeps the caller's model, so `model:` on it would be inert.
- **`update_fls.md` (`commands/concrete/update_fls.md`) has *no* YAML front matter at all** — no
  `description:`, no `allowed-tools:`. Confirmed by grep: zero `^---$` lines in the file. This is an
  outlier versus every other command in the plugin (all of which open with a front-matter block). It is
  pre-existing and out of scope for this slice's edit, but worth flagging to the user as an inconsistency
  (see "Anti-patterns" below) rather than silently perpetuating or "fixing" it.
- **`$ARGUMENTS`/`$1` is a real, used convention elsewhere** (`do_qa.md:16`, `format-content.md:11`,
  `validate-content.md:10-11`, `threat-model.md:1`, `security-review.md:9`) but **neither target file uses
  it** — both self-locate the spec directory from the branch name instead (`update_upgrade_notes.md:48-56`,
  `update_template_repo.md:12-20` is the sibling pattern; `update_fls.md` needs no spec-dir lookup at all,
  it walks the submodule's own completed-spec directories). The planned edits must not introduce arguments;
  they extend existing step bodies.
- **`commands/concrete/` commands run inside downstream projects**, confirmed by
  `commands/concrete/README.md:1` ("specifically for concrete implementations of FLS... typically include
  FLS as a submodule") and by `update_fls.md`'s own content (it operates on `submodules/Freedom-LS`, the
  concrete project's own `config/`, `package.json`, etc. — paths that only exist in a downstream checkout).
  This means the file **must never reference this repo's own `spec_dd/` layout, FLS's own dev-only tooling
  paths, or FLS-internal test markers** as if the downstream had them — everything it names must exist in
  a *concrete* FLS project.
- The **conformance suite is confirmed shipped and downstream-invokable**: `freedom_ls/contrib/conformance/`
  exists (test_theme.py, test_urls.py, test_settings.py, test_migrations.py) and
  `docs/product/configuration-and-extension.md:92-96` describes it as "an importable module a downstream
  project brings into its own test suite" — i.e. the downstream must have **already wired it into their own
  `tests/`** for a "run the conformance suite" step to have anything to invoke. That wiring is explicitly
  **not yet shipped** to the template (spec `1. spec.md:61-67`, `95-100` — it's `/update_template_repo`'s
  SDD-step-12 job). This is the single biggest correctness risk in the Layer-6 edit — see "Cross-file
  consistency" below.
- **The port pattern is safe to reference** in a downstream-run command: `/fls-dev:init` **requires**
  `/ds:init` to have already run (`commands/init.md:41`, enforced at `commands/init.md:110-112`, P3), so any
  concrete project with `fls-dev` initialised also has the `django-stack` (`ds`) plugin initialised, and
  therefore has `.claude/ds/scripts/find_available_port.sh` (`commands/do_qa.md:155`,
  `commands/README.md:89-91`). The template repo's shipped tree doesn't list `.claude/ds/` because it's
  created by `init`, not by the template itself (same pattern as `.claude/fls-dev/config.local.md`,
  `resources/template_repo_manifest.md:72`).
- **`update_product_docs.md:35-41`** carries a worked anti-pattern that is directly on-topic for this
  slice's "hard vs soft settings change" guidance: it shows a 186-word system-checks section that named
  check IDs and instructed a `SILENCED_SYSTEM_CHECKS` migration in the *product docs*, and explains that
  instruction belongs in `upgrade_notes.md`, not there. That's independent confirmation that "an E001→E002
  re-ID is itself a hard settings change a downstream must react to" is the right home for the guidance
  being added to `update_upgrade_notes.md` — and a caution not to duplicate that prose into
  `configuration-and-extension.md` as part of this slice (the spec already excludes that, `1. spec.md:81-88`).

---

## 1. The `sdd:claude-code-authoring` skill

Read: `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md` and its four `resources/*.md` files
(`subagents.md`, `model_tiering.md`, `fanout_recipe.md`, `interactive_cli.md`).

**What the skill actually covers** (front-matter `SKILL.md:1-8`: triggers on "writing/editing a slash
command, skill, or agent definition... choosing a model tier... how Claude Code
subagents/skills/models behave"):

- **No nesting / no fan-out from a subagent** (`SKILL.md:27-29`, `resources/subagents.md:1-8`): the `Agent`
  tool isn't exposed at depth 1. All fan-out must happen at depth 0.
- **Subagents can't type slash commands** (`SKILL.md:30-33`, `resources/subagents.md:10-16`): "Headline
  rule: prefer skills (or 'read-and-follow this helper file') to slash commands for any reusable logic a
  subagent must run." — This is why `update_fls.md` phrases its per-spec work as "use a subagent to do the
  following" (`update_fls.md:37`) followed by literal step prose, rather than telling the subagent to run
  `/some-other-command`.
- **Spawn-time input only** (`SKILL.md:34-36`): irrelevant here — neither edit changes spawn prompts.
- **Subagents can't ask the user** (`SKILL.md:37`): irrelevant — neither target file's edit adds
  `AskUserQuestion` inside a subagent-run section. (`update_fls.md` does use `AskUserQuestion` but only at
  its own depth-0 preview gate, Step 2, "Present the preview and let the operator confirm" — not inside the
  per-spec subagent loop.)
- **Agent `.md` frontmatter** (`SKILL.md:40-43`, `resources/subagents.md:34-40`): `name` + `description`
  required, `model` optional, resolution order `CLAUDE_CODE_SUBAGENT_MODEL` → per-spawn `model` param →
  frontmatter `model` → parent's model. **This is agent-file frontmatter, not slash-command frontmatter** —
  it does not directly constrain what fields `update_upgrade_notes.md`/`update_fls.md` (both plain
  commands, not agents) should carry. Neither target file spawns a persistent named subagent of its own;
  `update_upgrade_notes.md` spawns the generic `sdd:sdd-mechanic` agent for its todo-tick step
  (`update_upgrade_notes.md:99-105`), which already carries its own `model:` frontmatter elsewhere.
- **Model tiering** (`SKILL.md:45-56`, `resources/model_tiering.md`): the reliable knob is per-agent
  `model:` frontmatter; a file that is *read and followed inline* (not spawned) keeps the caller's model,
  so putting `model:` on either target command would be inert — neither currently has one, and neither
  edit should add one.
- **Fan-out recipe** (`SKILL.md:58-70`, `resources/fanout_recipe.md`): the 7-step resilience recipe (one
  output file per unit, resume = skip on `status: ok`, structured returns, synthesis as a separate step,
  clean up scratch). **Not implicated** by either edit — `update_upgrade_notes.md` explicitly opts out of
  fan-out for its single-file output (`update_upgrade_notes.md:8`), and the new verification steps in
  `update_fls.md` are added *inside* the existing per-spec subagent body (§3h), not as new fan-out.
- **Interactive-CLI notes** (`SKILL.md:72-80`): `AskUserQuestion` is orchestrator-only; no enforced
  structured JSON output in the CLI subagent path, so file-based hand-off with a `status:` footer is the
  durable contract. Not implicated by either edit.

**What the skill does *not* cover, that the task asked about:** front-matter field semantics
(`description`, `argument-hint`, `allowed-tools`), `$ARGUMENTS`/`$1` mechanics, length guidance, imperative
voice, or explicit prose anti-patterns for command bodies. None of these appear anywhere in `SKILL.md` or
its four resource files. They are **repo conventions inferred from sibling command files** (§2/§3 below),
not skill-documented rules. If the plan intends the skill to be "the source of the rules" for these edits,
the accurate framing is: the skill governs the **subagent/fan-out shape** the edits must not violate (they
don't touch it), while the **prose/structure conventions** come from matching the two files' own existing
idiom and the sibling commands' shared style.

---

## 2. The two target files as they stand

### `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (106 lines)

- **Front matter** (`:1-4`): `description: Author the structured upgrade_notes.md for downstream FLS
  projects` and `allowed-tools: Read, Write, Glob, Edit, Bash, Agent`. No `argument-hint` (takes no
  arguments — self-locates via branch name), no `model`.
- **Structure:** opens with a one-sentence purpose statement + a "runs at depth 0... no fan-out" note
  (`:6-8`, no H1 title), then H2 sections: `## upgrade_notes.md schema` (`:10`), `## Step 1: Locate the
  spec directory` (`:48`), `## Step 2: Gather inputs` (`:58`), `## Step 3: Write upgrade_notes.md` (`:84`),
  `## Step 4: Tick the todo` (`:97`).
- **The schema block** (`:14-46`) is a fenced YAML+markdown template followed by a flag-by-flag "Flag
  semantics" bullet list (`:37-46`). `requires_settings_change` is currently defined in one sentence
  (`:41`): "new or renamed settings keys. List them in `changed_settings`." — this is the exact spot the
  D6 hard/soft guidance is meant to extend (either inline here, or as new prose in Step 2/Step 3 that
  references this flag; the plan doesn't mandate which, see plan `2. plan.md:31-37`).
- **Voice:** pure second-person imperative addressed to the executing agent — "Find the spec directory...",
  "Read these files...", "Write `<spec-dir>/upgrade_notes.md`..." Never narrates *why* to a human reader
  except in brief parentheticals.
- **Existing "facts only" / altitude guidance already in the file** (`:88-95`) is the closest in-file
  precedent for how to phrase new guidance: "**Facts only.** Base every statement on the spec, the plan,
  and the actual diff. Do not speculate." / "**Right altitude.** ... Name settings, migration commands, and
  template paths explicitly when relevant. Skip internal implementation details they don't need." / "Keep
  the prose short and actionable... an honest 'no action needed' is more useful than padding." New D6
  guidance should match this bolded-lead-in-plus-one-or-two-sentence shape, not add a long new subsection.
- **Step 4 pattern** (`:97-105`) is boilerplate all fls-dev commands share: delegate the todo tick to
  `sdd:sdd-mechanic` with a block-quoted instruction naming the helper file and exact tick text. Not
  touched by this edit but worth preserving verbatim if the edit shifts line numbers around it.

### `claude_plugins/fls-dev/commands/concrete/update_fls.md` (172 lines)

- **Front matter: none.** The file starts directly at line 1 with plain prose ("Update the FreedomLS
  submodule..."). No `description`, `allowed-tools`, or `argument-hint`. This is the one command in the
  whole plugin tree with zero YAML front matter (confirmed by grep — every other file opens with `---`).
- **Structure:** opens with a 3-sentence purpose paragraph (`:1-3`, no H1), then **H1** (`# `) major
  sections — `# Step 1: Identify new completed specs` (`:5`), `# Step 2: Dry-run preview (no changes yet)`
  (`:12`), `# Step 3: Integrate each spec sequentially` (`:35`) with **H2** (`## `) substeps `## 3a.` …
  `## 3i.` (`:39,45,55,63,73,84,90,100,110`), `# Step 4: Final sync` (`:116`), `# Rollback: recovering from
  a spec that fails mid-integration` (`:124`), `# Per-spec loop (reference)` (`:152`, a fenced pseudocode
  block, `:154-171`).
- **This H1-for-steps convention is unique to this file** — `update_upgrade_notes.md` and every other
  fls-dev command use `##` for their top-level steps. An inserted verification step should match **this
  file's own** heading level (H2, since it's a substep of `## 3h. Verify` or a sibling of `3a`–`3i`), not
  the sibling command's convention.
- **Voice:** also second-person imperative to the executing agent, but with more explicit "why" asides
  than `update_upgrade_notes.md` (e.g. `:80` explains *why* npm install must run before Tailwind rebuild).
  Comfortable with longer prose paragraphs per step than the terser `update_upgrade_notes.md`.
- **Exact insertion point for this slice's edit:** `## 3h. Verify` (`:100-108`). Currently:
  ```
  Run the portable contract test set and confirm everything passes...
  uv run pytest -m "not playwright and not fls_internal and not ci_only"
  If there are front-end changes, use the Playwright MCP to verify things work visually.
  ```
  The plan's two additions — invoke the conformance suite, run `manage.py check` — land here. Three other
  bare-pytest call sites exist that are **explicitly out of scope** (already switched to marker selection
  by Part 1, plan says "leave those alone", `2. plan.md:53-54`): `update_fls.md:122` (Step 4 final sync),
  `update_fls.md:147` (Rollback step 4 confirmation), and `update_fls.md:168` (the `# Per-spec loop
  (reference)` pseudocode mirror of 3h). **Consistency risk to flag for the implementer:** the reference
  pseudocode block at `:152-171` mirrors every step in prose form (`:161` mirrors `requires_settings_change`
  handling, `:167-168` mirrors the verify gate) — if `manage.py check`/conformance-suite lines are added to
  3h's prose but not mirrored into this block, the block silently goes stale versus the steps it claims to
  summarise. The plan text itself doesn't mention the reference block, so this is a gap worth the
  implementer's attention even though it's not literally one of the two "call sites to touch."

---

## 3. Plugin layout

`claude_plugins/fls-dev/` structure (confirmed via `Glob`):

- `.claude-plugin/plugin.json` — minimal manifest: `name`, `version`, `description` only
  (`claude_plugins/fls-dev/.claude-plugin/plugin.json:1-5`). **No explicit `commands` glob or list** — this
  plugin relies on Claude Code's directory-convention auto-discovery of `commands/**/*.md`, which is why
  `commands/concrete/update_fls.md` (nested one level deep, no front matter) still functions as a command
  despite being structurally unlike its siblings.
- `commands/` — top-level commands run **in the FLS repo itself** (in-repo SDD workflow: `do_qa.md`,
  `update_product_docs.md`, `update_upgrade_notes.md`, `update_template_repo.md`,
  `update_claude_plugin_fls_content.md`, `plan_security_review.md`, `plan_structure_review.md`, `init.md`).
- `commands/concrete/` — commands that run **inside a downstream concrete project**, confirmed by
  `commands/concrete/README.md:1`: "These commands are specifically for concrete implementations of FLS.
  They typically include FLS as a submodule." Currently holds exactly one command (`update_fls.md`) plus
  the README.
- `skills/` — 13 `SKILL.md` dirs (app-settings, alpine-js, frontend-styling, icon-usage, admin-interface,
  git-worktree-setup, markdown-content, playwright-tests, multi-tenant, registration, use-playwright,
  testing, template).
- `resources/` — shared reference files a command or skill can `Read` (e.g. `template_repo_manifest.md`,
  `email_templates.md`).
- `agents/` — spawnable agent `.md` files (`qa-data-helper.md`, `qa-bugfixer.md`), which do carry `model:`
  frontmatter, unlike commands.
- `scripts/`, `templates/` (wrapper-script templates for `init`), `resources/launcher_editing.md`,
  `resources/wrapper_script_migration.md` — plumbing for `/fls-dev:init`.

**`commands/concrete/` vs top-level — the constraint this puts on wording:**

`update_fls.md` operates entirely on a **downstream project's own checkout**: `submodules/Freedom-LS`
(the FLS submodule, read-only from the downstream's perspective), the downstream's own `config/`,
`package.json`, `package-lock.json`, `uv.lock`. It must therefore:

- **Never assume this FLS repo's own paths** — no `spec_dd/`, no `claude_plugins/`, no FLS's own
  `freedom_ls/contrib/conformance/` source path as if it were locally editable; only as an *importable
  package* the downstream's own `tests/` may reference (`from freedom_ls.contrib.conformance import ...`),
  confirmed by `docs/product/configuration-and-extension.md:94` ("an importable module a downstream project
  brings into its own test suite").
- **Never assume FLS-repo-only dev tooling** unless that tooling is confirmed to exist downstream too. The
  port-finder script (`.claude/ds/scripts/find_available_port.sh`) is safe (see Summary bullet — `ds` is a
  hard prerequisite of `fls-dev:init`), but anything that is FLS-repo-specific CI/dev config (e.g. this
  repo's own `pyproject.toml` test markers, `conftest.py` fixtures, or `demo_content/`) must not be assumed
  present in a downstream project's own test tree.
- **Never assume FLS's own internal test markers exist downstream** unmodified — the existing
  `-m "not playwright and not fls_internal and not ci_only"` calls already correctly frame this as *the
  concrete project's own suite*, deselecting **FLS's** browser/internal/slow tests (`update_fls.md:102-105`
  comment). Any new verification instruction must keep this framing: it's testing the *downstream's*
  wiring, invoking things the *downstream* has (or is told to set up), not restating FLS-repo-internal
  commands.
- **The conformance-suite step specifically must be conditional**, not unconditionally invoked — see §4
  below, since the wiring it depends on isn't shipped to new projects yet.

---

## 4. Cross-file consistency risk

Checked `commands/update_template_repo.md`, `resources/template_repo_manifest.md`, and the `fls-dev`
skills for anything already saying something about `manage.py check`, the conformance suite, or
settings-change classification.

- **`resources/template_repo_manifest.md`** — the `urls.py` checklist is confirmed out of sync with
  `config/urls.py` (per this slice's own idea/plan, and independently observable: the manifest's tree
  listing has no `tests/` entry importing the conformance suite, and its `.claude/` block lists only
  `settings.json`, no test-wiring notes). **This file is explicitly out of scope for this slice** (idea.md
  and 2. plan.md are unambiguous: "the actual manifest edit is `/update_template_repo`'s job... do not
  pre-empt it"). Confirms the plan's own ground truth — nothing further to add here except: **this is the
  reason the new `update_fls.md` conformance-suite step must be phrased conditionally** ("if the project has
  wired the conformance suite into its own tests, run it" / "check whether `tests/` imports
  `freedom_ls.contrib.conformance`; if not, note it as an available signal it hasn't adopted yet") rather
  than as an unconditional call site like the existing `pytest -m "..."` lines. A downstream created from
  today's template has **no such wiring** until SDD step 12 lands it, so an unconditional invocation would
  either be a dead reference or, worse, a plausible-sounding fabricated command name if the model guesses
  at file paths.
- **`commands/update_template_repo.md`** — no mention of `manage.py check` or the conformance suite
  anywhere in its body (checked via targeted grep across all of `claude_plugins/`). It does read
  `upgrade_notes.md` frontmatter (`update_template_repo.md:39-44`) the same way `update_fls.md` does, and
  its signal→file table (`update_template_repo.md:48-55`) is the place a *future* conformance-suite/`tests/`
  scaffolding row would go — but that's SDD-step-12 work, per spec `1. spec.md:61-67`, not this slice.
  **No edit needed here for this slice.**
- **`fls-dev` skills** — grep across all `fls-dev` (and `django-stack`) skills for
  `manage.py check|conformance|SILENCED_SYSTEM_CHECKS|system check` found only:
  - `django-stack/skills/app-settings/SKILL.md:100-103` — general "required setting → system check, not a
    raise at import" guidance (developer-facing, about *writing* checks, not about upgrade verification).
    Not in conflict; different audience/purpose.
  - `django-stack/commands/security-review.md:8` — `manage.py check --deploy` as one of *its* review steps
    (a different command, different purpose — deploy-security checks, not upgrade verification). No overlap
    requiring edits.
  - `fls-dev/commands/update_product_docs.md:37,41` — the "Boot-Time System Checks" before/after example
    (discussed in Summary). This is **prose precedent**, not a place requiring a code/content change for
    this slice, but it does establish that check-ID-level detail (`E001`→`E002`) belongs in
    `upgrade_notes.md`, reinforcing that `update_upgrade_notes.md` (not `configuration-and-extension.md`)
    is the right file for the D6 guidance — consistent with what this slice is already doing.
- **No other place already states a hard/soft settings-change distinction** — grepped
  `hard.*settings|required settings change|optional.*informational|hard-required|hard/required` across the
  repo; only hits were this slice's own idea/plan/spec files and unrelated matches
  (`frontend_styling.md`, `django-stack/skills/testing/SKILL.md` — neither is about settings
  classification). **Confirms no duplicate-guidance risk**: the D6 language is genuinely new and has
  exactly one home.

**Conclusion:** no other plugin file needs a matching edit for this slice's two changes to stay consistent.
The one dependency to get right is **making the `update_fls.md` conformance-suite step conditional on the
downstream having wired it in**, so it doesn't silently assume SDD-step-12 has already landed.

---

## 5. Anti-patterns to avoid in these specific edits

- **Unconditionally invoking the conformance suite as if every downstream already has it wired.** Per §4,
  the template doesn't ship the `tests/` wiring yet. Phrase the new verification bullet as a check-then-run
  ("if the project's `tests/` imports `freedom_ls.contrib.conformance`, run it as part of the test gate;
  if not, note that it's available and point at `docs/product/configuration-and-extension.md`'s
  Conformance Suite section") rather than adding a bare, unconditional command line the way the existing
  `pytest -m "..."` calls are bare.
- **Referencing this repo's internal `spec_dd/` paths from `update_fls.md`.** It already avoids this
  correctly today (it only reads `submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/upgrade_notes.md`,
  which is *inside the submodule*, i.e. legitimately downstream-visible). Keep the new steps scoped the
  same way — nothing in the new steps should reference this worktree's own `spec_dd/2. in progress/...`.
- **Hardcoding port 8000, or inventing a port-finder path that doesn't exist downstream.** If a runserver
  step is added for the Playwright-visual-check line (`update_fls.md:108`), it must use
  `.claude/ds/scripts/find_available_port.sh` (confirmed present, §Summary) exactly as `do_qa.md:151-168`
  does — read the printed port and substitute the **literal value** into subsequent commands, since shell
  variables don't survive across Bash calls (`do_qa.md:157-159`). Currently `update_fls.md` has **no
  runserver step at all**, so this only matters if the implementer chooses to add one; if the verification
  addition stays to `manage.py check` + conformance suite (both non-server commands), the port-pattern note
  in the plan may end up moot — don't manufacture a runserver step just to exercise it.
- **Burying `manage.py check` after the pytest line where a reader skims past it, or making it a passive
  aside.** Both target files' existing convention is one imperative sentence + a fenced/backticked command
  per action (e.g. `update_fls.md:94-98` "Post-flight conflict check" is its own clearly labelled
  paragraph). Give the system-check step the same visual weight as the existing pytest line, not a trailing
  clause tacked onto it.
- **Forgetting the `# Per-spec loop (reference)` pseudocode block** (`update_fls.md:152-171`). It exists
  specifically to mirror every step above it in condensed form; a verification-step edit that updates only
  §3h's prose but not the `:167-168` mirror leaves that block silently wrong about what the verify gate
  actually runs. This isn't one of the plan's named call sites, but skipping it would violate the file's
  own internal contract (the block's own heading calls itself a "reference" for the steps above).
- **Duplicating the D6 guidance into `docs/product/configuration-and-extension.md`.** The spec explicitly
  excludes this (`1. spec.md:81-88` — "Not in scope... already shipped as
  `claude_plugins/fls-dev/skills/app-settings/SKILL.md`... the correct venue"), and `update_product_docs.md`
  independently confirms the routing rule ("wrong artifact" prong, `update_product_docs.md:25`: "upgrade,
  migration and breaking-change content → `/update_upgrade_notes`"). Keep the new guidance entirely inside
  `update_upgrade_notes.md`.
- **Writing the hard/soft distinction as a long new subsection instead of extending existing prose.**
  `update_upgrade_notes.md`'s established idiom is dense bolded-lead-in bullets (`:37-46`, `:88-95`), not
  worked examples with before/after blocks (that heavier style belongs to `update_product_docs.md`, a
  different command with a different, more editorial job). Match the terser sibling-file idiom: extend the
  existing `requires_settings_change` bullet (`:41`) and/or Step 2's settings-detection guidance (`:79`)
  with one or two more sentences, plus the check-ID-is-also-a-hard-change note the idea file already
  drafted (`idea.md:39-41`) as a short paragraph, not a new `##` section.
- **Adding `model:` or `argument-hint:` front matter to either file "for consistency."** Neither change is
  in scope: `update_fls.md` has no front matter at all today and this slice's task doesn't ask for adding
  any; `update_upgrade_notes.md`'s existing front matter (`description` + `allowed-tools`) needs no new
  fields for a prose-only content edit. Adding fields not requested would be scope creep beyond "add
  guidance" / "add verification steps."
- **Changing the three untouched `pytest -m "..."` call sites** (`update_fls.md:122,147,168` besides the
  mirror concern above) — the plan is explicit these are Part-1's already-correct work and must be left
  alone (`2. plan.md:53-54`). Touch only §3h's verification block (plus, per the point above, the
  reference-block mirror of §3h specifically — not the other two unrelated pytest call sites).

---

## Open questions for the user

- Should the new `update_fls.md` conformance-suite step be **unconditional prose that documents the
  condition** ("run it if the project has wired it in; note it's available otherwise") or should it also
  update the Step 2 preview table / Step 3a upgrade-notes read to explicitly surface "conformance suite:
  wired / not wired" as a per-spec signal? The plan doesn't specify this level of detail, and §4 above
  argues for at least a conditional phrasing given the template's `tests/` wiring hasn't shipped yet.
- Should the `# Per-spec loop (reference)` pseudocode block (`update_fls.md:152-171`) be updated to mirror
  the new verification lines, even though the plan's two named call sites don't include it? Leaving it
  stale is a real (if minor) internal-consistency defect in the file; updating it is a small, contained
  addition to the same edit.
- `update_fls.md`'s complete absence of YAML front matter is a pre-existing oddity unrelated to this
  slice's scope — worth a one-line heads-up to the user in case they want it tracked as a separate cleanup
  item, but this research does not recommend touching it as part of this slice.

status: ok
