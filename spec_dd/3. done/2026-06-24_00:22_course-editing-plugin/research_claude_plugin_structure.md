# Research: How to author the course-author Claude Code plugin

Sources: in-repo `fls-claude-plugin/` structure and `skills/claude-code-authoring/` (primary);
demo_content/ for content-type reference; Anthropic Claude Code docs cited in subagents.md and
model_tiering.md.

---

## 1. Plugin anatomy

### Minimum required files

A Claude Code plugin needs exactly one mandatory file:

```
<plugin-root>/.claude-plugin/plugin.json
```

`plugin.json` has three fields (see `fls-claude-plugin/.claude-plugin/plugin.json`):

```json
{
  "name": "fls-content",
  "version": "1.0.0",
  "description": "FLS course-authoring conventions, content types, widget reference, and markdown conversion"
}
```

`name` is the namespace used to invoke skills and agents (`fls-content:<agent-name>`) and to reference
the plugin root via `${CLAUDE_PLUGIN_ROOT}`. Everything else in the plugin is optional but follows the
layout of the existing `fls-claude-plugin/`.

### Full layout for the new plugin

The plugin must live in its own directory at the repo root (sibling to `fls-claude-plugin/`).
Proposed name: `fls-content-plugin/`.

```
fls-content-plugin/
├── .claude-plugin/
│   └── plugin.json                  # name: "fls-content", version, description
│
├── skills/
│   ├── content-types/
│   │   ├── SKILL.md                 # frontmatter + summary; delegates to resources/
│   │   └── resources/
│   │       ├── file-layout.md       # directory structure, numbering conventions
│   │       ├── topic-files.md       # .md topic frontmatter reference
│   │       ├── form-files.md        # form.md + page.yaml reference
│   │       └── course-files.md      # course.md + part.yaml reference
│   │
│   ├── widget-reference/
│   │   ├── SKILL.md                 # frontmatter + summary; delegates to resources/
│   │   └── resources/
│   │       ├── media-widgets.md     # c-youtube, c-picture, c-image-grid, c-pdf-embed, c-file-download
│   │       ├── interactive-widgets.md  # c-admonition, c-flashcard, c-accordion, c-card
│   │       ├── structured-widgets.md   # c-table, c-code-block, c-pull-quote, c-equation
│   │       └── content-link.md      # c-content-link, path resolution rules
│   │
│   ├── conventions/
│   │   └── SKILL.md                 # numbering, UUIDs, file naming — self-contained (no resources/ needed)
│   │
│   └── markdown-conversion/
│       ├── SKILL.md                 # when and how to convert; delegates to resources/
│       └── resources/
│           └── conversion-patterns.md  # mapping from common messy patterns to FLS structure
│
├── commands/
│   └── convert-markdown.md          # slash command: /fls-content:convert-markdown
│
└── agents/
    └── content-converter.md         # Sonnet agent for conversion fan-out
```

No `hooks/`, `.mcp.json`, or `scripts/` needed for this plugin — those are developer concerns.
The existing `fls-claude-plugin/` hooks still apply to the repo.

---

## 2. Skill design

### SKILL.md structure

Every skill SKILL.md follows this pattern (drawn from `fls-claude-plugin/skills/`):

```markdown
---
name: <skill-name>
description: <one or two sentences — this is what Claude reads to decide whether to invoke the skill>
allowed-tools: Read, Grep, Glob
---

# When to use this skill
<bullet list of trigger situations>

# Key rules / summary
<self-contained reference covering the most common cases>

Refer to `${CLAUDE_PLUGIN_ROOT}/resources/<file>.md` for full details and examples.
```

The `description` frontmatter field is the **trigger**. Claude loads skills whose description matches
the current task. Key observations from the existing skills:

- `testing` skill description: "Write pytest tests. Use when implementing features, fixing bugs, or
  when the user mentions testing, TDD, or pytest" — explicit keyword enumeration plus task context.
