---
description: Validate FLS content offline, auto-fix obvious problems, and report the rest in plain language (no Python or uv knowledge needed)
allowed-tools: Read, Glob, Bash, Edit
---

## Steps

### 1. Resolve the target path

If `$ARGUMENTS` is non-empty, use it as the target path (file or directory).
If `$ARGUMENTS` is empty, use the current working directory as the target.

Expand the path to an absolute path before passing it to the validator.

### 2. Ensure the validator environment exists

The validator's dependencies are installed once by `/fls-content:init` into a dedicated
environment the plugin owns. Confirm it is present and healthy:

```bash
"${CLAUDE_PLUGIN_ROOT}/validate/.venv/bin/python" -c "import pydantic, yaml, frontmatter"
```

If that succeeds, go to Step 3.

If it fails (the author has not run `/fls-content:init` yet, or the environment is broken),
set it up yourself — do not ask the author to run anything. First check `uv` is available
(`uv --version`); if `uv` is missing, stop and tell the author to install it from
https://docs.astral.sh/uv/getting-started/installation/ (or ask their FLS administrator).
With `uv` present, create the environment:

```bash
uv venv "${CLAUDE_PLUGIN_ROOT}/validate/.venv"
uv pip install --python "${CLAUDE_PLUGIN_ROOT}/validate/.venv/bin/python" \
  pydantic pyyaml python-frontmatter
```

Never fall back to a bare `python` or `python3` invocation. Do not fail silently.

### 3. Run the bundled validator

Run the validator with the environment's Python:

```bash
"${CLAUDE_PLUGIN_ROOT}/validate/.venv/bin/python" \
  "${CLAUDE_PLUGIN_ROOT}/validate/validate.py" "<resolved-target-path>"
```

Capture both stdout and stderr; note the exit code.

### 4. Translate the result into plain language

**Exit 0 (success):**
Report to the author that the content passed the structural pre-flight check.
Example:

> All content files in `<path>` passed structural validation. No schema errors found.

**Non-zero exit (failures detected):**
Do **not** show the author a raw Python traceback. Instead, rewrite the
validator's human-readable output into friendly, actionable items:

- Identify each failing file by name (preserve any file-path references from the validator output).
- State what is wrong in plain language (missing required field, unknown field, wrong type, etc.).
- Tell the author how to fix it (e.g. "Add a `title:` field to the frontmatter of `01. intro.md`").
- Preserve any line-number or field references from the validator output.

If the validator output is empty on a non-zero exit (unexpected error), report
the exit code and ask the author to check the file path and re-run.

### 5. Auto-fix the obvious problems, then re-validate

For each reported failure, if the fix is **obvious and unambiguous**, just make it directly
in the source file — do not turn it into a task for the author. These are safe to fix:

- Malformed frontmatter / YAML syntax (bad indentation, missing `---`, unquoted value that
  breaks parsing).
- A typo'd or wrong-cased field name or `content_type` value (e.g. `tittle:` → `title:`,
  `content_type: topic` → `TOPIC`) where the intent is clear.
- An unknown field that is plainly a misspelling of a valid one.

Do **not** auto-fix anything that needs author judgement or could change meaning:

- Never write or edit a `uuid:`.
- Never invent prose, titles, or descriptions, and never make semantic widget decisions.
- A genuinely missing required value you cannot derive from the file's existing content —
  report it for the author to supply, do not guess.

After applying fixes, **re-run the validator** (Step 3) to confirm. Then report what you
fixed automatically and list anything that still needs the author to decide or supply.

### 6. Restate the boundary

End every response — success or failure — with this note (keeping it brief):

> **Note:** This is a structural pre-flight check only. It validates frontmatter
> schemas, required fields, and recognised content types. It does not perform the
> authoritative host-side processing (UUID assignment, icon resolution,
> cross-reference resolution, asset upload). A clean result here does not guarantee
> that later step will succeed, but it catches the most common structural mistakes first.
