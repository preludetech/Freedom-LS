# FLS Content Directory Layout

## Course without parts

```
my-course/
  course.md              ← COURSE (required; identifies the directory as a course)
  images/                ← shared image/binary assets (reused across topics)
  01. intro/             ← TOPIC directory (preferred layout)
      content.md         ← TOPIC (the topic body + frontmatter)
      images/            ← images used only by this topic
  02. key-concepts/      ← TOPIC directory
      content.md
  03. knowledge-check/   ← FORM directory (numbered subdirectory)
      form.md            ← FORM (required; identifies the directory as a form)
      1. page.yaml       ← FORM_PAGE (section 1) + questions/content (sections 2+)
      2. more-questions.yaml ← FORM_PAGE + questions
```

A topic is a numbered directory containing a `content.md`. Give the topic its own
`images/` for assets used only by that topic; keep assets reused by several topics in an
`images/` directory higher up the tree (the course root, or a part).

A flat numbered topic file (`01. intro.md`) is still accepted, but the directory form is
preferred — it keeps a topic's body and its images together.

## Course with COURSE_PARTs

```
my-course/
  course.md
  01. Getting Started/      ← COURSE_PART directory (numbered)
      part.yaml             ← COURSE_PART (required; no closing ---)
      01. welcome/          ← TOPIC directory
          content.md
      02. what-to-expect/
          content.md
  02. Core Concepts/
      part.yaml
      images/               ← assets shared by topics within this part
      01. key-ideas/
          content.md
      02. going-deeper/
          content.md
          images/           ← assets used only by "going deeper"
      03. knowledge-check/  ← FORM directory nested inside a PART
          form.md
          1. page.yaml
```

## Numbering rules

- Two-digit zero-padded prefix for directories (topic, part, and form directories): `01.`, `02.` … `09.`, `10.`
- Single-digit prefix for form-page files: `1.`, `2.`, `3.`
- Sort order is strict alphabetical — zero-pad consistently when a directory will have more than 9 items.
- Slug portion is kebab-case derived from the content title.

Cross-reference: `fls-content:conventions` skill for the full numbering and scanner-skip rules.

## Role files (unnumbered, name-identified)

| File | Role | Directory type it identifies |
|---|---|---|
| `course.md` | COURSE | The course root directory |
| `content.md` | TOPIC / ACTIVITY | A numbered topic/activity directory |
| `form.md` | FORM | A numbered subdirectory that contains form pages |
| `part.yaml` | COURSE_PART | A numbered subdirectory that groups topics |

When a numbered subdirectory contains more than one role file, the collection roles
(`course.md`, `form.md`, `part.yaml`) win over `content.md` — so a COURSE_PART directory is
always treated as the part, never as a topic.

## Files excluded from scanning

The FLS scanner skips:
- Names starting with `_` or `.`
- `README.md` and `CLAUDE.md`
- Names ending with `~`

`.fls-content.yaml` (the deployment config) is never scanned as content because it starts with `.`.

## Child auto-discovery

When a COURSE or COURSE_PART has no explicit `children:` list, `content_save` auto-discovers children by iterating the directory alphabetically. Ordering therefore depends on correct `NN.` numbering. For custom ordering, add an explicit `children:` list in `course.md` or `part.yaml`.

Auto-discovery skips any file or directory whose name starts with `_` or `.`
(e.g. `_drafts/`, `.fls-content.yaml`) — both among the top-level items of the
collection directory, and among the files inside a numbered subdirectory when
deciding whether that subdirectory is a nested collection (`course.md` /
`form.md` / `part.yaml`) or a topic (`content.md`). This is **narrower** than
the "Files excluded from scanning" list above: auto-discovery does not
separately special-case `README.md`, `CLAUDE.md`, or a trailing `~` — only the
`_`/`.`-prefix rule applies to auto-discovered children. Prefix a draft
file/directory with `_` to keep it out of an auto-discovered `children:` list.

## Image path resolution

Paths in `c-picture`, `c-pdf-embed`, and `c-file-download` are stored relative to the course root in the DB (as uploaded by `content_save`). In source files, write paths relative to the content file referencing them:

- A topic-local image, from `02. going-deeper/content.md`:
  `src="images/diagram.svg"` → stored as `02. going-deeper/images/diagram.svg`.
- A shared image at the course root, from `02. going-deeper/content.md`:
  `src="../images/logo.svg"` → stored as `images/logo.svg`.
- A shared image from inside a form subdirectory: `src="../images/graph.svg"`.
