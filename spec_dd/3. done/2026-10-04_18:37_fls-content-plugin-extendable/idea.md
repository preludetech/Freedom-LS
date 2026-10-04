# Custom widgets in the fls-content plugin

## What and why

The `fls-content` plugin gets copied into content repos. Content from those repos is imported into
concrete projects. A concrete project can already add its own widgets: it writes a cotton component
and adds it to `MARKDOWN_ALLOWED_TAGS` (`docs/how tos/custom-content-widgets.md`). The plugin only
knows FLS's built-in widgets. It tells authors the allowlist is closed, and `format-content` flags
any other `c-*` tag and strips attributes it doesn't recognise. In a content repo for a concrete
project with custom widgets, the plugin works against the author.

The goal is to let a content repo declare the concrete project's custom widgets, so that everything
the plugin already does with widgets also works with those custom widgets.

## Settled

- **Custom widgets are only ever added.** Built-in widgets, their reference files and their
  behaviour stay exactly as they are. There is no mechanism to remove, rename or restyle a built-in.
  A custom widget's name must not be the name of a built-in.
- **The plugin defines a convention and reads it.** It does not care where the declarations come
  from. The concrete project generates them for its content repo, following the convention set
  here. How it generates them is out of scope.
- **The declarations live in the content repo, outside the plugin.** The plugin's files get
  overwritten whenever it is re-copied or re-synced from FLS
  (`/fls-dev:update_claude_plugin_fls_content`). This follows the existing `.fls-content.yaml`
  pattern, where a consumer-owned file at the content repo root is read at runtime.
- **One reference file per custom widget**, in the same shape as the plugin's own
  `skills/widget-reference/resources/c-*.md`: purpose, allowed attributes, attribute table and a
  copy-pasteable example. The allowed attributes listed in a widget's file are that widget's
  complete attribute set. The files go in `.claude/fls-content/widgets/c-<name>.md` at the content repo
  root, following the `.claude/<plugin>/` convention for plugin configuration.
- **No declarations means no custom widgets.** When `.claude/fls-content/widgets/` is missing, the plugin
  behaves as it does today, so existing content repos need nothing new.
- **Only existing functionality changes, and none is added.**
  - The `widget-reference` skill must tell the agent to read the repo's custom widget files and to
    treat those widgets as valid alongside the built-ins.
  - `format-content` and its `content-formatter` agent must accept declared custom widgets and
    their attributes. Today `conversion-patterns.md` removes unlisted attributes and flags unknown
    `c-*` names. Built-in widgets keep that behaviour, and so do tags that aren't declared.
  - The validator never inspects widgets, so it stays as it is. `/fls-content:init` doesn't touch
    widgets and stays as it is.
- **Docs that say the plugin can't do this get corrected.** These are the "Telling your authors"
  section of `docs/how tos/custom-content-widgets.md`, the plugin `README.md`, and the plugin
  description in `docs/product/content-editing-workflow.md`.

## Open for the spec

- Confirm that `content_save` and the validator skip `.claude/fls-content/`. Dot-prefixed files are not
  scanned as content (`skills/content-types/resources/file-layout.md`), but no one has checked that
  this holds for dot-prefixed directories too.

## Research

- `research_plugin_widget_touchpoints.md`: every place in the plugin that assumes the widget list is
  closed, plus the `.fls-content.yaml` precedent.
- `research_claude_code_plugin_extension.md`: why a consumer-owned directory, which the plugin skill
  explicitly tells the agent to read, beats a project skill, a fork or `userConfig`.
- `research_custom_component_declaration.md`: how Markdoc, MDX, Hugo and others declare custom
  components for tooling. Background only.
