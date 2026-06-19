# Course Editing Plugin

## Problem

People authoring FLS courses write Markdown and YAML by hand, against a fairly
specific set of conventions (content types, file/folder layout, numbering,
frontmatter, `c-*` widgets, UUID rules). Getting any of this wrong means the
content fails `content_save` validation or renders incorrectly. The authors who
hit this most are working in projects that **do not have the FLS source code**,
so they cannot read the schema, settings, or component templates to find the
rules.

We want a Claude Code plugin that helps these authors structure content
correctly and turn messy Markdown into valid FLS content — focused on
**integration** (what tool to use where, the syntax, and the structure), not on
teaching pedagogy or course design.

## Goal

A self-contained Claude Code plugin, living in its own directory in this repo,
that:

- Explains the FLS content **file types** and how to use them (course, course
  part, topic, form/quiz/survey, form page).
- Explains how to **organise** those files — directory layout and the `NN. name`
  numbering convention.
- Explains the **widgets** (`c-*` cotton components): what each is for, its
  syntax and attributes, and simple best practices.
- Makes clear that **UUIDs must never be touched** (they are written by
  `content_save` and are the database identity).
- Converts **messy Markdown into FLS content structure** — point it at a single
  `.md` file or a directory of them.

The plugin is the source authors rely on instead of the (unavailable) codebase,
so all reference material must be **self-contained and literal**.

## Hard constraints

- **Never change the substantive content of a course.** Conversion is a
  structural/format transform only — no rewriting, summarising, or inventing
  prose. Frontmatter values are derived from existing heading/paragraph text,
  never fabricated.
- **Never invent or edit UUIDs.** `content_save` assigns them; the plugin omits
  the `uuid` field entirely on new content and never alters existing ones.
- **Self-contained:** every authoring fact (valid `content_type` values, FORM
  `strategy` values, the full widget allowlist and attributes, escaping rules)
  is stated literally in the plugin, not by reference to FLS source.

## Shape of the plugin

Lives in a new directory at the repo root, sibling to `fls-claude-plugin/`.
Proposed namespace `fls-content` (directory `fls-content-plugin/`) so it does not
collide with the existing developer `fls` plugin. Distribution to other projects
is **out of scope for now** — once the plugin is nailed down we will decide how
to ship it.

Contents:

- **Reference skills** (passive, always-available, reusable inside subagents):
  - *content types & file layout* — per-type frontmatter, directory structure,
    numbering.
  - *widget reference* — every `c-*` widget with attributes and examples.
  - *conventions & UUID rules* — numbering, file naming, UUID rules, escaping.
  - *markdown conversion* — how and when to map Markdown onto FLS structure.
- **A conversion command** (e.g. `/fls-content:convert-markdown`) backed by the
  conversion skill (and, for large inputs, a conversion subagent). A command,
  not a skill, because it is an explicit multi-step action taking a file/dir
  argument and benefiting from fan-out.

### Conversion behaviour

- **Conservative by default.** Auto-apply only unambiguous, lossless transforms
  (local image `![](...)` → `<c-picture>`; Obsidian `![[image]]` / `![[image | title]]`
  → `<c-picture>`; YouTube watch URL → `<c-youtube>`). Convert content into its
  **final FLS form** — do not leave `![[...]]` for `content_save` to translate,
  because that path drops alt text; expanding it during conversion lets us set
  `alt` properly (deriving it from any caption/title present, otherwise flagging
  it for the author). Anything semantic (blockquote → admonition, Q&A → flashcard,
  "optional reading" → accordion, math → equation) is **proposed for author
  confirmation, never applied silently**. When in doubt, leave it as plain Markdown.
- **Splitting:** split a source document at H1 (or H2 if it has no H1); derive
  `title`/`subtitle`/`description` strictly from existing heading and intro-paragraph
  text. Single file → one or more topics; directory → a course, with
  subdirectories becoming course parts.
- **Written review alongside the output.** Conversion writes the files and also a
  `_conversion_review.md` next to them listing every auto-applied change, every
  flagged item (with source line references), unresolved images/links, and a
  prose-preservation report (source-vs-output text check) confirming no content
  was lost. The author reviews via the git diff plus this file, then deletes it
  before running `content_save`. (No dry-run default — git already makes the
  change safe to inspect and revert.)
- **Idempotent:** skip any file that already has `content_type:` frontmatter;
  never touch an existing `uuid:`. Safe to re-run on partially converted content.
- Content lives in **git**, so the author already has a full before/after diff
  and rollback — the conversion does not need to contrive its own versioning or
  backup of the source.

## Keeping the plugin in sync with FLS

When FLS course-authoring functionality changes (new/changed widgets, frontmatter,
content types, conventions), the plugin must be updated to match. This is wired
into the **SDD workflow itself** as a lightweight, built-in check rather than a
separate doc-generation pipeline or an external manual checklist:

- A new SDD step / `todo.md` item: run an `/update_author_plugin` command near
  the "update product docs" stage.
- The command first runs a cheap detection heuristic (`git diff main` against
  authoring-relevant paths: `content_engine/schema.py`, `templates/cotton/*.html`,
  `MARKDOWN_ALLOWED_TAGS` in `settings_base.py`, `content_save`/`content_validate`,
  `demo_content/`). No match → tick the box and exit (zero tokens, no LLM).
- On a match → fan out one worker to draft the scoped plugin edits from the
  changed source files, apply them (touching only affected sections), and tick
  the box.

The source of truth for these updates is the FLS code itself (schema, cotton
templates, settings), with `demo_content/` as living convention examples.

## Open questions for the spec phase

- **Standalone validator (undecided — settle in the spec):** `validate.py` +
  `schema.py` have almost no Django dependency, so a trimmed copy could be bundled
  in the plugin to give authors full Pydantic `extra="forbid"` validation offline
  (icon validation stubbed out). This strengthens the "no FLS source" story but
  adds code that must be kept in sync (the SDD sync check would cover it). The
  alternative is documentation-only: teach the rules and direct authors to run
  `content_validate`/`content_save` on an FLS host for the authoritative pass.
- Exact skill split and naming (the research proposes `content-types`,
  `widget-reference`, `conventions`, `markdown-conversion`).
- Whether the conversion command needs its own subagent or can run inline for the
  expected input sizes.

## Notes / discrepancies surfaced by research

- `c-card` is a real, registered widget but is **missing from the current product
  docs and the developer `markdown_content.md` resource**. The new plugin should
  document it; the code (`MARKDOWN_ALLOWED_TAGS`, `card.html`) is the source of
  truth.
- `content_save`'s Obsidian `![[image]]` auto-translation **drops alt text**.
  This is why the conversion command expands `![[...]]` to `<c-picture>` itself
  rather than relying on that translation — so alt text can be set or flagged.
- `c-code-block` and `c-equation` bodies are **not** Markdown-processed and require
  manual HTML-escaping of `<`, `>`, `&` (and `"` for code blocks).

See the `research_*.md` files in this directory for full detail.