- `markdown-content` skill description: "Work with markdown content system… Use when working with
  content models or adding markdown components." — lead with what you do, follow with when.
- `icon-usage` skill description: "Use this skill when making use of any icons in any part of the
  frontend." — trigger phrase first.

**Pattern:** `<action phrase> when <condition list>`. Be concrete about keywords authors will use
("widget", "quiz", "form page", "UUID", "convert").

### Description trigger guidelines for author-facing skills

The descriptions for the new skills should cover the words a course author is likely to type, not
developer terms:

- `content-types`: trigger on "topic", "form", "quiz", "survey", "course", "course part", "chapter",
  "module", "content file"
- `widget-reference`: trigger on widget names ("admonition", "flashcard", "accordion", "youtube",
  "picture", "table", "code block", "card", "pull quote", "equation") plus "widget", "component"
- `conventions`: trigger on "UUID", "numbering", "file name", "order", "directory", "folder"
- `markdown-conversion`: trigger on "convert", "messy markdown", "restructure content", "import",
  "paste content"

### Splitting SKILL.md vs resources/

Rule: **SKILL.md is the fast-load summary; resources/ hold the full reference.**

From the pattern in `skills/testing/SKILL.md` (long, self-contained) vs `skills/markdown-content/SKILL.md`
(short, delegates to `resources/markdown_content.md`):

- If the skill body fits in ~50–80 lines and covers the 80% case without padding, keep it in SKILL.md.
- If the body needs exhaustive tables of options, multi-example walkthroughs, or format specs that
  don't need to be in context for every invocation, push them to `resources/` files.

For this plugin:
- `conventions/SKILL.md` — keep self-contained. UUID rules, numbering, and file-naming are short and
  must always be in context when authoring any file.
- `content-types/SKILL.md` — short summary + "refer to resources/ for full frontmatter spec"; the
  detailed per-file-type frontmatter goes in resources/.
- `widget-reference/SKILL.md` — summary of all widgets + when to use which; full syntax in resources/.
- `markdown-conversion/SKILL.md` — overview of the conversion process + refer to resources/ for
  patterns.

### How skills reference each other

From `skills/testing/SKILL.md`: "See the `fls:playwright-tests` skill for browser / E2E tests" and
"The `fls:htmx` skill for production-side HTMX rules." The pattern is a plain prose mention with the
namespace-prefixed skill name.

For the new plugin, use `fls-content:` prefix:

```
See the `fls-content:widget-reference` skill for full widget syntax.
See the `fls-content:conventions` skill for UUID and numbering rules.
```

This is documentation only — Claude will not auto-follow the reference; it just primes it to invoke
that skill via the `Skill` tool if needed.

### Concrete skill set

| Skill | SKILL.md length | resources/ files | Trigger keywords |
|---|---|---|---|
| `content-types` | ~40 lines | 4 files | topic, form, quiz, survey, course, part, chapter |
| `widget-reference` | ~60 lines | 4 files | widget names, "component", "admonition" etc |
| `conventions` | ~50 lines | none | uuid, numbering, ordering, file name, folder |
| `markdown-conversion` | ~30 lines | 1 file | convert, messy, import, restructure |

Keep `content-types` and `widget-reference` separate; they're queried for different tasks. A skill
preloaded into an agent (`skills:` frontmatter) loads the full SKILL.md, so a short SKILL.md + deep
resources/ is the right shape for large reference sets.

---

## 3. Commands vs skills for our use cases

### When to use a skill

Skills are the right shape for:
- Reference material that Claude needs in context when doing a task (e.g. writing a topic file,
  inserting a widget).
- Rules that must apply throughout an authoring session without being re-read each time.
- Content that subagents need — skills are auto-loaded or can be preloaded via `skills:` frontmatter.

All four reference concerns (content types, widgets, conventions, UUID rules) should be **skills**.

### When to use a slash command

