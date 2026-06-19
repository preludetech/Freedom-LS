# Research: Messy Markdown to FLS Content Structure Conversion

_Research for the course-editing-plugin "improve idea" phase._
_Ground truth: `demo_content/`, `docs/product/content-editing-workflow.md`, `freedom_ls/content_engine/schema.py`, `freedom_ls/content_engine/validate.py`._

---

## 1. The Conversion Problem Space

### FLS Content Hierarchy — What Needs to Be Produced

FLS has a fixed structural hierarchy with eight content types. For a markdown-to-FLS conversion tool, only the authoring-time types matter:

| Level | Type | File | Trigger |
|---|---|---|---|
| 1 | `COURSE` | `course.md` | One per course directory |
| 2 | `COURSE_PART` | `part.yaml` | Optional; one per chapter subdirectory |
| 3 | `TOPIC` | `NN. slug.md` | Numbered `.md` file with frontmatter |
| 3 | `FORM` | `form.md` + `NN. page.yaml` | A directory containing form pages |
| 4 | `FORM_PAGE` | `NN. page.yaml` | YAML with multi-doc separator (`---`) for questions |

The `COURSE` and `COURSE_PART` types do **not** list their children in a `children:` list that the author writes by hand — `content_save` discovers them from the directory layout. (The `Course` schema has a `children` field, but that is populated during loading, not hand-authored.)

### Mapping Arbitrary Markdown Structure to FLS Types

**Decision tree for the source document:**

```
Does the source have a single logical theme/lesson?
  YES -> one TOPIC (single .md file)
  NO  -> split (see below)

Does it have H2-level chapters that each span 3+ screens?
  YES -> each H2 section -> one TOPIC
  NO  -> is it short enough to be one TOPIC? Keep it whole.

Does it contain quiz/survey questions?
  YES -> questions -> FORM + FORM_PAGE(s) + FORM_QUESTIONs (YAML, not markdown)
  NO  -> pure TOPIC

Is there a collection of multiple related documents/directories?
  YES -> consider COURSE_PART grouping if natural sections exist (e.g. chapters)
  TOP LEVEL -> one COURSE (course.md)
```

**Practical splitting rules:**

