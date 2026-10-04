# Research: where the fls-content plugin assumes a closed widget list

Codebase findings only. Paths are relative to the project root.

## Files that assume FLS's widgets are the only widgets

**`claude_plugins/fls-content/skills/widget-reference/SKILL.md`** is the main touchpoint.
- The frontmatter `description` (the skill's trigger text) says "Every FLS c-* widget".
- Line 9 says "**The allowlist is closed — you cannot invent new `c-*` names.**"
- The "All widgets at a glance" table is hard-coded to the 15 FLS widgets.
- The "Authorised attribute sets (complete allowlist)" block hard-codes each widget's attributes and
  says it "equals the `MARKDOWN_ALLOWED_TAGS` allowlist exactly".
- The closing link list points at the 15 `resources/c-*.md` files, one per widget. A custom widget
  has no home for its reference inside the plugin.
- The "Admonition types are deployment-configurable" section is the existing template for "read the
  repo's `.fls-content.yaml`, not the base set".
- Each `resources/c-*.md` repeats the "silently stripped" note. Those files describe built-ins and
  stay as they are.

**`claude_plugins/fls-content/skills/markdown-conversion/resources/conversion-patterns.md`**
- Line 73: "Attribute outside the allowlist → Remove the disallowed attribute". A custom widget's
  attributes would be removed.
- Line 78: "Unknown `c-*` name (not in the allowlist) → Flag in `_conversion_review.md` — never emit
  as-is". Line 104 repeats it. This is the behaviour `docs/how tos/custom-content-widgets.md`
  complains about.
- Line 39 leaves "Any existing `c-*` widget that is already correct" alone, so "correct" has to
  include custom widgets.
- Section 7 is the admonition precedent: propose only a `type` listed in `.fls-content.yaml`.

**`claude_plugins/fls-content/agents/content-formatter.md`**
- Describes `widget-reference` as "the widget allowlist, attribute sets, quirks, HTML-escaping rule".
- Step 2 reads `./.fls-content.yaml` for `admonition_types` only, and returns `status: blocked` if
  the file is missing.

**`claude_plugins/fls-content/commands/init.md`** scaffolds and reports on `admonition_types` and
`access_types` only. Its "Constraint reminder" says it writes three things.

**`claude_plugins/fls-content/commands/format-content.md`** checks `.fls-content.yaml` exists and lets
each agent read it. Little or no change.

**`claude_plugins/fls-content/commands/validate-content.md`** says "never make semantic widget
decisions". Widgets are not in its list of checks.

**Pointers only, no closed-list wording:** `skills/content-types/SKILL.md`,
`skills/content-types/resources/topic-files.md`, `skills/content-types/resources/file-layout.md`,
`skills/conventions/SKILL.md`, `skills/markdown-conversion/SKILL.md` each point at
`fls-content:widget-reference`.

**`claude_plugins/fls-content/README.md`** says init scaffolds "the repo's admonition- and
access-type config".

**Docs outside the plugin** that state the gap:
- `docs/how tos/custom-content-widgets.md`, "Telling your authors": the plugin "only knows FLS's
  built-in widgets... treats the allowlist as closed, and nothing in `.fls-content.yaml` declares
  extra widgets".
- `docs/product/content-editing-workflow.md` describes the plugin and init as declaring admonition
  types only.

## The validator does not check widgets

A grep of `claude_plugins/fls-content/validate/` for `c-`, `MARKDOWN_ALLOWED` and `widget` finds
nothing. The validator checks frontmatter and schema, never the Markdown body. All widget handling
is done by the agent through the skills and `content-formatter`.

## The `.fls-content.yaml` precedent

- Lives at `Path.cwd() / ".fls-content.yaml"`, the content repo root. It is never searched for.
- `validate.py` `_load_allowed_access_types()` reads `access_types`. A missing or malformed file is a
  hard error pointing at `/fls-content:init`. A non-empty list replaces the base set. An absent key
  falls back to the shipped default.
- The validator does not read `admonition_types`. Only the agent does, through `content-formatter`
  Step 2, `conversion-patterns.md` section 7 and the skill text.
- Init writes a verbatim template when the file is absent. When it exists, init reports each list
  against its base set and leaves the file "byte-for-byte untouched".
- Dot-prefixed files are not scanned as content (`skills/content-types/resources/file-layout.md`
  line 100).

## How the plugin reaches content repos

- Distribution is undecided. The course-editing-plugin spec put shipping "to source-less downstream
  projects" out of scope. The split-claude-plugin spec says `fls-content` was "Relocated unchanged"
  and the repo loads plugins with `--plugin-dir`, with no marketplace. Versioning is `plugin.json`
  1.0.0 plus git SHA.
- `/fls-dev:update_claude_plugin_fls_content` keeps the plugin in sync with FLS one way. It edits
  skill sections and re-copies the validator from FLS sources, re-applying a patch list.
- So the plugin's files are regenerated from FLS. Anything a consumer adds must live in the content
  repo, outside the plugin, or a re-sync or re-copy overwrites it.

## Where FLS keeps widget data

- `config/settings_base.py` `MARKDOWN_ALLOWED_TAGS`: 15 entries, matching the skill's list.
  `freedom_ls/markdown_rendering/config.py` defaults it to `{}`, and a concrete project's setting
  replaces it whole.
- Built-in cotton templates: `freedom_ls/content_engine/templates/cotton/` and
  `freedom_ls/base/templates/cotton/`. A concrete project adds its own in any app's `templates/cotton/`.
- No management command exports the widget list.
- The concrete project and the content repo are separate repos. The content repo cannot read the
  project's settings, so whatever the plugin learns about custom widgets has to arrive as files in
  the content repo.

## Claude Code mechanics seen in this repo

- Plugin skills are namespaced (`fls-content:widget-reference`). Project `.claude/skills/` are
  separate. Nothing in the repo shows the two merging.
- `.fls-content.yaml` is the one existing case of the plugin reading a consumer-owned file at
  runtime, and it depends on cwd being the content repo root.

status: ok