Commands are the right shape for:
- Multi-step workflows that a user invokes explicitly at a specific moment.
- Tasks that benefit from fan-out (e.g. converting a large markdown document requires reading the
  whole file, splitting into topics, producing structured output for each).
- Tasks where the user provides input at invocation time (`$ARGUMENTS`).

The **markdown-conversion** capability should be a **command** (`/fls-content:convert-markdown`)
backed by the `markdown-conversion` skill. A command can spawn a `content-converter` agent for
larger documents.

### Why not a command for reference?

From `skills/claude-code-authoring/SKILL.md`: "Subagents can't type slash commands. There is no
`SlashCommand` tool inside a subagent." If reference lives in a command rather than a skill, it
cannot be reused inside the conversion agent. Skills are the correct primitive for reference.

### Summary mapping

| Use case | Mechanism | Why |
|---|---|---|
| "What frontmatter does a TOPIC file need?" | Skill `content-types` | passive reference, always available |
| "How do I write an accordion?" | Skill `widget-reference` | passive reference, always available |
| "What are the UUID rules?" | Skill `conventions` | passive reference, always available |
| "Convert this messy markdown" | Command `convert-markdown` | explicit invocation, fan-out, user input |

---

## 4. Self-containment

### Why this matters

Authors won't have the FLS source. They can't read `config/settings_base.py`, `models.py`, or the
Cotton component templates. Every fact they need must be stated literally in the plugin.

### What to include literally in resources/

- All valid `content_type` values: `COURSE`, `COURSE_PART`, `TOPIC`, `FORM`, `FORM_PAGE` — with
  examples of each file's frontmatter.
- All valid FORM `strategy` values: `QUIZ`, `CATEGORY_VALUE_SUM` (and any others).
- All widget names with full attribute tables and at least one copy-pasteable example per variant.
- The complete `MARKDOWN_ALLOWED_TAGS` allowlist (the widgets that actually work), so authors know
  they can't invent new widget names.
- UUID rules: never edit existing UUIDs; generate new ones only with a proper UUID4 generator.
- Numbering conventions: `NN. <name>` prefix on directories and topic files; `part.yaml` identifies
  a course-part directory; `form.md` identifies a form directory.
- Image path rules: `src` on picture/card/image-grid is relative to the current topic file; images
  live in `images/` sibling directory.
- HTML-escaping rules for `c-code-block` and `c-equation` (must escape `<`, `>`, `&` as entities).

### How large can skills get?

The existing `skills/testing/SKILL.md` is ~220 lines and fully self-contained. The `resources/`
pattern (`skills/icon-usage/`, `skills/claude-code-authoring/`) handles larger material by splitting.
A SKILL.md that exceeds ~100 lines should push its examples into resources/. There is no hard limit,
but skill content is loaded into the context window on every trigger, so lean skill bodies keep token
cost low.

Recommended cap: SKILL.md body ≤ 80 lines; overflow goes to resources/. A resources/ file can be as
long as needed — it's only loaded when the SKILL.md refers to it and the agent reads it explicitly.

---

## 5. Naming and namespacing

### Current plugin name

The existing developer plugin is `"name": "fls"` in `fls-claude-plugin/.claude-plugin/plugin.json`.
Its skills are invoked as `fls:<skill-name>` (e.g. `fls:sdd-worker`). Its directory is
`fls-claude-plugin/`.

### Proposed name for the new plugin

```json
{ "name": "fls-content" }
```

This gives:
- Skills: `fls-content:content-types`, `fls-content:widget-reference`, etc.
- Agents: `fls-content:content-converter`
- Commands: `/fls-content:convert-markdown`
- Directory: `fls-content-plugin/`

This namespace is distinct from `fls:` so there is no collision risk. The directory name mirrors the
`fls-<purpose>-plugin/` pattern consistently.

### Do not use `fls:` for the new plugin

Any skill named `fls:X` in the new plugin would clash with the existing developer plugin.
Use `fls-content:` throughout.

