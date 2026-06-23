# TOPIC and ACTIVITY Files

<!-- claude todo: add: title and subtitle are automatically rendered, dont add top-level headings in the markdown text

Eg:


```[bad]
---
title: foo
---
# Foo
```

This will render as:

<h1>Foo</h1>
<h2>Foo</h2>


 -->

## TOPIC

A numbered directory (e.g. `01. welcome/`) inside a course or course-part directory,
containing a `content.md` with the topic's frontmatter and body. Put images used only by
this topic in the directory's own `images/` subfolder; images shared across topics live in
an `images/` directory higher up (see `resources/file-layout.md`).

A flat numbered file (`01. welcome.md`) is still accepted, but the
directory-with-`content.md` form is preferred.

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `TOPIC` | Yes | Must be exactly `TOPIC` |
| `title` | `str` | Yes | Rendered as the page H1 by the template |
| `subtitle` | `str` | No | Optional subtitle shown beneath the title |
| `description` | `str` | No | Optional description (not in body) |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |
| `tags` | `list[str]` | No | Optional tag list |
| `meta` | `dict` | No | Arbitrary metadata for downstream use |

### Heading rule (load-bearing)

The `title` frontmatter value is rendered as the page H1 by the template — **do not repeat it as a heading in the body**.

Body headings use the `mdx_headdown` rendering shift: every heading in the body is shifted down one level at render time:
- Body `#` (H1) → rendered H2
- Body `##` (H2) → rendered H3
- Body `###` (H3) → rendered H4

This is how body content nests beneath the page title. Use `#` for your top-level body sections, `##` for sub-sections, and so on. Never skip heading levels (e.g. do not jump from `#` to `###` without a `##` between them).

### Minimal example (new file — no uuid)

```yaml
---
content_type: TOPIC
title: Introduction to Variables
description: Learn what variables are and how to use them.
---

Variables are named containers for values. In Python, you create one by assignment:

# What is a variable?

A variable stores a value that can change.

## Integers and strings

The two most common types...
```

### Full example (after content_save has run)

```yaml
---
content_type: TOPIC
title: Welcome
subtitle: What this course covers
description: An overview of what you will learn.
uuid: 8bc127c1-edf1-4997-b7fc-35fdf8604f30
---

Welcome to the course. Here is what we will cover.

# Module overview

This module covers the fundamentals.

## Getting started

Start with the basics...
```

---

## ACTIVITY

Same on-disk shape as a TOPIC — a numbered directory with a `content.md` (a flat numbered
`.md` file is also accepted). Identical to TOPIC but with one extra optional field.

### Additional field

| Field | Type | Required | Notes |
|---|---|---|---|
| `level` | `int` | No | Difficulty level; 1 = easiest |

### Example

```yaml
---
content_type: ACTIVITY
title: Practice Exercise — Variables
level: 1
---

Complete the following tasks...
```

Widget syntax for topic/activity bodies: see the `fls-content:widget-reference` skill.
