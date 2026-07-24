---
description: Sync the fls-content course-author plugin if this SDD run touched FLS authoring functionality
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Agent
---

Sync the `claude_plugins/fls-content-plugin/` course-author Claude Code plugin to reflect any changes to FLS authoring functionality made by this SDD run. This command is a **fast no-op** when nothing authoring-relevant changed.

## Step 1: Detect authoring-relevant changes (zero-token)

Run the detection heuristic:

```bash
git diff main --name-only | grep -qE \
  '(freedom_ls/content_engine/schema\.py|freedom_ls/content_engine/validate\.py|freedom_ls/content_engine/templates/cotton/|config/settings_base\.py|freedom_ls/content_engine/management/commands/content_(save|validate)\.py|demo_content/)'
```

- **Exit code 1 (no match):** print `No authoring-relevant changes` and go directly to Step 4 (tick). No LLM, no fan-out.
- **Exit code 0 (match):** note the list of changed authoring-relevant files and proceed to Step 2.

## Step 2: Draft the plugin update (fan-out — on a match only)

Spawn **one `sdd:sdd-worker`** to read only the changed authoring-relevant files, identify exactly what changed, and draft scoped edits. Pass in the prompt:

- The list of changed authoring-relevant file paths from Step 1.
- Instruction to read those files and identify exactly what changed (new/removed/modified: content types, frontmatter fields, widget tags, `MARKDOWN_ALLOWED_TAGS` entries, `ADMONITION_TYPES` keys, convention examples in `demo_content/`).
- Instruction to produce a concrete, scoped set of edits to:
  - (a) the `fls-content` **reference skills** under `claude_plugins/fls-content-plugin/skills/` — kept shallow and author-facing; edit only the sections corresponding to changed files.
  - (b) the **bundled validator** under `claude_plugins/fls-content-plugin/validate/` — when `schema.py` or `validate.py` changed, detail what re-sync is required.
- Instruction to base every statement on the actual file contents, not inference.
- Instruction to write its output to `.sdd-work/fls_content_sync.md` and end the file with `status: ok` on success, `status: failed` + `reason:` on failure, or `status: blocked` + `needs:` if inputs are unclear.

Apply the standard resume/retry/blocked recipe:

- **Resume:** skip this unit if `.sdd-work/fls_content_sync.md` already exists and ends `status: ok`.
- **Retry (≤2):** on `status: failed`, re-spawn the same worker including the prior error.
- **Blocked:** on `status: blocked`, gather the listed `needs` via `AskUserQuestion`, then re-spawn with answers baked in.

## Step 3: Apply the edits (depth-0 synthesis)

Read `.sdd-work/fls_content_sync.md` by path. Apply the drafted edits to the relevant `claude_plugins/fls-content-plugin/` files:

- Use `Edit` for targeted section updates; use `Write` only if a file is new.
- **When `schema.py` or `validate.py` changed:** re-copy the trimmed validator from the FLS source and **re-apply both patches** (per D3.1 in the implementation plan):
  1. **Icon stub:** replace the body of `Course._validate_icon_fields` with `return self` (drop the deferred Django/icon import).
  2. **Import + `__main__` shim:** change `from .schema import SCHEMAS` → `from schema import SCHEMAS`; add the `if __name__ == "__main__":` entry point; fix the stale docstring to the `uv run` form; add the top-of-file bundled-copy comment.
- Touch **only** the affected sections — never rewrite the whole plugin and never add detail beyond what the source files express.

Delete `.sdd-work/` after all edits are applied:

```bash
rm -rf .sdd-work/
```

## Step 4: Tick the todo

Delegate the todo tick to `sdd:sdd-mechanic`. Spawn the mechanic with this instruction:

> Read the helper file at `claude_plugins/sdd-claude-plugin/commands/protected/update_todo.md` and follow its steps with:
> - `<todo-path>`: the `todo.md` in the spec directory for the current feature
> - `tick:"Run \`/update_claude_plugin_fls_content\` to sync the course-author plugin if authoring functionality changed"`

The mechanic edits `todo.md` directly.
