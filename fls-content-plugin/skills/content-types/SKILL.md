---
name: content-types
description: FLS content types, file formats, and frontmatter schemas. Use when authoring a topic, form, quiz, survey, course, course part, chapter, module, or any content file.
allowed-tools: Read, Grep, Glob
---

# FLS Content Types

FLS has eight content types. Each maps to a specific file name or naming pattern; the `content_type` frontmatter field identifies which type a file is.

All models use `extra="forbid"` — any unrecognised frontmatter key causes validation to fail. Typos in key names produce a clear error.

## The eight types at a glance

| `content_type` | File | Notes |
|---|---|---|
| `COURSE` | `course.md` | One per course directory; optional markdown body |
| `COURSE_PART` | `part.yaml` | One per part subdirectory; **no closing `---`** |
| `TOPIC` | `NN. slug.md` | Numbered `.md` file; markdown body |
| `ACTIVITY` | `NN. slug.md` | Numbered `.md` file; markdown body; has `level` field |
| `FORM` | `form.md` | Inside a numbered subdirectory; identifies the directory as a form |
| `FORM_PAGE` | `NN. slug.yaml` | First `---`-delimited YAML section of the file |
| `FORM_QUESTION` | (in `NN. slug.yaml`) | Subsequent sections containing a `question` key |
| `FORM_CONTENT` | (in `NN. slug.yaml`) | Subsequent sections containing a `content` key |

## Key non-obvious facts

- **`FORM_QUESTION` vs `FORM_CONTENT`** — the parser selects the type based on whether a YAML section has a `question` key or a `content` key, not on an explicit `content_type` declaration.
- **`FORM_QUESTION` and `FORM_CONTENT`** inherit a *smaller* base model — they have **no** `title`, `subtitle`, `description`, `category` (as a display field), or `image` fields.
- **`part.yaml` has no closing `---`** — the file ends after the last YAML key. This is valid single-document YAML.
- **TOPIC body headings**: the `title` lives in frontmatter and renders as the page H1. **Do not repeat it as a heading in the body.** Body headings start at `#` (H1 in the source), which `mdx_headdown` shifts down to render as H2 beneath the title. Nest sub-sections with `##`, `###`, … without skipping levels.

## Common base fields (most types)

| Field | Required | Notes |
|---|---|---|
| `content_type` | Yes | One of the eight values above |
| `title` | Yes (most types) | Display title |
| `uuid` | No | Written by `content_save` on first run — **never hand-create** |
| `subtitle` | No | Optional subtitle |
| `description` | No | Optional description |
| `tags` | No | `list[str]` |
| `meta` | No | `dict` of arbitrary metadata |

See `resources/` for full per-type frontmatter, directory layout, and copy-pasteable examples:

- [`resources/file-layout.md`](resources/file-layout.md) — directory structure and numbering
- [`resources/topic-files.md`](resources/topic-files.md) — TOPIC and ACTIVITY frontmatter
- [`resources/form-files.md`](resources/form-files.md) — FORM, FORM_PAGE, FORM_QUESTION, FORM_CONTENT
- [`resources/course-files.md`](resources/course-files.md) — COURSE and COURSE_PART frontmatter

UUID and numbering rules: see the `fls-content:conventions` skill.
Widget syntax for topic bodies: see the `fls-content:widget-reference` skill.
