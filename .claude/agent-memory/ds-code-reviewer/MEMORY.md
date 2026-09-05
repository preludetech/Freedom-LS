# FreedomLS Code Review Memory

## Project Context
- Multi-site Django LMS with custom site-aware user model
- Role colour tokens (the full list): primary, secondary, accent, success, warning, error, info — each with an `on-*` partner; the `-light` status tints and their `on-*-light` partners; success-soft; surface, surface-2, on-surface, border, muted, focus-ring. Utilities follow the token name (`text-on-surface`, `bg-surface-2`, `border-border`).
- There is NO `foreground`, no `danger`, and no `*-bold` series. `text-foreground`, `text-danger` and `text-primary-bold` resolve to nothing. Body text is `text-on-surface`; the destructive role is `error`.
- HTMX integration with global CSRF headers via `<body hx-headers=...>`
- `tailwind.components.css` holds the `@layer base` element rules, the component classes a theme reopens (btn, chip, alert, surface, signup-panel, header, course-card, course-accent-*, course-progress-*, modal-backdrop*), and the `.task-list*` classes the markdown renderer emits. A component's own styling lives in its template instead — utilities on the markup, or a `<style>` block wrapped in `@layer components`.
- Modern Python 3.13+ with type hints required on all functions (no Any type)

## Key Files
- freedom_ls/themes/default/static/themes/default/theme.css: every colour, shape and type token. Themes are sparse, so this file is the full contract; freedom_ls/themes/first_class/... shows only the deltas.
- tailwind.components.css: element base rules + the themable component classes (no tokens, no per-component styling)
- claude_plugins/fls-dev/resources/frontend_styling.md: the FLS token contract and the stylesheet-vs-template rule
- claude_plugins/django-stack/resources/frontend_styling.md: the generic layer and placement rules
- .claude/skills/brand-guidelines/SKILL.md: brand identity and voice (design intent — read the theme for what is actually configured)
- CLAUDE.md: Project conventions

## Cohort Course Progress Panel Implementation
- **Status**: Tasks 4-5 in progress (template styling)
- **Template**: freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html
- **Key Features**:
  - Course selection dropdown with HTMX
  - Frozen header row (sticky top/left positioning)
  - Progress grid with learner rows and course item columns
  - Pagination for both learners and columns
  - Deadline visualization with hard/soft distinction
  - Learner override display with clock icon
  - Color-coded cells: success for completed, primary for started, border/muted for not started
  - Quiz-specific display: percentage + pass/fail + attempt count

## Color/Brand Usage Rules
- Never use raw hex colours, and never reach for a raw palette utility (`bg-blue-600`, `text-slate-400`) where a role token names the same job
- Respect the declared foreground/background pairings — `text-on-primary` on `bg-primary`, `text-on-error-light` on `bg-error-light`. They carry the contrast guarantees
- Hover variants exist for the seven coloured roles only (`hover:bg-primary-hover`). surface, surface-2, on-surface, border, muted and focus-ring have none — do not invent one
- Chip classes: chip-primary, chip-secondary, chip-success, chip-warning, chip-error, chip-info, chip-muted, chip-xs. There is no chip-danger
- Button classes: btn, btn-primary, btn-secondary, btn-ghost, btn-link, btn-accent, btn-success, btn-error, btn-sm. There is no btn-outline
- Proper z-index layering for frozen headers/columns (z-30 for corner, z-20 for headers/cols, z-10 for body freeze col)

## Template Patterns in This Project
- Use theme variables for colors (not raw Tailwind utilities)
- Empty states with text-muted color
- Deadline styling: error/10 or warning/20 backgrounds with left border
- Overdue cells: error/15 for hard deadlines, warning/15 for soft overdue
- Icons: Use `<c-icon name="semantic_name" />` cotton component (registry: `freedom_ls/icons/semantic_names.py` for allowed names + `freedom_ls/icons/mappings.py` for heroicon mapping; note: NOT `freedom_ls/base/icons.py`)
- Icon internals: `icon_name` filter in `icon_tags.py` + `{% heroicon_* %}` tags in `cotton/icon.html`
- All icons are informative by default (role="img", aria-label set to semantic name)
- IMPORTANT: `aria_label=""` does NOT make an icon decorative — backend falls back to the semantic slug. See icon_aria_gotcha.md. Wrap in `aria-hidden="true"` span for decorative.
- Alpine.js icon toggling: `x-show` on wrapper spans or `rotate-180` for directional flips
- Icon sizing: size-3 (badges), size-4 (compact), size-5 (standard), size-6 (emphasis), size-8 (large), size-16 (hero)

## Learner Model Refactoring (Completed)
- The old per-learner registration model was removed; all FKs now point to User directly
- That earlier refactor renamed the per-learner registration and per-learner deadline-override models to UserCourseRegistration and UserCohortDeadlineOverride respectively
- LearnerDeadline (a separate model) and its FK field learner_course_registration were later renamed in the site-wide terminology rename — this corrects an earlier note in this file claiming neither was renamed
- Migrations 0006-0012 handle the full refactoring chain
- related_name on UserCourseRegistration.collection is "user_registrations"
- CohortMembership has no unique constraint on (user, cohort)

## Role-Based Permissions System
- App: `freedom_ls/role_based_permissions/`
- Three assignment models: SystemRoleAssignment (plain Model), SiteRoleAssignment (SiteAwareModel), ObjectRoleAssignment (SiteAwareModel)
- Role dataclass has `assignment_scope` field (system/site/object) but it's NOT enforced in utils.py assignment functions
- Spec uses `ui_hint` but implementation renamed to `role_type` (same values: standalone/composable)
- `get_course_roles`/`get_cohort_roles` convenience wrappers from plan not implemented
- `removed_by` parameter from plan not implemented on remove functions
- Config loading: `FREEDOMLS_PERMISSIONS_MODULES` maps site names to module paths
- DemoDev site config at `config/role_based_permissions/demodev.py`
- Management commands use djclick
- `_report_orphans` in sync command uses single config, may produce false positives in multi-site setups

## Factory Boy Implementation
- SiteAwareFactory base in `freedom_ls/site_aware_models/factories.py`
- One `factories.py` per app, uses SiteAwareFactory base
- GenericFK pattern: `Meta.exclude` + `Params` with convenience param, `LazyAttribute` to derive content_type/object_id
- ContentCollectionItem has dual GenericFK (collection_object, child_object)
- `add_item_to_collection()` helper in conftest wraps ContentCollectionItemFactory
- QA commands pass `site=` explicitly since mock_site_context isn't active outside tests
- Deadline factories use `content_item` param (excluded) to set nullable GenericFK fields
- `course.items.create(child=...)` pattern still used in some test files (GenericRelation manager)

## Topic Files
- [project_panel_framework.md](project_panel_framework.md) — Panel framework architecture: views.py dispatch, OOB patterns, Alpine components
- [project_admonition_widgets.md](project_admonition_widgets.md) — Admonition/flashcard/accordion widgets: ADMONITION_TYPES registry, icon resolution, callout migration
- [project_markdown_widget_pipeline.md](project_markdown_widget_pipeline.md) — render_markdown order, why cotton output is trusted, the `{% markdown slot %}` re-sanitise gotcha
- [project_fls_content_plugin.md](project_fls_content_plugin.md) — Bundled Django-free validator; ruff/mypy/`uv --no-project` gotchas for `claude_plugins/fls-content/`
- [icon_aria_gotcha.md](icon_aria_gotcha.md) — Why `aria_label=""` does not make an icon decorative
