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

A topic is a numbered directory containing a `content.md`. Give the topic its own `images/`
for assets only it uses; keep assets shared by several topics in an `images/` directory
higher up (the course root, or a part).

A flat numbered topic file (`01. intro.md`) is accepted, but the directory form is preferred:
it keeps a topic's body and images together.

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

## Course with reference parts

```
my-course/
  course.md                 ← lists the parts under reference:
  01. Getting Started/      ← COURSE_PART in the learning path
      part.yaml
      01. welcome/
          content.md
  reference/                ← optional home for the course's reference parts (not a child)
      01. Airspace Rules/   ← COURSE_PART listed under reference:
          part.yaml
          01. airspace-classes/
              content.md
```

A reference part holds topics only. It is attached through `reference:` in `course.md` (see
[`course-files.md`](course-files.md#reference-parts)); a part elsewhere in the repo, such as one shared by several courses,
works the same way.

## Course categories declaration (repo root)

If a repo declares dashboard categories, exactly one `COURSE_CATEGORIES` file lives outside
every course directory, normally at the repo root beside the course directories, never
nested inside one:

```
demo_content/
  course_categories.yaml   ← COURSE_CATEGORIES (declared once, for the whole repo)
  functionality_demo_course_parts/
    course.md
    ...
  functionality_demo_standard_markdown/
    course.md
    ...
```

Its frontmatter and validation rules: see
[`course-files.md`](course-files.md#course_categories-course_categoriesyaml).

## Articles

An `ARTICLE` is a standalone file, not a course child. Name it after its slug (`my-article.md`);
no `NN.` prefix. A `slug/content.md` directory is also read, with the slug taken from the
directory name. Child auto-discovery skips ARTICLE files, so an article may sit in a course
directory without becoming a topic of that course. See
[`article-files.md`](article-files.md).

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

`.fls-content.yaml` (the deployment config) starts with `.`, so it is never scanned. `.claude/fls-content/widgets/` (the content repo's widget declarations, see the `fls-content:widget-reference` skill) is never scanned either: it sits inside `.claude/`.

The optional `ignore:` list in `.fls-content.yaml` names more paths to leave out: exact POSIX paths relative to the repo root, each a file or a folder (a folder covers everything beneath it; no wildcards, no absolute paths, no `..`). Ignored paths are not parsed, uploaded or auto-discovered, an explicit `children:` entry or `sections:` target naming one is an error, and ignored files must still be committed.

## Child auto-discovery

When a COURSE or COURSE_PART has no explicit `children:` list, `content_save` auto-discovers children by iterating the directory alphabetically. Ordering therefore depends on correct `NN.` numbering. For custom ordering, add an explicit `children:` list in `course.md` or `part.yaml`.

Auto-discovery skips any file or directory whose name starts with `_` or `.`
(e.g. `_drafts/`, `.fls-content.yaml`), both among the top-level items of the collection
directory and among the files inside a numbered subdirectory when deciding whether it is a
nested collection (`course.md` / `form.md` / `part.yaml`) or a topic (`content.md`). This is
**narrower** than the "Files excluded from scanning" list above: auto-discovery does not
special-case `README.md`, `CLAUDE.md`, or a trailing `~`; only the `_`/`.`-prefix rule
applies. Prefix a draft file/directory with `_` to keep it out of an auto-discovered
`children:` list.

Auto-discovery also skips ARTICLE and COURSE_CATEGORIES files, wherever they sit: neither is
ever a collection child.

A COURSE also skips a directory named `reference` beside its `course.md`: it is never a child, whatever it holds, and nothing
in it is read during discovery. A COURSE_PART has no such rule.

## Image path resolution

Paths in `c-picture`, `c-pdf-embed`, `c-file-download`, `c-audio`, and `c-audio-clip` are stored relative to the course root in the DB (as uploaded by `content_save`). In source files, write paths relative to the content file referencing them:

- A topic-local image, from `02. going-deeper/content.md`:
  `src="images/diagram.svg"` → stored as `02. going-deeper/images/diagram.svg`.
- A shared image at the course root, from `02. going-deeper/content.md`:
  `src="../images/logo.svg"` → stored as `images/logo.svg`.
- A shared image from inside a form subdirectory: `src="../images/graph.svg"`.

**Never write `src=` with a `.webp` extension because that is what you see in the database or the
storage bucket.** `content_save` re-encodes most raster images (JPEG, PNG, GIF, BMP) to WebP
when it stores them, but `src=` always keeps the extension of the file you authored:
`src="images/photo.jpg"` stays correct even though the stored object is renamed
`photo.webp`. See `c-picture` in the
`fls-content:widget-reference` skill for what happens to the image itself.

## Audio files

`content_save` classes a file as audio by extension: `.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac`, `.aac`. Use `.mp3` unless you have a reason not to. Any other extension (including `.opus` and `.oga`) is not audio, and `c-audio` and `c-audio-clip` show their "Audio not found" error box for it. Keep audio next to the topic that uses it (e.g. `audio/bravo.mp3` in the topic directory) and write `src` relative to the content file, as for images. See `c-audio` and `c-audio-clip` in the `fls-content:widget-reference` skill.
