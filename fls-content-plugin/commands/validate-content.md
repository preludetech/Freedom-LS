---
description: Validate FLS content offline and report any problems in plain language (no Python or uv knowledge needed)
allowed-tools: Read, Glob, Bash
---

## Steps

### 1. Resolve the target path

If `$ARGUMENTS` is non-empty, use it as the target path (file or directory).
If `$ARGUMENTS` is empty, use the current working directory as the target.

Expand the path to an absolute path before passing it to the validator.

### 2. Check that `uv` is available

Run:
```bash
uv --version
```

If `uv` is not installed or not on `PATH`, stop here and tell the author:

> `uv` is not installed. The bundled validator requires `uv` to supply its
> dependencies ephemerally. Please install `uv` by following the instructions
> at https://docs.astral.sh/uv/getting-started/installation/ — or ask your
> FLS administrator to set up the environment.

Do **not** fall back to a bare `python` or `python3` invocation. Do not fail silently.

### 3. Run the bundled validator

Always invoke through `uv` — never use bare `python` or `python3` directly.
`uv` supplies `pydantic`, `pyyaml`, and `python-frontmatter` ephemerally with no
project setup required.

```bash
uv run --no-project --with pydantic --with pyyaml --with python-frontmatter \
  python "${CLAUDE_PLUGIN_ROOT}/validate/validate.py" "<resolved-target-path>"
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

### 5. Restate the boundary

End every response — success or failure — with this note (keeping it brief):

> **Note:** This is a structural pre-flight check only. It validates frontmatter
> schemas, required fields, and recognised content types. The authoritative pass —
> UUID assignment, icon resolution, cross-reference resolution, and asset upload —
> still happens via `content_save` on an FLS host. A clean result here does not
> guarantee `content_save` will succeed, but it will catch the most common
> structural mistakes before you reach the host.
>
> (See the `fls-content:markdown-conversion` skill for the full boundary description.)
