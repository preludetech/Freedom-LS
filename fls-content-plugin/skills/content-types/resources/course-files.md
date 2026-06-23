# COURSE and COURSE_PART Files

---

## COURSE (`course.md`)

One `course.md` file per course root directory. Its presence identifies the directory as a COURSE.

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `COURSE` | Yes | Must be exactly `COURSE` |
| `title` | `str` | Yes | Course display title |
| `subtitle` | `str` | No | Optional subtitle |
| `description` | `str` | No | Optional course description |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |
| `icon` | `str` | No | Semantic icon name (e.g. `"notes"`) or literal glyph |
| `icon_fallback` | `str` | No | `"<iconset>:<glyph>"` (e.g. `"phosphor:drone"`); only valid when `icon` is also set |
| `learning_outcomes` | `list[str]` | No | "What you'll learn" bullet list |
| `difficulty` | `beginner`, `intermediate`, `advanced`, or `all_levels` | No | Difficulty level |
| `estimated_duration` | `str` | No | Duration string e.g. `"1:30:00"` (HH:MM:SS) |
| `children` | `list` | No | Explicit ordered list of child paths; if omitted, auto-discovered alphabetically |
| `content` | `str` | No | Optional markdown intro body |
| `tags` | `list[str]` | No | Optional tag list |
| `meta` | `dict` | No | Arbitrary metadata |

### Minimal example (new course)

```yaml
---
content_type: COURSE
title: Introduction to Python
description: A beginner-friendly guide to Python programming.
---
```

### Full example

```yaml
---
content_type: COURSE
title: Standard Markdown - Demo
subtitle: A standard tour of the content system
description: This will show how all the Standard Markdown goodies show up.
difficulty: beginner
estimated_duration: "1:30:00"
icon: notes
learning_outcomes:
  - Understand how the markdown content system renders
  - Recognise every built-in content widget
  - Author a course with confidence
---

Your competitive advantage is your ability to learn.
```

### Children ordering

When `children:` is omitted, `content_save` auto-discovers children alphabetically from the directory. For custom ordering or to exclude specific files, use an explicit `children:` list:

```yaml
children:
  - path: 01. intro.md
  - path: 02. concepts.md
  - path: 03. quiz/form.md
```

---

## COURSE_PART (`part.yaml`)

One `part.yaml` file per course-part subdirectory. Its presence identifies the directory as a COURSE_PART. The directory must be numbered (e.g. `01. Getting Started/`).

**`part.yaml` has no closing `---`** — the file ends after the last key. This is valid single-document YAML.

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `COURSE_PART` | Yes | Must be exactly `COURSE_PART` |
| `title` | `str` | Yes | Part display title |
| `subtitle` | `str` | No | Optional subtitle |
| `description` | `str` | No | Optional description |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files, and NEVER EDIT existing UUIDs** |
| `children` | `list` | No | Explicit ordered child list; if omitted, auto-discovered |
| `tags` | `list[str]` | No | Optional tag list |
| `meta` | `dict` | No | Arbitrary metadata |

Note: COURSE_PART has **no `content`** field — there is no markdown body on a part.

### Example (new part — no uuid)

```yaml
---
content_type: COURSE_PART
title: Getting Started
```

### Example (after content_save — uuid added)

```yaml
---
content_type: COURSE_PART
title: Getting Started
uuid: 66bb8510-ce90-426e-82fb-f02b7ca92fdc
```

Note the missing closing `---` — this is correct.

Directory layout reference: see [`file-layout.md`](file-layout.md).
UUID and numbering rules: see the `fls-content:conventions` skill.
