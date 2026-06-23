---
description: Scaffold .fls-content.yaml and install the validator's dependencies (non-destructive, safe to re-run)
allowed-tools: Read, Write, Glob, Bash
---

## Steps

### 1. Resolve the content root

If `$ARGUMENTS` is non-empty, use it as the content root directory.
If `$ARGUMENTS` is empty, use the current working directory.

Expand to an absolute path.

### 2. Check whether `.fls-content.yaml` already exists

Use the `Glob` tool to check for `<content-root>/.fls-content.yaml`.

**Important:** `.fls-content.yaml` is a hidden (dot-prefixed) file. Ensure the glob pattern
matches it explicitly — pass the full literal filename, not just `*`. A false "not found"
result here would cause Step 4 to overwrite an existing file, violating the non-destructive
guarantee.

---

**If the file already exists — go to Step 3.**

**If the file is absent — go to Step 4.**

---

### 3. File already exists — report and exit without writing

Read the existing `.fls-content.yaml`. Parse the `admonition_types` list **and** the
`access_types` list from the file content you just read. Compare each against its FLS base
set and report both groups for each. Do **not** copy the example values below — compute the
splits from the actual file.

- `admonition_types` FLS base names: `note`, `tip`, `important`, `warning`, `danger`,
  `key_takeaways`, `checklist`.
- `access_types` FLS base names (the shipped `COURSE_ACCESS_BACKEND` vocabulary): `free`,
  `application_gated`. If the file has no `access_types` key at all, note that the repo
  predates this config and the validator will fall back to the FLS shipped default — suggest
  adding an `access_types` block (see Step 4) so the valid set is explicit.

Report:

1. That the file is already present and has been left **byte-for-byte untouched**.
2. A convenience cross-reference of each declared list against its FLS base set. Frame this
   as informational only — differences from the base set are expected and intentional (the
   file is the authoritative set, not the base set).

Example report format:

> `.fls-content.yaml` already exists at `<path>` — no changes made.
>
> Your declared `admonition_types` compared to the FLS base set:
> - Also in FLS base set: `note`, `tip`, `warning`, `danger`, `key_takeaways`, `checklist`
> - In your config but not in the FLS base set: `regulation`
> - In the FLS base set but not in your config: `important`
>
> Your declared `access_types` compared to the FLS shipped set:
> - Also in FLS shipped set: `free`
> - In the FLS shipped set but not in your config: `application_gated`
>
> This is informational only — your config is the authoritative set for this repo and may
> intentionally differ from the FLS base set.

Do **not** merge, reorder, overwrite, or delete anything. Then continue to Step 5.

### 4. File is absent — create it

Write the following content verbatim to `<content-root>/.fls-content.yaml`:

```yaml
# .fls-content.yaml — deployment-specific FLS authoring config
#
# This file declares the admonition types available in this content repository.
# The list below is the COMPLETE, AUTHORITATIVE set of valid types for this repo —
# not "base types plus extras". Edit it freely: add, remove, or rename types to
# match your deployment's ADMONITION_TYPES configuration.
#
# The FLS base set (from config/settings_base.py) is pre-populated here as a
# starting template. It is fully overridable — a deployment may add new types,
# remove types from this list, or rename them entirely.
#
# After editing, the declared types here are what /fls-content:format-content
# and the fls-content:widget-reference skill will treat as valid for this project.
# Any type not listed will be flagged (rather than silently emitted) during
# conversion.

admonition_types:
  - note            # neutral aside or extra context
  - tip             # helpful suggestion or shortcut
  - important       # something the reader must not miss
  - warning         # caution — risk of a mistake or pitfall
  - danger          # severe risk — serious consequences if ignored
  - key_takeaways   # summary of the main points (usually a list)
  - checklist       # things to verify or complete (reading checklist, not a task list)
  # - regulation: "SACAA regulations and law"   # Example: add deployment-specific types like this

# Course access types — the valid values for a course's `access_config.access_type`
# frontmatter (see the fls-content:content-types skill, course-files.md). Like
# admonition_types, this is the COMPLETE, AUTHORITATIVE set for this repo, and it mirrors
# your deployment's COURSE_ACCESS_BACKEND vocabulary. /fls-content:validate-content checks
# each course's access_type against this list.
#
# The list below is the FLS shipped default (ApplicationCourseAccessBackend). Edit it to
# match your deployment:
#   - a free-only deployment (FreeOnlyCourseAccessBackend) keeps only `free`;
#   - a custom backend (e.g. subscriptions) replaces these with its own values.
access_types:
  - free               # open to everyone; learners self-enrol
  - application_gated  # learner submits an application before they can enrol
```

After writing, confirm to the author:

> Created `.fls-content.yaml` at `<path>` with the FLS base admonition set and the FLS
> shipped course `access_types` as a starting template. Edit `admonition_types` and
> `access_types` to match your deployment's configured types — each list is the complete
> authoritative set for this repo, not a floor. Run `/fls-content:init` again at any time; it
> will not overwrite your customised config.

### 5. Install the validator's dependencies

`/fls-content:validate-content` runs a bundled Python validator that needs `pydantic`,
`pyyaml`, and `python-frontmatter`. Install them once here, into a `.venv/` at the repo root,
so validation never re-resolves dependencies on every run.

The venv lives at the repo root — the current working directory where Claude runs, alongside
`.claude/`. (This is independent of the content root from Step 1; in the common case they are
the same directory.)

First confirm `uv` is available:

```bash
uv --version
```

If `uv` is not installed, tell the author to install it from
https://docs.astral.sh/uv/getting-started/installation/ (or ask their FLS administrator),
and stop — the validator cannot be set up without it.

If the environment already exists and is healthy, do nothing:

```bash
".venv/bin/python" -c "import pydantic, yaml, frontmatter"
```

If that command succeeds, the dependencies are already installed — report that and skip the
install. If it fails (or the environment does not exist), create it and install the deps:

```bash
uv venv .venv
uv pip install --python .venv/bin/python \
  pydantic pyyaml python-frontmatter
```

Finally, make sure the venv is never committed — ensure `.venv/` is listed in the repo's
`.gitignore` (idempotent; creates the file if absent):

```bash
if ! grep -qxF '.venv/' .gitignore 2>/dev/null; then
  printf '.venv/\n' >> .gitignore
fi
```

Then confirm to the author that the validator is ready and they can run
`/fls-content:validate-content`.

### Constraint reminder

This command writes only three things: `.fls-content.yaml` in the content root when absent
(Step 4), the validator's `.venv/` dependency environment at the repo root, and a `.venv/`
line in the repo-root `.gitignore` (Step 5). It does **not** read, modify, rename, or delete
any course files, images, or UUIDs.
