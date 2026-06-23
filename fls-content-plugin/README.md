# fls-content

A Claude plugin for authoring FLS course content in a content repo.

## Commands

- `/fls-content:init` — scaffold `.fls-content.yaml` (the repo's admonition-type config) and
  install the validator's dependencies. Run once when setting up a content repo.
- `/fls-content:format-content <path>` — reformat messy Markdown (and YAML role files) into
  valid, well-structured FLS content, in place. Run when importing or cleaning up content.
- `/fls-content:validate-content <path>` — check content structure and auto-fix obvious
  problems. Run before considering content done, or whenever you want to confirm it is valid.
