---
name: conventions
description: FLS course-authoring conventions — numbering, file naming, UUID rules, and HTML-escaping rules. Use when asking about uuid, numbering, ordering, file name, folder, or directory structure.
allowed-tools: Read, Grep, Glob
---

# FLS Course-Authoring Conventions

## Numbered items: `NN. name` prefix

All ordered content (topics, course-part directories, form-page files) uses a numeric prefix:

```
01. Getting Started/          ← course-part directory (holds part.yaml)
02. Core Concepts/
    01. welcome/              ← topic directory (holds content.md)
        content.md
    02. what-to-expect/
        content.md
    03. knowledge-check/      ← form directory (holds form.md)
        1. page.yaml          ← form-page file
        2. results.yaml       ← another form-page file (e.g. a results page)
```

Form-page files live **inside** the form directory alongside `form.md`. The names
`page.yaml` / `results.yaml` are just illustrative — each numbered `.yaml` is one page of
the form, named with a kebab-case slug like any other content.

Rules:
- Zero-pad every numeric prefix to the digit-width of the largest sibling in the same
  directory (largest is `10.` → pad all to two digits; largest is `100.` → three). Discovery
  order is strict alphabetical, so consistent padding is what keeps the order correct.
- Default to two digits for top-level course items (topics, parts) — those sets usually grow
  past nine.
- Form-page files inside a form directory follow the same rule: single digit until there are
  at least ten pages, then two.
- Slug portion is kebab-case derived from the content title; never invented.

## Role files (unnumbered)

These files are identified by **name alone** — they are never numbered:

| File | Role |
|---|---|
| `course.md` | Identifies the directory as a COURSE |
| `content.md` | Identifies a numbered directory as a TOPIC / ACTIVITY |
| `form.md` | Identifies the directory as a FORM |
| `part.yaml` | Identifies the directory as a COURSE_PART |

(An ACTIVITY uses `content.md` too — same as a TOPIC. There is no `activity.md`.)

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
