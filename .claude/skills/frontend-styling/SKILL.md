---
name: frontend-styling
description: Apply TailwindCSS v4 styling, use component classes, and follow styling conventions. Use when styling components, working with Tailwind, or when the user mentions CSS or styling.
allowed-tools: Read, Grep, Glob
---

# Frontend Styling

This Skill helps apply proper TailwindCSS styling following project conventions.

## When to Use This Skill

Use this Skill when:
- **Styling templates or components** - Need to apply Tailwind classes
- **Creating new UI elements** - Buttons, cards, forms, etc.
- **User mentions "CSS", "Tailwind", "styling", "classes"**
- **Reviewing markup** - Checking for proper class usage
- **Adding component classes** - Need to modify `tailwind.components.css`
- **Building Tailwind** - Running build/watch commands

## Key Rules

- Always check `tailwind.components.css` first — use component classes (`.btn`, `.btn-primary`, `.surface`) when available
- Don't duplicate base styles — `h1-h4`, `a`, lists, and form elements are pre-styled in `@layer base`
- Only use inline Tailwind classes for unique layout/spacing/positioning
- Repeated patterns should be added to `tailwind.components.css`
- Run `npm run tailwind_build` after CSS changes

Refer to @.claude/docs/frontend_styling.md for full details and examples.
