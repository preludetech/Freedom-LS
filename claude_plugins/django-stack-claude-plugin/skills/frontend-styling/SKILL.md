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

- **Read the theme before you style.** Open the project's Tailwind entry stylesheet (commonly
  `tailwind.input.css`), follow its `@import`s, and read the `@theme {}` blocks. Those declarations are
  the only design tokens that exist in this project — never assume a token name from another codebase.
  Style with the tokens you actually found; don't hard-code hex values or reach for raw palette
  utilities (`bg-blue-600`) where the theme names a token for the job.
- Use Tailwind utility classes exclusively — no custom CSS unless absolutely necessary
- Run `npm run tailwind_build` after adding new Tailwind classes that aren't already in use
- Use the project's spacing scale consistently
- Mobile-first responsive design: start with mobile, add `md:` and `lg:` breakpoints
- Reuse before you write: check the project's existing cotton components (`<c-*>`) and, **if the
  project has one**, its `tailwind.components.css` component classes, before adding new styling.

For full details and examples, see `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.
