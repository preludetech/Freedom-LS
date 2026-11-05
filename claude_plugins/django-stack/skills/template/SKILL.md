---
name: template
description: Create or edit Django templates with cotton components, template partials, and proper Tailwind usage. Use when creating/editing HTML templates, adding components, or when the user mentions templates, UI, or frontend work.
allowed-tools: Read, Grep, Glob
---

# When to Use This Skill

- User asks to create a new template, page, or component
- User wants to edit existing templates
- User mentions "UI", "frontend", "template", "HTML"
- Adding new pages to an app
- Creating reusable components
- Working with HTMX or Alpine.js in templates

# Details

## Key Rules

- Pages: `<app>/templates/<app>/<page>.html`, always extending `_base.html`
- Cotton components: project-level `templates/cotton/<name>.html` for shared/design-system components,
  or `<app>/templates/cotton/<name>.html` for app-specific ones; use `<c-vars>` with defaults
- Partials: `<app>/templates/<app>/partials/<name>.html`
- Use `{% partialdef %}` with kebab-case names for inline partials
- Don't hardcode URLs; use `{% url 'app:name' %}`
- Check existing cotton components before creating new ones
- Views returning partials use `partial_` prefix
- Use Django-style comments `{% comment %}...{% endcomment %}`, never Jinja-style `{# ... #}`
- Copy: a list page starts at its heading and toolbar, a confirm dialog states the current state
  and the change, a disabled action shows its reason ("Copy a template carries" in
  `${CLAUDE_PLUGIN_ROOT}/resources/templates_and_cotton.md`)

Refer to `${CLAUDE_PLUGIN_ROOT}/resources/templates_and_cotton.md` for full patterns and examples.