- Split on **H1** headings first. Each H1 in a multi-section document typically maps to one `TOPIC`. FLS applies `mdx_headdown` at render time, so H1 in a topic body becomes H2 visually — this is intentional; the topic `title` frontmatter is the rendered H1.
- If the source document has no H1 (uses H2 as top-level sections), use H2 as the split boundary.
- Do not split on H3 or lower — these become subsections within a topic.
- A useful reference tool is [mdsplit](https://pypi.org/project/mdsplit/0.3.1/) (Python; `pip install mdsplit`), which splits at a chosen heading level, naming files after heading text and writing to subdirectories. The conversion skill can use the same logic without requiring the tool to be installed.

**Title/subtitle/description derivation rules (without inventing content):**

- `title`: the heading text that caused the split (e.g. the H1 or H2). Strip leading `#` characters and trim whitespace. Never paraphrase or rewrite.
- `subtitle`: the first sub-heading below the split point (the first H2 or H3 under the split H1), if one exists. If none, omit — the field is `| None`.
- `description`: the first non-heading paragraph of the section, if it reads as introductory (not a numbered list, code block, or widget invocation). Limit to the single paragraph; do not concatenate. If none exists, omit.
- `content_type`: always set explicitly.
- `uuid`: **omit entirely** — `content_save` writes it on first load. Never invent a UUID.

**Numbering and folder layout:**

FLS uses numeric prefixes on filenames and folder names. Discovery order is alphabetical, so numbering must be zero-padded consistently:

```
my-course/
  course.md
  images/
  01. Getting Started/
    part.yaml
    01. introduction.md
    02. key-concepts.md
  02. Deep Dive/
    part.yaml
    01. the-detail.md
    02. another-topic.md
    03. knowledge-check/
      form.md
      1. page.yaml
```

Rules:
- Two-digit prefix (`01.`, `02.` ... `09.`, `10.`) for directories and topic files.
- Single-digit prefix (`1.`, `2.`) for form pages inside a form directory (see `demo_content/functionality_demo_end_with_quiz/3. quiz/`).
- Slug is kebab-case derived from the heading text: lowercase, spaces to hyphens, remove punctuation. Never invent slugs — derive from actual heading text.
- If the source has no inherent ordering, preserve the document order.

**Image handling:**

- Place all images in an `images/` subdirectory at the course level (or at the course-part level if images are part-specific).
- Rewrite `![alt](path/to/image.jpg)` as `<c-picture src="images/image.jpg" alt="alt" title="..."></c-picture>`. The `title` comes from the image's surrounding caption or alt text; do not invent text.
- Obsidian `![[image.jpg]]` and `![[image.jpg | title]]` — FLS's `content_save` already translates these to `<c-picture>` automatically at save time (documented in `docs/product/content-editing-workflow.md`). The conversion skill should **leave `![[...]]` syntax as-is** when the source uses Obsidian notation; no rewrite needed for this case.
- Rewrite only `![alt](url)` standard markdown syntax that points to local files. Remote `https://` image URLs should be noted as needing manual download/placement, not silently dropped.

---

## 2. Mapping Markdown Constructs to Widgets

The principle is **conservative by default**: plain markdown stays as plain markdown. Widgets add semantic meaning and UI behaviour; they should only be introduced when the source clearly signals that intent, or when the structural conversion (e.g. image `![]()` to `c-picture`) is unambiguous and lossless.

### Safe/Automatic Conversions (no author confirmation needed)

| Source construct | FLS output | Notes |
|---|---|---|
| `![alt](local-path.jpg)` | `<c-picture src="images/..." alt="..." title="..."></c-picture>` | Lossless; alt and title derived from source |
| `![[image.jpg]]` (Obsidian) | Leave as `![[image.jpg]]` | `content_save` handles this |
| Fenced code block ` ```lang ` | Standard fenced code block | FLS renders these natively; `c-code-block` is only needed for title/language-label display. Leave as fenced unless title is needed. |
| GFM table | Leave as GFM table or wrap in `<c-table caption="...">` if a caption exists nearby | FLS renders GFM tables natively. Wrap only if caption text is present. |
| Heading structure | Split into frontmatter `title`/`subtitle` and body headings | Automatic as part of the split |
| YouTube link `https://www.youtube.com/watch?v=ID` | `<c-youtube video_id="ID"></c-youtube>` | Unambiguous URL pattern |

### Needs Author Confirmation (propose, do not apply automatically)

| Source construct | Proposed widget | Why it needs review |
|---|---|---|
| Blockquote (`> ...`) | `c-pull-quote` or `c-admonition type="note"` | Blockquotes are used for many things: cited quotes, sidebar notes, general emphasis. The author must decide. |
| Bold paragraph that looks like a callout ("**Warning:** ...") | `c-admonition type="warning"` | Pattern-matching on bold text is unreliable; might be inline emphasis, not a callout. |
| Definition list or Q&A pairs | `c-flashcard` | Author must confirm this is intended as recall practice, not just formatted prose. |
| Section with collapsed detail ("Optional reading", "For advanced users") | `c-accordion` | The semantic intent (hide-by-default) must be confirmed. |
| Paragraph starting with "Key takeaways:" followed by a list | `c-admonition type="key_takeaways"` | Strong signal but should be confirmed. |
| Checklist `- [ ] item` | `c-admonition type="checklist"` | Might be a task list, not a reading checklist. |
| Set of images that appear in sequence | `c-image-grid` | Layout preference; depends on intent. |
| LaTeX-style math (`$...$` or `$$...$$`) | `c-equation` | Equations must have their `<`, `>`, `&` escaped for the sanitiser; this is a semantic transform the author must verify. |

### Do Not Widgetise

- Inline formatting (`**bold**`, `*italic*`, `code`) — leave as-is.
- Ordered and unordered lists — leave as-is.
- Hyperlinks `[text](url)` — leave as-is (unless it is a YouTube URL as above).
- Standard blockquotes used for general emphasis — leave as-is if no other signal.
- Horizontal rules `---` — leave as-is or remove if they were used only to separate sections that are now split into separate files.
- Any HTML that is already valid FLS widget syntax — leave untouched.

**Key rule: if in doubt, leave it as plain markdown.** The author's prose must never be rewritten. A conservative conversion that underuses widgets is always safer than one that over-structures.

---

## 3. Content-Preservation Guarantees

The hardest constraint: **no substantive content must be altered**. This is a structural/format conversion, not an editorial one.

### Concrete Techniques

**1. Three-phase pipeline with explicit boundaries**

Separate the conversion into three distinct phases that each produce a reviewable artefact:

- **Phase A — Parse**: Read source markdown(s), extract headings, paragraphs, code blocks, images, and other leaf elements. Produce a structured representation (Python dataclass or dict). No output files written yet.
- **Phase B — Map**: Apply mapping rules to produce the FLS file tree in memory. Identify ambiguous constructs (blockquotes, etc.) and flag them. No output files written yet.
- **Phase C — Write (dry run or live)**: Write output files. In dry-run mode, print the proposed file tree and the proposed content of each file without writing them.

**2. Dry-run / preview mode**

All conversion tools should default to dry-run. The author sees exactly what will be written before anything changes. This is standard in CMS migration tooling: Sanity's migration CLI runs in dry-run mode by default and requires `--no-dry-run` to make actual changes (https://www.sanity.io/docs/content-lake/schema-and-content-migrations). The FLS conversion skill should follow the same pattern.

**3. Text-content diff**

After conversion, extract all prose text from the output files (stripping frontmatter YAML, widget tags, and heading markers) and compare it with the prose text extracted from the source. The comparison should show:
- Words/sentences present in source but absent from output (loss).
- Words/sentences present in output but absent from source (addition — should only be the structural wrapping, i.e. frontmatter keys).

A zero-loss result means the body text is fully preserved. This can be done with Python's `difflib` or a simple word-count check; the goal is not a character-perfect diff but a content-completeness check.

**4. Separation of structural vs. content changes**

The conversion report should explicitly label each change as one of:
- **Structural** (new file created, heading promoted to frontmatter title, image path rewritten) — always safe.
- **Widget wrap** (blockquote proposed as `c-admonition`) — requires author sign-off.
- **Content** (prose altered in any way) — must never happen; if the tool detects this, it must abort or flag the specific change.

**5. No in-place editing of source**

Output is always written to a new directory, never in-place modification of the source. This gives the author a before/after comparison using any diff tool.

**6. Flagging ambiguous constructs in the report**

The conversion produces a short report listing:
- Files created and their source section.
- Widgets auto-applied (e.g. YouTube URLs converted).
- Ambiguous constructs flagged for author review, with line numbers in the source.
- Images that could not be resolved (e.g. remote URLs needing manual download).

Reference: Airbnb's LLM migration workflow flags migrations below a confidence threshold for manual review, and developers review suggestions before committing (https://medium.com/airbnb-engineering/accelerating-large-scale-test-migration-with-llms-9565c208023b). The same approach applies here: low-confidence mappings are flagged, not silently applied.

---

## 4. Single File vs Directory

### Single File Input

A single markdown file is most likely one of:
- A single topic (the whole file becomes one `TOPIC`).
- A multi-section document that needs splitting into multiple `TOPIC` files.

**Decision rule**: if the file has more than one H1 (or more than one H2 in an H2-first document), offer to split. If it has exactly one H1 (or zero), treat it as a single topic.

**Output structure for a single file that becomes one topic:**

```
output-slug/
  course.md           <- generated from filename or H1
  1. slug.md          <- the topic content
  images/             <- any referenced images
```

The author can then rename, add more topics, and flesh out the `course.md` frontmatter.

**Output structure for a split single file:**

```
output-slug/
  course.md
  01. first-heading.md
  02. second-heading.md
  images/
```

### Directory Input

A directory of markdown files is likely a whole course or a course part. The conversion must infer the structure from the directory layout and filenames.

**Mapping rules:**

- If the directory contains a single flat level of `.md` files: treat each file as a `TOPIC`; generate a `course.md` with title inferred from the directory name.
- If the directory has subdirectories: each subdirectory becomes a `COURSE_PART`; `.md` files inside each subdirectory become `TOPIC`s.
- If a file already has FLS-style frontmatter (`content_type:` key present): leave it as-is. Do not re-convert already converted files.

**Idempotency:**

Idempotency is critical — running the conversion twice must produce the same result, and running it on already-converted content must not corrupt it.

Rules for idempotent behaviour:
1. Detect FLS frontmatter: if a `.md` file already has `content_type:` in its frontmatter, skip it.
2. If a `course.md` already exists in the output, do not overwrite it (or only overwrite explicitly flagged fields).
3. UUID fields: if a `uuid:` field is present in the frontmatter (written by a previous `content_save` run), never touch it.
4. Do not re-number files that already have numeric prefixes matching the expected pattern.

**Re-running on partially converted content:**

The tool should skip any file that already has `content_type:` frontmatter, then process only the remaining unconverted files. This enables incremental conversion of a directory that was partially converted previously.

---

## 5. Common Pitfalls and Complaints

These are documented failure modes from the broader markdown-to-structured-content ecosystem:

**1. Broken tables**

GFM tables with merged cells or complex headers do not convert cleanly. Standard `|---|` table syntax is fine; any table using `colspan` or `rowspan` cannot be expressed in GFM at all. Recommendation: detect tables that use HTML `<table>` syntax in the source and wrap them in `<c-table>` but otherwise leave the HTML intact, since FLS's sanitiser allows `scope` attributes on `<th>` elements. Reference: Microsoft Azure Document Intelligence changed table representation in 2024-07-31-preview from markdown to HTML tables because "Markdown can't represent everything HTML can" (https://learn.microsoft.com/en-us/answers/questions/2111913/concerns-regarding-the-tables-in-markdown-output-c).

**2. Smart quotes and typographic characters**

Pandoc and many editors insert "smart quotes" (`"`, `"`, `'`, `'`), em-dashes (`—`), and ellipses (`…`) as Unicode characters. These are fine in UTF-8 content (FLS stores UTF-8). The risk is when they appear inside YAML frontmatter values — YAML requires careful quoting of strings containing these characters. The conversion tool must wrap frontmatter string values in double quotes and escape any embedded double quotes. Never strip smart quotes from prose — that changes content.

Reference: pandoc documents issues with smart quote Unicode normalization in CommonMark mode (https://github.com/jgm/pandoc/issues/8341).

**3. Heading level mismatches**

Source documents often skip heading levels (H1 → H3, no H2 in between) or use all-H2 structures. FLS renders topic body content with `mdx_headdown` — H1 in the body becomes H2. This is usually invisible but means a document using H1 for sections and H2 for sub-sections in its body will render with H2 and H3, which is correct. However, if the source skips from H1 to H3, the output will have H2 and H4, creating a heading gap. The conversion tool should warn when heading levels are skipped in the source body but should not alter the heading text (that would change content).

Reference: Heading best practices state "never skip a heading level — do not go from H2 to H4 without an H3" (https://allmarkdowntools.com/blog/how-to-heading-in-markdown).

**4. Lost formatting in YAML frontmatter**

When the conversion extracts a heading or first paragraph as the `description` field, special characters (`&`, `<`, `>`, `:`, `{`, `}`) can corrupt the YAML. Always quote all string values in generated frontmatter. Never use bare string values for `title`, `subtitle`, or `description` in generated YAML if any of these characters are present.

**5. Mangled links and image references**

Relative links (`[see here](../other-topic.md)`) may break if the conversion changes the directory structure. The tool should:
- Detect all relative links in the source.
- Rewrite them using FLS's `<c-content-link path="...">` widget only if the target file is also part of the converted course.
- Otherwise, flag the link for manual review rather than silently dropping or breaking it.

**6. Frontmatter clobbering**

If the source markdown already has YAML frontmatter (e.g. from a Jekyll or Hugo site), the conversion must merge it with FLS frontmatter, not replace it. Extract the existing title/description from source frontmatter first before falling back to heading detection.

**7. Setext headings**

Setext-style headings (underlined with `===` or `---`) are not recognised by `mdsplit` and may cause issues with heading-based splitting logic. The tool should convert setext headings to ATX (`#` prefix) before processing. This is a purely structural normalisation and does not alter content.

Reference: https://github.com/markusstraub/mdsplit — "Only ATX headings such as `# Heading 1` are supported. Setext headings (underlined headings) are not recognised."

---

## 6. Validation Loop

### What Can Be Checked Without FLS

The FLS Pydantic schema (`freedom_ls/content_engine/schema.py`) and the validation logic (`freedom_ls/content_engine/validate.py`) can be extracted into the plugin as a **standalone validator** that does not require a database or Django.

Key facts from reading the source:
- `validate.py` imports only `frontmatter`, `yaml`, and `pydantic` — no Django ORM, no database.
- The validator reads files and instantiates Pydantic models. The only Django-dependent validator is the `Course._validate_icon_fields` model validator (which calls `freedom_ls.content_engine.icon_validation`). This can be skipped in standalone mode by catching `ImportError`.
- `extra="forbid"` means any unrecognised frontmatter key causes validation to fail with a clear error — this catches typos and obsolete fields immediately.

**Recommended standalone validation approach:**

Bundle a copy of `schema.py` and `validate.py` in the plugin as `course_plugin/validate/`. Strip or mock the Django-dependent `_validate_icon_fields` validator. Authors can run `python course_plugin/validate/validate.py <path>` without installing FLS.

This gives full Pydantic schema validation — required fields, `extra="forbid"`, type checks on all fields — without needing the FLS source. The validation output format (`freedom_ls/content_engine/validate.py` lines 113–133) is already user-friendly with field paths and error messages.

### What Requires FLS

- UUID assignment (write-back to frontmatter after `content_save`) — only happens via the management command.
- Icon field validation (calls into FLS icon resolution logic).
- Cross-reference resolution (`c-content-link path="..."` target existence).

For the plugin, these are documented as "run `content_save` on the FLS host to complete validation" — the standalone validator covers structural correctness, and `content_save` covers the rest.

### Validation Sequence

The recommended validation loop for converted content:

1. **Standalone schema validation**: run the bundled validator. Fix any `extra="forbid"` errors, missing required fields, or type errors.
2. **Content completeness check**: run the prose-diff check (Phase 3 above). Confirm zero content loss.
3. **Widget syntax spot-check**: open a sample topic in a text editor and verify that `<c-*>` tags are well-formed (balanced open/close, no unclosed tags, correct attribute names).
4. **FLS install (if available)**: run `python manage.py content_validate <path>` for the full validation including icon resolution and cross-references.
5. **FLS save**: run `python manage.py content_save <path> <site>` — this is the authoritative pass; UUIDs are written back.

Step 4 can be skipped if the author does not yet have an FLS install. Steps 1–3 are entirely self-contained in the plugin.

---

## Recommendations Summary

1. **Conservative widget mapping**: auto-convert only unambiguous constructs (images, YouTube URLs, fenced code that needs a title). Propose other widget conversions with a review flag; never auto-apply them.

2. **Heading-based splitting**: split at H1 (or H2 if no H1 present), derive title from heading text, derive subtitle from first sub-heading, derive description from first introductory paragraph. Never rephrase or invent text.

3. **Dry-run first, always**: default to dry-run mode; show the proposed file tree and content before writing anything. Authors must explicitly confirm before files are written.

4. **Idempotency guard**: skip any file that already has `content_type:` frontmatter; never touch existing `uuid:` values.

5. **Bundled standalone validator**: ship a copy of `schema.py` and `validate.py` (minus the Django-dependent icon validator) so authors can validate their output without needing the FLS source.

6. **Prose-diff report**: after conversion, produce a report showing prose word counts (source vs output), all auto-applied changes, and all flagged-for-review items with source line numbers.

---

## Web Sources

- [mdsplit — Split markdown files at headings (PyPI)](https://pypi.org/project/mdsplit/0.3.1/)
- [markusstraub/mdsplit (GitHub)](https://github.com/markusstraub/mdsplit)
- [Sanity CMS content migration — dry run and review workflow](https://www.sanity.io/docs/content-lake/schema-and-content-migrations)
- [Important considerations for schema and content migrations — Sanity Docs](https://www.sanity.io/docs/content-lake/important-considerations-for-schema-and-content-migrations)
- [Concerns regarding tables in markdown output changes in 2024-07-31-preview — Microsoft Learn](https://learn.microsoft.com/en-us/answers/questions/2111913/concerns-regarding-the-tables-in-markdown-output-c)
- [Pandoc: smart quotes / unicode normalization issues — GitHub issue](https://github.com/jgm/pandoc/issues/8341)
- [Markdown heading best practices — allmarkdowntools.com](https://allmarkdowntools.com/blog/how-to-heading-in-markdown)
- [Accelerating large-scale test migration with LLMs — Airbnb Engineering Blog](https://medium.com/airbnb-engineering/accelerating-large-scale-test-migration-with-llms-9565c208023b)
- [What a diff makes: automating code migration with LLMs — arXiv](https://arxiv.org/html/2511.00160v1)

---

status: ok
