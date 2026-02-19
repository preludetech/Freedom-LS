---
name: template
description: Create or edit Django templates with cotton components, template partials, and proper Tailwind usage. Use when creating/editing HTML templates, adding components, or when the user mentions templates, UI, or frontend work.
allowed-tools: Read, Grep, Glob
---

# When to Use This Skill

Use this Skill when:
- User asks to create a new template, page, or component
- User wants to edit existing templates
- User mentions "UI", "frontend", "template", "HTML"
- Adding new pages to an app
- Creating reusable components
- Working with HTMX or Alpine.js in templates

# Details

## Key Rules

- Pages: `freedom_ls/<app>/templates/<app>/<page>.html` — always extend `_base.html`
- Cotton components: `freedom_ls/<app>/templates/cotton/<name>.html` — use `<c-vars>` with defaults
- Partials: `freedom_ls/<app>/templates/<app>/partials/<name>.html`
- Use `{% partialdef %}` with kebab-case names for inline partials
- Don't hardcode URLs — use `{% url 'app:name' %}`
- Check existing cotton components before creating new ones
- Views returning partials use `partial_` prefix

Refer to @.claude/docs/templates_and_cotton.md for full patterns and examples.