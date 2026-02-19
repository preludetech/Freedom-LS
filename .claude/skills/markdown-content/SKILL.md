---
name: markdown-content
description: Work with markdown content system, MarkdownContent models, and cotton components in markdown. Use when working with content models or adding markdown components.
allowed-tools: Read, Grep, Glob
---

# Markdown Content System

This Skill helps work with markdown content rendering and cotton components in content.

## When to Use This Skill

Use this Skill when:
- **Working with content models** - Topic, Activity, Course, Form, FormContent
- **Rendering markdown** - Using rendered_content() or {% markdown %}
- **Adding markdown components** - Creating cotton components for content
- **User mentions "markdown", "content", "rendered_content"**
- **Debugging content rendering** - Issues with markdown or sanitization
- **Modifying MARKDOWN_ALLOWED_TAGS** - Adding new component support

## Key Rules

- Content models (Topic, Activity, Course, Form, FormContent) extend `MarkdownContent`
- Render with `instance.rendered_content()` — pipeline: markdown -> sanitize (nh3) -> cotton components -> safe HTML
- Cotton components in markdown live in `freedom_ls/content_engine/templates/cotton/`
- New components must be registered in `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py`
- H1 in content becomes H2 (mdx_headdown)

Refer to @.claude/docs/markdown_content.md for full details and examples.
