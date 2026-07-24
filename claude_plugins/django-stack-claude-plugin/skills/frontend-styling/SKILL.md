---
name: frontend-styling
description: Frontend styling with Tailwind including applying classes to templates and components, creating UI elements, reviewing markup, modifying component classes, and building Tailwind.
allowed-tools: Read, Grep, Glob
---

# Frontend Styling

## When to Use

Use this skill when:
- Applying Tailwind CSS classes to templates and components
- Creating new UI elements or layouts
- Reviewing or modifying markup and styling
- Building Tailwind CSS (`npm run tailwind_build`)

## Key Rules

- Use Tailwind utility classes exclusively — no custom CSS unless absolutely necessary
- Run `npm run tailwind_build` after adding new Tailwind classes that aren't already in use
- Use the project's color palette and spacing scale consistently
- Mobile-first responsive design: start with mobile, add `md:` and `lg:` breakpoints

For full details and examples, see `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.
