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

- **Read the project's stylesheets before you style — always.** Open `./tailwind.input.css` and follow
  its project `@import`s (`@import "tailwindcss"` is the library — don't chase it). Those files hold
  everything you need: the `@theme {}` design tokens, the `@layer base` element styling, and the CSS
  component classes.
- **Style only with what you found.** The tokens and classes in those stylesheets are the only ones
  that exist — never assume a name from another codebase. Don't hard-code hex values or reach for raw
  palette utilities (`bg-blue-600`) where the project names a token for the job.
- **Every rule you add goes in a layer** — `@theme {}` for tokens, `@layer base {}` for element
  selectors, `@layer components {}` for reusable classes, `@utility` for a new utility. Never write an
  unlayered rule: unlayered CSS beats every layered rule in the cascade, so it silently overrides the
  utility classes in your markup.
- Reuse before you write: check the project's existing cotton components (`<c-*>`) and the component
  classes in its stylesheets before adding new styling.
- Use Tailwind utility classes exclusively — no custom CSS unless absolutely necessary
- Run `npm run tailwind_build` after adding new Tailwind classes that aren't already in use
- Use the project's spacing scale consistently
- Mobile-first responsive design: start with mobile, add `md:` and `lg:` breakpoints

For full details and examples, see `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.
