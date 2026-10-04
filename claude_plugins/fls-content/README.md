# fls-content

A Claude plugin for authoring FLS course content in a content repo.

## Commands

- `/fls-content:init` — scaffold `.fls-content.yaml` (the repo's admonition- and access-type
  config) at the repo root and install the validator's dependencies into a `.venv/` there. Run
  once when setting up a content repo.
- `/fls-content:format-content <path>` — reformat messy Markdown (and YAML role files) into
  valid, well-structured FLS content, in place. Run when importing or cleaning up content.
- `/fls-content:validate-content <path>` — check content structure and auto-fix obvious
  problems. Run before considering content done, or whenever you want to confirm it is valid.

A content repo can declare its project's custom widgets in `.claude/fls-content/widgets/`, one `c-<name>.md` per widget, and the plugin treats them like built-ins.
