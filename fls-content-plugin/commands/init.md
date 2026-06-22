---
description: Scaffold .fls-content.yaml in a content repo (non-destructive, safe to re-run)
allowed-tools: Read, Write, Glob
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

Read the existing `.fls-content.yaml`. Parse the `admonition_types` list from the file
content you just read. Compare it against the FLS base names (`note`, `tip`, `important`,
`warning`, `danger`, `key_takeaways`, `checklist`) and report both groups. Do **not** copy
the example values below — compute the split from the actual file.

Report:

1. That the file is already present and has been left **byte-for-byte untouched**.
2. A convenience cross-reference of the declared types against the FLS base set. Frame this
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
> This is informational only — your config is the authoritative set for this repo and may
> intentionally differ from the FLS base set.

Do **not** merge, reorder, overwrite, or delete anything. Exit here.

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
  - note
  - tip
  - important
  - warning
  - danger
  - key_takeaways
  - checklist
  # - regulation   # Example: add deployment-specific types like this
```

After writing, confirm to the author:

> Created `.fls-content.yaml` at `<path>` with the FLS base admonition set as a starting
> template. Edit `admonition_types` to match your deployment's configured types — the list
> is the complete authoritative set for this repo, not a floor. Run `/fls-content:init`
> again at any time; it will not overwrite your customised config.

### Constraint reminder

This command's only-ever write is creating `.fls-content.yaml` when absent (Step 4).
It does **not** read, modify, rename, or delete any course files, images, or UUIDs.
