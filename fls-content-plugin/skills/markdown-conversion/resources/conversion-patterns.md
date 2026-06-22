<!-- Source: research_markdown_conversion.md §2 (auto/propose/never table), spec §7 (conversion behaviour, heading handling, existing-widget handling, idempotency), research_authoring_format.md §6 (Obsidian syntax) -->

# Conversion Patterns

## 1. Auto / Propose / Never table

### Auto-apply (lossless — no author confirmation needed)

| Source construct | FLS output | Notes |
|---|---|---|
| `![alt](local-path.jpg)` | `<c-picture src="images/..." alt="..." title="...">` | Derive `title` from surrounding caption; emit `alt=""` and flag if no alt text available |
| `![[image.jpg]]` (Obsidian) | `<c-picture src="image.jpg"></c-picture>` | Expand during conversion — `content_save`'s built-in translation drops alt text |
| `![[image.jpg \| title]]` (Obsidian) | `<c-picture src="image.jpg" title="title"></c-picture>` | Flag if no alt text to set |
| YouTube watch URL `https://www.youtube.com/watch?v=ID` | `<c-youtube video_id="ID"></c-youtube>` | Unambiguous URL pattern |
| Setext heading `===`/`---` underlines | ATX `#`/`##` equivalent | Purely structural normalisation; do this before any other heading step |
| Heading promoted to frontmatter `title` | Removed from body | The heading text goes into `title:`; the body starts after it |
| Body heading re-levelling | Shift headings so top section is `#` | After title lifting, promote remaining headings to start at `#` |

### Propose only (list in `_conversion_review.md`, never apply silently)

| Source construct | Proposed widget | Why it needs author review |
|---|---|---|
| Blockquote (`> ...`) | `c-pull-quote` or `c-admonition` | Blockquotes serve many purposes — author must decide |
| Bold callout ("**Warning:** …") | `c-admonition type="warning"` | Pattern-matching on bold text is unreliable |
| Q&A pairs or definition lists | `c-flashcard` | Author must confirm intent is recall practice |
| Section with "Optional reading" / "For advanced users" | `c-accordion` | Semantic intent (hide-by-default) must be confirmed |
| "Key takeaways:" followed by a list | `c-admonition type="key_takeaways"` | Strong signal but must be confirmed |
| Checklist `- [ ]` items (non-task context) | `c-admonition type="checklist"` | May be a task list, not a reading checklist |
| Set of images that appear in sequence | `c-image-grid` | Layout preference; depends on author intent |
| LaTeX math (`$...$` or `$$...$$`) | `c-equation` | Equations require HTML escaping — author must verify |

### Leave alone (never widgetise)

- Inline formatting (`**bold**`, `*italic*`, `` `code` `` )
- Ordered and unordered lists
- Hyperlinks `[text](url)` (unless it is a YouTube URL as above)
- Standard fenced code blocks ` ``` ` (leave as fenced unless a title is needed — FLS renders them natively)
- GFM tables (leave as-is unless a caption exists nearby; then wrap in `<c-table caption="...">`)
- Horizontal rules `---`
- Any existing `c-*` widget that is already correct

---

## 2. Heading-handling rules

Apply in this order:

1. **Normalise setext headings to ATX first.** Convert `===`/`---` underlines to `#`/`##` before any other step.

2. **Identify the title heading.** The H1 (or first H2 if no H1) becomes the frontmatter `title`. Strip the `#` markers and trim whitespace. **Never paraphrase or rewrite the heading text.**

3. **Identify subtitle and description (optional).**
   - `subtitle`: the first sub-heading immediately below the split point (if any); omit if none.
   - `description`: the first non-heading, non-list, non-code, non-widget paragraph below the title (if it reads as introductory); omit if none.

4. **Remove the title (and subtitle if lifted) from the body.** The page template renders the frontmatter `title` as the visible H1 — repeating it in the body produces two H1s.

