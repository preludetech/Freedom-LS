Update the student dashboard so it looks and feels good. We will be making use of some designs made by claude design.

Changes needed:

- Heading area:
    - Left align "Welcome back, First name"
    - Add a small Date just above the welcome back heading

In-progress, history, etc sections:
- remove the borders around the sections
- section headings must be smaller and left-aligned

Available courses section:
- make this visible, but show max 3 courses
- Add a right-aligned "Browse all courses" button next to the "Available courses" heading
- Remove the "all courses" button at the bottom of the screen


# Source material

Visual designs (external React prototype): `@ $HOME/workspace/lms/design/Learner Experience v3.html` Look only at the "dashboard"

The designs come from an external tool that is **not** aware of our codebase. They
assume functionality and intentions that don't always fit our stack. **Don't scope
creep.** Where a design implies heavy infrastructure, ask for scoping decisions.

Do not add any weird placeholder content or faked functionality. We are simply making our current implementation look more in line with the given design.

## Theming

The prototype was drawn to match the **first_class** theme. Implement each widget
in the **default** theme using standard role tokens (`--color-primary`,
`text-on-surface`, `bg-surface`, status tokens, `--fls-radius-*`, etc.), then
override in the **first_class** theme only where the brand look needs it. The
brand colours/shapes in the prototype already flow from the first_class theme
tokens — widgets should not hardcode hex values.
