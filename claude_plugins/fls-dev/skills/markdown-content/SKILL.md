---
name: markdown-content
description: MarkdownContent models (Topic, Activity, Course, Form, FormContent) and cotton components inside markdown. Use when working with content models, rendering markdown (rendered_content(), {% markdown %}), adding a markdown component or editing MARKDOWN_ALLOWED_TAGS, or debugging content rendering or sanitization.
allowed-tools: Read, Grep, Glob
---

# Markdown Content System

## Key Rules

- Content models (Topic, Activity, Course, Form, FormContent) extend `MarkdownContent`.
- Render with `instance.rendered_content()`. Pipeline: markdown -> sanitize (nh3) -> cotton components -> safe HTML.
- Cotton components in markdown live in `freedom_ls/content_engine/templates/cotton/`.
- Register new components in `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py`.
- H1 in content becomes H2 (mdx_headdown).

Full details and examples: `${CLAUDE_PLUGIN_ROOT}/resources/markdown_content.md`.
