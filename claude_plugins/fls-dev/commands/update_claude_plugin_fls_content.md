---
description: Sync the fls-content course-author plugin if this SDD run touched FLS authoring functionality
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Agent
---

Sync the `claude_plugins/fls-content/` course-author Claude Code plugin to reflect any changes to FLS authoring functionality made by this SDD run. This command is a **fast no-op** when nothing authoring-relevant changed.

## Step 1: Detect authoring-relevant changes (zero-token)

Run the detection heuristic:

```bash
git diff main --name-only | grep -qE \
  '(freedom_ls/(content_base|content_engine|form_engine)/schema\.py|freedom_ls/form_engine/(enums|typed_answers)\.py|freedom_ls/content_engine/validate\.py|freedom_ls/content_engine/templates/cotton/|config/settings_base\.py|freedom_ls/content_engine/management/commands/content_(save|validate)\.py|demo_content/)'
```

- **Exit code 1 (no match):** print `No authoring-relevant changes` and go directly to Step 4 (tick). No LLM, no fan-out.
- **Exit code 0 (match):** note the list of changed authoring-relevant files and proceed to Step 2.

## Step 2: Draft the plugin update (fan-out — on a match only)

Spawn **one `sdd:sdd-worker`** to read only the changed authoring-relevant files, identify exactly what changed, and draft scoped edits. Pass in the prompt:

- The list of changed authoring-relevant file paths from Step 1.
- Instruction to read those files and identify exactly what changed (new/removed/modified: content types, frontmatter fields, `QuestionType` members, form-question field rules (`min`/`max`/`decimal_places` and the `question_bounds_error` checks), widget tags, `MARKDOWN_ALLOWED_TAGS` entries, `ADMONITION_TYPES` keys, convention examples in `demo_content/`).
- Instruction to produce a concrete, scoped set of edits to:
  - (a) the `fls-content` **reference skills** under `claude_plugins/fls-content/skills/` — kept shallow and author-facing; edit only the sections corresponding to changed files.
  - (b) the **bundled validator** under `claude_plugins/fls-content/validate/` — when any mirrored source changed (`content_base/schema.py`, `content_engine/schema.py`, `content_engine/validate.py`, `form_engine/schema.py`, `form_engine/enums.py`, `form_engine/typed_answers.py`), detail what re-sync is required.
- Instruction to base every statement on the actual file contents, not inference.
- Instruction to write its output to `.sdd-work/fls_content_sync.md` and end the file with `status: ok` on success, `status: failed` + `reason:` on failure, or `status: blocked` + `needs:` if inputs are unclear.

Apply the standard resume/retry/blocked recipe:

- **Resume:** skip this unit if `.sdd-work/fls_content_sync.md` already exists and ends `status: ok`.
- **Retry (≤2):** on `status: failed`, re-spawn the same worker including the prior error.
- **Blocked:** on `status: blocked`, gather the listed `needs` via `AskUserQuestion`, then re-spawn with answers baked in.

## Step 3: Apply the edits (depth-0 synthesis)

Read `.sdd-work/fls_content_sync.md` by path. Apply the drafted edits to the relevant `claude_plugins/fls-content/` files:

- Use `Edit` for targeted section updates; use `Write` only if a file is new.
- **When any mirrored source changed** (the six paths listed in Step 2b): re-copy the trimmed validator from the FLS sources and **re-apply every patch listed in the `# Patches applied:` header of `claude_plugins/fls-content/validate/schema.py` and of `claude_plugins/fls-content/validate/validate.py`**. Those two headers are the authoritative patch list — read them before editing, and add a numbered entry there for any new patch. Do not rely on a list duplicated here: one kept drifting out of date, which is the same failure this command exists to catch.
- Note that `validate/schema.py` bundles **four** sources, not one: `content_base/schema.py`, `content_engine/schema.py`, `form_engine/schema.py`, and a hand-ported mirror of `form_engine/typed_answers.question_bounds_error`.
- Touch **only** the affected sections — never rewrite the whole plugin and never add detail beyond what the source files express.

Delete this command's scratch file after all edits are applied, naming it explicitly and letting the
wrapper drop the directory once it is empty:

```bash
.claude/fls-dev/scripts/delete_sdd_work_files.sh --prune-empty .sdd-work/fls_content_sync.md
```

`--prune-empty` removes the directory with `rmdir`, which only ever removes an **empty** directory,
so a concurrent SDD command's scratch files survive and the prune is skipped with a notice. Never
wipe `.sdd-work/` wholesale: it is shared with other SDD commands, and a recursive force-delete is
blocked by the `security-guard` PreToolUse hook.

## Step 4: Tick the todo

Delegate the todo tick to `sdd:sdd-mechanic`. Spawn the mechanic with this instruction:

> Read the helper file at `claude_plugins/sdd/commands/protected/update_todo.md` and follow its steps with:
> - `<todo-path>`: the `todo.md` in the spec directory for the current feature
> - `tick:"Run \`/update_claude_plugin_fls_content\` to sync the course-author plugin if authoring functionality changed"`

The mechanic edits `todo.md` directly.

## Step 5: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `sync the fls-content author plugin`. Tell it to stage the edited files under
`claude_plugins/fls-content/` and the `todo.md` in the spec directory.

If Step 1 found no authoring-relevant changes, there is nothing to stage beyond the todo tick.
