# Contextual help in the educator interface

## What

A help icon beside a panel heading, a field or a button. Clicking, tapping or focusing it and pressing Enter opens a short explanation of what that part of the page does or what the button will do. The panel framework gets a help component for this, and the educator interface panels get help text where an educator needs it.

## Why

Educators meet actions with side effects (bulk deactivation, registering a cohort, staff roles) and panels whose purpose is not obvious from the heading. Today there is nowhere to explain them short of the documentation.

## What is settled

- The help opens on click, tap and keyboard, not on hover alone. Hover tooltips fail on touch screens and for keyboard users. The icon is a real `<button>` with an accessible name; Esc closes the help and focus returns to the icon (WCAG 1.4.13).
- Help never holds the only copy of something the educator must know before acting. A consequence of an action stays in the action's confirm dialog or as hint text under the field.
- Tooltips remain only as labels for icon-only buttons.
- The component is panel framework work. It lands after `extract_panels_framework-5-package-and-install`, in the `django-panel-framework` package. The help text belongs to FLS panels and actions.

## Open until the spec

- How a panel, field, action or column declares its help text.
- Which panels and actions get help in the first pass.
- The look and placement of the icon and its popover. This needs a design.

## Out of scope

- A help centre, guided tours or links into documentation.
- Help in the learner interface.

## Resources

- `spec_dd/1. next/educator-interface-page-polish/research_comparable_systems.md` section 2.
- `fls-dev:panel-framework`, `fls-dev:icon-usage` and `brand-guidelines` skills.
- Designs needed: the help icon and its open state, wide and phone.
