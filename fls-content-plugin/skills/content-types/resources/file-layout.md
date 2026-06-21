<!-- Source: demo_content/, freedom_ls/content_engine/validate.py (scanner skip rules, get_all_files), freedom_ls/content_engine/management/commands/content_save.py (child auto-discovery) -->

# FLS Content Directory Layout

## Course without parts

```
my-course/
  course.md              ← COURSE (required; identifies the directory as a course)
  images/                ← image/binary assets (uploaded to DB by content_save)
  01. intro.md           ← TOPIC
  02. key-concepts.md    ← TOPIC
  03. knowledge-check/   ← FORM directory (numbered subdirectory)
      form.md            ← FORM (required; identifies the directory as a form)
      1. page.yaml       ← FORM_PAGE (section 1) + questions/content (sections 2+)
      2. results.yaml    ← FORM_PAGE + questions
```

## Course with COURSE_PARTs

```
my-course/
  course.md
  01. Getting Started/      ← COURSE_PART directory (numbered)
      part.yaml             ← COURSE_PART (required; no closing ---)
      01. welcome.md        ← TOPIC
      02. what-to-expect.md ← TOPIC
  02. Core Concepts/
      part.yaml
      01. key-ideas.md
      02. going-deeper.md
      03. knowledge-check/  ← FORM directory nested inside a PART
          form.md
          1. page.yaml
```

## Numbering rules

- Two-digit zero-padded prefix for directories and topic/activity files: `01.`, `02.` … `09.`, `10.`
- Single-digit prefix for form-page files: `1.`, `2.`, `3.`
- Sort order is strict alphabetical — zero-pad consistently when a directory will have more than 9 items.
- Slug portion is kebab-case derived from the content title.

Cross-reference: `fls-content:conventions` skill for the full numbering and scanner-skip rules.

## Role files (unnumbered, name-identified)

| File | Role | Directory type it identifies |
|---|---|---|
| `course.md` | COURSE | The course root directory |
| `form.md` | FORM | A numbered subdirectory that contains form pages |
| `part.yaml` | COURSE_PART | A numbered subdirectory that groups topics |

## Files excluded from scanning

The FLS scanner skips:
- Names starting with `_` or `.`
- `README.md` and `CLAUDE.md`
- Names ending with `~`

`.fls-content.yaml` (the deployment config) is never scanned as content because it starts with `.`.

## Child auto-discovery

When a COURSE or COURSE_PART has no explicit `children:` list, `content_save` auto-discovers children by iterating the directory alphabetically. Ordering therefore depends on correct `NN.` numbering. For custom ordering, add an explicit `children:` list in `course.md` or `part.yaml`.

## Image path resolution

Paths in `c-picture`, `c-pdf-embed`, and `c-file-download` are stored relative to the course root in the DB (as uploaded by `content_save`). In source files, write paths relative to the content file referencing them — e.g. `src="images/graph.svg"` from a topic at the course root, or `src="../images/graph.svg"` from inside a form subdirectory.
