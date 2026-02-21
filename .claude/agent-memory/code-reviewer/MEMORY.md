# FreedomLS Educator Interface - Code Review Memory

## Project Context
- Multi-site Django LMS with custom site-aware user model
- Uses brand theme color variables: text-foreground, text-muted, bg-surface, bg-surface-2, border-border, text-primary, text-primary-bold, text-success, text-success-bold, text-danger, text-warning
- HTMX integration with global CSRF headers via `<body hx-headers=...>`
- Component classes defined in tailwind.components.css (btn, chip, surface, etc.)
- Modern Python 3.13+ with type hints required on all functions (no Any type)

## Key Files
- tailwind.components.css: Theme colors and component definitions
- .claude/skills/brand-guidelines/SKILL.md: Brand color palette and UI patterns
- .claude/docs/frontend_styling.md: TailwindCSS conventions and component usage
- CLAUDE.md: Project conventions

## Cohort Course Progress Panel Implementation
- **Status**: Tasks 4-5 in progress (template styling)
- **Template**: freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html
- **Key Features**:
  - Course selection dropdown with HTMX
  - Frozen header row (sticky top/left positioning)
  - Progress grid with student rows and course item columns
  - Pagination for both students and columns
  - Deadline visualization with hard/soft distinction
  - Student override display with clock icon
  - Color-coded cells: success for completed, primary-bold for started, border/muted for not started
  - Quiz-specific display: percentage + pass/fail + attempt count

## Color/Brand Usage Rules
- Brand theme colors available: primary, primary-bold, success, success-bold, danger, danger-bold, warning, foreground, muted, surface, surface-2, border
- Never use raw hex colors when theme classes exist
- Chip classes available: chip-primary, chip-success, chip-danger, chip-warning, chip-xs
- Button classes: btn, btn-outline, btn-primary
- Proper z-index layering for frozen headers/columns (z-30 for corner, z-20 for headers/cols, z-10 for body freeze col)

## Template Patterns in This Project
- Use theme variables for colors (not raw Tailwind utilities)
- Empty states with text-muted color
- Deadline styling: danger/10 or warning/20 backgrounds with left border
- Overdue cells: danger/15 for hard deadlines, warning/15 for soft overdue
- Icons: Unicode characters (✓ for complete, ▶ for started, – for not started, ⏱ for clock)