5. **Re-base the body heading hierarchy.** After the title is lifted out, promote all remaining body headings so the topmost section is `#` (H1). This preserves relative nesting depth. Only the `#` marker count changes; heading **text is never altered**.
   - Example: if the remaining body starts at `##`, shift everything down by one: `##` → `#`, `###` → `##`, etc.

6. **Flag skipped levels, never rewrite them.** If the source skips a heading level (e.g. `#` then `###` with no `##`), add a note to `_conversion_review.md` with the source line number. Do not insert or renumber headings — that risks changing meaning.

**Why this matters:** FLS applies `mdx_headdown` at render time, shifting every body heading down one level (`#` → H2, `##` → H3, …) so body content nests beneath the page-title H1. A correct body starts at `#`.

---

## 3. Existing-widget normalisation rules

Source content may already contain `c-*` widgets — hand-written, pasted, or produced by an older tool — and they are frequently subtly wrong. Treat each existing widget as structure to validate, not prose to leave alone.

| Widget state | Action |
|---|---|
| Already correct (valid name, correct attributes, correct form) | Leave untouched |
| Attribute outside the allowlist | Remove the disallowed attribute (sanitiser would strip it silently) |
| `c-image-grid` child in self-closing form `<c-picture .../>` | Rewrite to closed form `<c-picture ...></c-picture>` |
| Missing blank lines before/after children in `c-image-grid` or `c-flashcard` slots | Insert blank lines |
| `c-accordion open` with a value | Normalise to bare `open` attribute |
| Unescaped `<`, `>`, `&`, `"` in `c-code-block` or `c-equation` body | Escape to `&lt;`, `&gt;`, `&amp;`, `&quot;` |
| Unknown `c-*` name (not in the allowlist) | Flag in `_conversion_review.md` — never emit as-is |
| `c-admonition type` not in the active set | Flag in `_conversion_review.md` — never emit a silently-wrong `default`-rendering value |

**Only widget syntax, attributes, and structure change — never the prose inside a widget.** Normalising an existing widget is a structural transform.

---

## 4. Idempotency rules

The converter checks everything; it fixes only what is broken.

- The presence of `content_type:` frontmatter does **not** mean the file is correct — every file (Markdown and pure-YAML alike) has its frontmatter, widgets, naming, and placement checked.
- **Never touch an existing `uuid:`** — not even if the field looks wrong.
- **Never re-split, re-paraphrase, or rewrite prose that is already structured.** Only broken structure and syntax are fixed.
- Running on already-correct content produces no changes.
- Running on partially converted content fixes only what remains broken.

---

## 5. `_conversion_review.md` — written only when there is something to flag

This is **not** a changelog. Git records what changed — auto-applied lossless changes are left to the `git diff` and are **not** listed.

The review file is written only when at least one of these exists:

- Proposed-but-not-applied semantic conversions (blockquote → admonition, Q&A → flashcard, etc.)
- Things the converter could not resolve: missing alt text, unknown widget name, out-of-set `c-admonition type`, skipped heading level, remote image URLs needing manual download, links to targets outside the converted set
- Any concern that substantive prose may have been lost or added

Each item includes the source-line reference. The file ends by reminding the author to resolve items, review the `git diff`, run `/fls-content:validate-content`, and delete `_conversion_review.md` before `content_save`.

**If nothing needs the author's attention, no `_conversion_review.md` is written.**

---

## 6. Frontmatter safety rules

- Quote all generated string values — prevents YAML corruption from `:`, `&`, `<`, `>`, `{`, `}` in titles and descriptions.
- Merge (do not clobber) any pre-existing YAML frontmatter — extract existing `title`/`description` from source frontmatter before falling back to heading detection.
- `uuid:` is never written — omit it entirely on new files; never touch it on existing files.

---

## 7. Admonition types from the project config

When proposing a blockquote/callout → `c-admonition`, only propose a `type` that is present in `.fls-content.yaml` (or the base set as fallback). An intended type not in the active set is flagged in `_conversion_review.md`, never emitted as a silently-wrong `default`-rendering value.

For the base set and deployment-configurable admonition types, see the `fls-content:widget-reference` skill.