---

## 6. Keeping the plugin maintainable

### The core problem: docs drift from the code

From the idea file: "If we change course authoring functionality at all (eg adding new widgets,
frontmatter, content types, etc) then we'll need to update the plugin to match." This is the
maintainability requirement.

### Patterns from claude-code-authoring that apply

**Single source of truth per concern.** The `claude-code-authoring` skill states: "Author
commands/skills/agents against these constraints instead of restating them in every file." Apply
the same rule here: each authoring fact (e.g. the FORM strategy values, the widget attribute table)
should live in exactly one resources/ file. If a fact appears in two places, they will drift.

**Versioned claim.** `claude-code-authoring/SKILL.md` opens with "Target: Claude Code 2.1.x." Add
an equivalent version note to this plugin: "FLS content system as of <date/version>." This tells a
maintainer immediately whether the plugin matches the current codebase.

**Keep resources/ files auditable.** Resources are plain markdown files with explicit tables and
examples. When a new widget is added to FLS, the change is obvious: add a row to the attributes
table in the relevant resources/ file and add an example. No code to understand, just doc to write.

**Map plugin resources to source files.** In a comment at the top of each resources/ file, record
which FLS source file(s) it was derived from. For example:

```markdown
<!-- Source: config/settings_base.py (MARKDOWN_ALLOWED_TAGS), demo_content/*/TOPIC.md -->
```

This makes updating trivial: when FLS adds a widget, the maintainer opens the corresponding
resources/ file and updates it.

**Don't auto-generate.** Tempting to make the plugin auto-derive from the running codebase, but
that breaks the self-containment requirement (authors don't have the source). Keep resources/ as
hand-maintained, human-readable reference files.

**Conversion skill = the highest-maintenance item.** The `markdown-conversion` skill and command
will encode transformations from messy input to FLS structure. As the format evolves, these patterns
must be updated. Keep conversion patterns in a single `resources/conversion-patterns.md` file,
clearly cross-referenced to the content-types and widget-reference resources.

---

## Appendix: key content-type facts (reference for skill authoring)

Drawn directly from `demo_content/`.

### File types

| File | content_type | Key frontmatter | Notes |
|---|---|---|---|
| `course.md` | `COURSE` | title, subtitle, description, uuid | One per course directory |
| `part.yaml` | `COURSE_PART` | title, uuid | One per part subdirectory; no `.md` |
| `NN. name.md` | `TOPIC` | title, subtitle, description, uuid | Numbered; body is markdown + widgets |
| `form.md` | `FORM` | title, strategy, uuid, quiz_pass_percentage, quiz_show_incorrect | strategy: QUIZ or CATEGORY_VALUE_SUM |
| `NN. name.yaml` | `FORM_PAGE` | title, subtitle, description, uuid | Numbered; body is YAML blocks of questions |

### UUID rules

- Every file/entity has a `uuid` field.
- UUIDs are generated once and never changed — they are the identity of the entity in the database.
- Authors must never copy or re-use a UUID from another file.
- Generate new UUIDs with a proper UUID4 generator (Python `uuid.uuid4()`, online tool, etc.).
- Form pages (page.yaml) include UUIDs on the page itself AND on every question and every option.

### Numbering conventions

- Topic files and form directories are numbered with a two-digit prefix: `01. topic-name.md`,
  `02. another-topic.md`, `03. knowledge-check/`.
- Course part directories are numbered: `01. Getting Started/`, `02. Core Concepts/`.
- The number controls display order; gaps are allowed but discouraged.
- `course.md` and `form.md` (and `part.yaml`) are unnumbered — one per directory, identified by name.

### HTML-escape rules in widget content

- `c-code-block` and `c-equation` bodies: must escape `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`,
  `"` → `&quot;`. The sanitiser processes the body as HTML before the widget renders it.
- All other widget bodies: standard markdown; escaping is handled automatically.

---

status: ok
