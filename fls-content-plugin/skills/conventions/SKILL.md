---
name: conventions
description: FLS course-authoring conventions — numbering, file naming, UUID rules, and HTML-escaping rules. Use when asking about uuid, numbering, ordering, file name, folder, or directory structure.
allowed-tools: Read, Grep, Glob
---

# FLS Course-Authoring Conventions

<!-- Source: demo_content/, freedom_ls/content_engine/validate.py (scanner skip rules), freedom_ls/content_engine/schema.py (UUID field) -->

## Numbered items: `NN. name` prefix

All ordered content (topics, course-part directories, form-page files) uses a numeric prefix:

```
01. Getting Started/      ← course-part directory
02. Core Concepts/
01. welcome.md            ← topic file
02. what-to-expect.md
1. page.yaml              ← form-page file
2. results.yaml
```

Rules:
- Use two-digit zero-padded prefix (`01.`, `02.` … `09.`, `10.`) for directories and topic files.
- Use single-digit prefix (`1.`, `2.`) for form-page files inside a form directory.
- Discovery order is strict alphabetical — zero-pad consistently whenever a directory will have more than 9 ordered items.
- Slug portion is kebab-case derived from the content title; never invented.

## Role files (unnumbered)

Three files are identified by **name alone** — they are never numbered:

| File | Role |
|---|---|
| `course.md` | Identifies the directory as a COURSE |
| `form.md` | Identifies the directory as a FORM |
| `part.yaml` | Identifies the directory as a COURSE_PART |

`part.yaml` has **no closing `---`** — the file ends after the last field:

```yaml
---
content_type: COURSE_PART
title: Getting Started
uuid: 66bb8510-ce90-426e-82fb-f02b7ca92fdc
```

## Scanner skip rules

The FLS scanner (`validate.py`) skips these files and directories — they are never treated as content:

- Names starting with `_` (e.g. `_drafts/`)
- Names starting with `.` (e.g. `.fls-content.yaml`)
- Files named `README.md` or `CLAUDE.md`
- Files whose name ends with `~`

## UUID rules (load-bearing — read before creating any file)

1. **Omit `uuid` on new content.** Do not write a `uuid:` field. `content_save` generates a UUID and writes it back into the source file on first run.
2. **Never edit an existing `uuid:`.** The UUID is the stable identity for the DB row; editing it breaks the upsert and may silently create a duplicate.
3. **Never duplicate a UUID across files.** Two files with the same UUID cause one to silently overwrite the other on `content_save`.
4. **Never hand-create a UUID.** Not even with a UUID4 generator — the workflow is: omit the field, run `content_save`, let it write the UUID back.

Example of a **correct** new topic (no uuid field):

```yaml
---
content_type: TOPIC
title: Introduction to Variables
description: Learn what variables are and how to use them.
---

Body content here...
```

After the first `content_save`, the file will have a `uuid:` field added automatically.

## HTML-escaping rules

`c-code-block` and `c-equation` bodies are **not** markdown-processed — they pass as raw text through the nh3 sanitiser. Authors must escape these characters:

| Character | Escape as |
|---|---|
| `<` | `&lt;` |
| `>` | `&gt;` |
| `&` | `&amp;` |
| `"` | `&quot;` (code-block only) |

All other widget bodies use standard markdown; escaping is handled automatically.

Full widget syntax details: see the `fls-content:widget-reference` skill.
