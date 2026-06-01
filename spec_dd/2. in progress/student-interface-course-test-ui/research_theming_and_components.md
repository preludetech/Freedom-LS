# Research: Theming and Component Mapping for the Exam/Test UI

This document maps the third-party design (at `/home/sheena/workspace/lms/design/computed/exam/`) onto the FLS token system, cotton components, and base template structure. It feeds the implementation spec.

---

## 1. Token Mapping Table

The design declares all variables in a `:root {}` block inside each HTML file (identical across all screen-size files, lines 19-42 of e.g. `desktop/start_page.html`). The table below maps each design variable to the FLS `@theme` token that should replace it.

### Brand colours

| Design variable | Design hex | FLS `@theme` token | Notes |
|---|---|---|---|
| `--color-primary` | `#283593` (deep indigo) | `--color-primary` | First-class theme already sets this exact hex (`first_class/theme.css:17`) |
| `--color-primary-900` | `#1f2a73` | `color-mix(in oklch, var(--color-primary), black 12%)` or use `--color-primary-hover` | FLS auto-derives hover via `color-mix`; the design uses 900 as hover (`theme.css:66`). Use Tailwind utility `hover:bg-primary-hover` in templates. |
| `--color-secondary` | `#00CEC9` (teal) | `--color-secondary` | FC theme sets this exact hex (`first_class/theme.css:19`) |
| `--color-secondary-600` | `#00A8A4` (darker teal) | No direct token — use `color-mix(in oklch, var(--color-secondary), black 12%)` inline, OR add `--color-secondary-hover` via the existing hover-mix pattern | The hover pattern in `default/theme.css:67` already generates `--color-secondary-hover` using `color-mix`. Use Tailwind `text-secondary/80` or `text-secondary` on elements needing the muted teal. |
| `--color-accent` | `#FF6B35` (orange) | `--color-accent` | FC theme sets this exact hex (`first_class/theme.css:21`) |
| `--color-accent-600` | `#E55A28` | Use `--color-accent-hover` (auto-derived, `default/theme.css:68`) | No raw hex needed in templates |

### Status colours

| Design variable | Design hex | FLS `@theme` token |
|---|---|---|
| `--color-success` | `#38A169` | `--color-success` (both themes match, `first_class/theme.css:25`) |
| `--color-success-light` | `#F0FFF4` | `--color-success-light` (`first_class/theme.css:37`) |
| `--color-warning` | `#D69E2E` | `--color-warning` (`first_class/theme.css:27`) |
| `--color-warning-light` | `#FFFFF0` | `--color-warning-light` (`first_class/theme.css:38`) |
| `--color-error` | `#E53E3E` | `--color-error` (`first_class/theme.css:29`) |
| `--color-error-light` | `#FFF5F5` | `--color-error-light` (`first_class/theme.css:39`) |
| `--color-info` | `#3182CE` | `--color-info` (`first_class/theme.css:31`) |
| `--color-info-light` | `#EBF8FF` | `--color-info-light` (`first_class/theme.css:40`) |

### Surface / foreground / border

The design uses a two-tier surface system (`--bg` = page canvas, `--bg-elev` = elevated card/panel) and four foreground steps (`--fg`, `--fg-1..4`).

| Design variable | Design semantics | FLS `@theme` token | Notes |
|---|---|---|---|
| `--bg` → `var(--color-surface)` = `#F8F9FC` | Page canvas | `--color-surface` | FC theme matches exactly (`first_class/theme.css:48`) |
| `--bg-elev` = `#FFFFFF` | Elevated panel / card | `--color-surface` in default; use `bg-white` utility when you need the literal white elevation | No dedicated `surface-elev` token exists — if the two-level surface distinction is important, consider adding `--color-surface-elev: #FFFFFF` to the first-class theme. For now, `bg-white` on card panels works for the first-class theme. |
| `--bg-subtle` → `var(--grey-100)` | Background tint | `--color-surface-2` (`first_class/theme.css:49` = `#EDF2F7`) |  |
| `--fg` → `var(--color-text)` = `#1A1A2E` | Body foreground | `--color-on-surface` (`first_class/theme.css:50` = `#1A1A2E`) |  |
| `--fg-1` = `--grey-800` = `#1A202C` | Strong foreground | `--color-on-surface` (close enough; both are near-black) |  |
| `--fg-2` = `--grey-600` = `#4A5568` | Subdued text | `--color-muted` (`first_class/theme.css:51` = `#718096`). Note slight difference. For strong subdued use `text-on-surface/80`. |  |
| `--fg-3` = `--grey-500` = `#718096` | Placeholder / label | `--color-muted` (FC = `#718096`, exact match) | Use `text-muted` |
| `--fg-4` = `--grey-400` = `#A0AEC0` | Disabled / very muted | `text-muted/60` Tailwind opacity modifier or `text-border` | No exact token; use `text-muted/60` |
| `--border` = `--grey-200` = `#E2E8F0` | Default border | `--color-border` (`first_class/theme.css:52` = `#E2E8F0`, exact match) |  |
| `--border-strong` = `--grey-300` = `#CBD5E0` | Strong border | `--color-border/70` opacity modifier | No separate strong-border token; use Tailwind modifier |

### Grey scale (used for backgrounds and inline tints)

| Design variable | Hex | FLS equivalent |
|---|---|---|
| `--grey-50` | `#F8F9FC` | `--color-surface` |
| `--grey-100` | `#EDF2F7` | `--color-surface-2` |
| `--grey-200` | `#E2E8F0` | `--color-border` |
| `--grey-300` | `#CBD5E0` | `--color-border/70` |
| `--grey-400..900` | Various | Use Tailwind opacity modifiers on `--color-muted` or `--color-on-surface` for matching shades. No named tokens exist for these steps. |

### Typography

| Design variable | Value | FLS `@theme` token | Notes |
|---|---|---|---|
| `--font-heading` | `"Outfit"` | `--font-display` → `--fls-font-display: "Outfit"` (FC theme, `first_class/theme.css:76`) | Use Tailwind class `font-display` |
| `--font-body` | `"DM Sans"` | `--font-sans` → `--fls-font-sans: "DM Sans"` (FC theme, `first_class/theme.css:75`) | Use `font-sans` (body default) |
| `--font-mono` | `"IBM Plex Mono"` | `--font-mono` → `--fls-font-mono: "IBM Plex Mono"` (FC theme, `first_class/theme.css:77`) | Use `font-mono` |

Note: in the default theme, `--fls-font-sans` falls back to system-ui (`default/theme.css:111`), `--fls-font-display` aliases `--fls-font-sans` (`default/theme.css:113`), and `--fls-font-mono` is system monospace (`default/theme.css:114`). The exam UI will therefore use system fonts under the default theme and Outfit/DM Sans/IBM Plex Mono under first_class — which is the desired fallback-first behaviour.

The Google Fonts `<link>` tags in the design files (`start_page.html:9`) are NOT needed in FLS templates — the first_class theme's static bundle (or a project-level `<link>`) is expected to load those fonts. The exam templates should not include their own font CDN links.

### Radii

| Design usage | Radius | FLS token | Tailwind class |
|---|---|---|---|
| Buttons, inputs | `8px` | `--fls-radius-md: 0.5rem` (FC = 8px, `first_class/theme.css:68`) | `rounded-md` |
| Cards, modals | `12–16px` | `--fls-radius-lg: 0.75rem` (FC = 12px, `first_class/theme.css:69`) | `rounded-lg` |
| Chips / pills | `999px` | `--fls-radius-pill: 9999px` (`default/theme.css:108`) | `rounded-pill` |
| Progress track | `999px` | same | `rounded-pill` |
| Meta-grid (start screen) | `14px` | close to `rounded-lg`; Tailwind `rounded-xl` (12px) or `rounded-2xl` (16px) if exact match needed | For default theme, `rounded-lg` suffices |

### Shadows

The design defines `--shadow-sm`, `--shadow`, `--shadow-md`, `--shadow-lg` (design file line 37-40). FLS does not define named shadow tokens in `@theme`; use Tailwind's built-in shadow utilities:

| Design variable | FLS/Tailwind equivalent |
|---|---|
| `--shadow-sm` | `shadow-sm` |
| `--shadow` | `shadow` |
| `--shadow-md` | `shadow-md` |
| `--shadow-lg` | `shadow-lg` |

---

## 2. Component Reuse Map

### Existing cotton components (all in `freedom_ls/base/templates/cotton/` or `freedom_ls/student_interface/templates/cotton/`)

| Design UI block | Cotton component to reuse | Notes / current usage in form templates |
|---|---|---|
| **Top bar / site header** (`.fc-topbar`) | Existing `.header` + `partials/header_bar.html` via `_base.html:57` | The standard FLS header already renders on start and results screens. No change needed — just extend `_base.html` as normal. |
| **Breadcrumb** (`.fc-crumb`) | Inline markup using `text-primary`, `text-muted` | No dedicated cotton component. A short inline snippet is fine. |
| **Primary button** (`.fc-btn-primary`, `.fc-exam-start`) | `c-button` with `variant="primary"` | Already used in `course_form.html:85` and `course_form_complete.html:185` |
| **Ghost / secondary button** (`.fc-btn-ghost`) | `c-button` with `variant="ghost"` | Component exists (`tailwind.components.css:176`) |
| **Small button** (`.fc-btn-sm`) | `c-button` with `class="text-sm py-1.5 px-3"` | No separate sm variant; pass extra class |
| **Button group (footer nav)** | `c-button-group` with `variant="space-between"` | Already used in `course_form.html:77`, `course_form_page.html:165` |
| **Icon** | `c-icon` with semantic name | Used throughout existing form templates |
| **Chip / reassurance chip** (`.ck-reassure .chip`) | `c-chip` with `variant="success"` or `variant="secondary"` | `tailwind.components.css:196`. For calm/teal chips: `variant="secondary"` maps to `bg-secondary/15 text-secondary`. |
| **Surface card / question card** (`.fc-choice`, `.fc-question`) | `.surface` CSS class (defined `tailwind.components.css:191`) + inline Tailwind | The `.surface` class gives border + rounded-md + padding. Already used in `course_form_page.html:63` (`<div class="surface">`) |
| **Page wrapper** | `c-page` with `flush="true"` | Used in `course_form.html:4`, `course_form_page.html:100` |
| **Page-dots navigation** (`.fc-page-dot`) | `c-form-page-link` OR new inline partial | `c-form-page-link` exists (`cotton/form-page-link.html`) but uses numbered links, not dot shapes. The runner's dot-strip is decorative/positional, not a numbered list. Recommend a new inline partial `exam_page_dots` inside the runner template rather than the existing component. |
| **Modal / submit dialog** | `c-modal` | `freedom_ls/base/templates/cotton/modal.html` — Alpine-driven, has title/footer slots, uses `bg-surface`, `border-border`. Already close to design's `.fc-modal`. |
| **Markdown content block** | `c-markdown-container` | Used in `course_form_page.html:94` |
| **Loading indicator** | `c-loading-indicator` | Exists at `freedom_ls/base/templates/cotton/loading-indicator.html` |

### New components / partials needed

| Design UI block | Recommendation | Suggested name |
|---|---|---|
| **Start-screen meta grid** (`.fc-exam-meta-grid` — 4-cell stat row with icon + number + label) | New inline partial or cotton component; reuses `bg-surface`, `border-border`, `rounded-lg`, `text-primary` for icon colour | `cotton/exam-meta-grid.html` or inline `{% partialdef exam_meta_grid %}` inside start template |
| **Reassurance chip row** (`.ck-reassure`) | Compose from existing `c-chip` components; wrapper is just `flex flex-wrap gap-2` | Inline in start template; no separate component needed |
| **Previous attempts list** (`.ck-prev`, `.ck-prev-row`) | New inline partial or small cotton component | `partials/exam_previous_attempts.html` |
| **Runner top bar** (`.fc-runner-bar`) — 3-column grid with exit / title / timer | New component unique to the exam runner | `cotton/exam-runner-bar.html` (has distinct layout from `.header`) |
| **Progress bar** (`.fc-runner-progress`) | Thin inline markup: `<div class="bg-surface border-b border-border px-6 py-2.5">` track + fill div | No separate component needed; use Tailwind inline with `bg-border` track and `bg-secondary` fill |
| **Question card** (`.fc-question`) | Extend existing `.surface` pattern: wraps question text + choices. Recommend an inline `{% partialdef exam_question %}` in the runner template, similar to existing `{% partialdef form-question %}` in `course_form_page.html:62` | Keep as inline partial |
| **Choice row** (`.fc-choice`) | New inline partial within the question partial; Alpine-driven selected state | Inline; no separate cotton component |
| **True/False row** (`.fc-tf`, `.fc-tf-opt`) | New inline partial within the question partial | Inline |
| **Results score ring** (SVG circle) | New partial; pure SVG with inline `stroke-dasharray` driven by percentage variable | `partials/exam_score_ring.html` — the SVG is computed from score percentage (see design `desktop/results_pass.html` SVG block) |
| **Results stat grid** (`.fc-result-stats`) | New inline partial; same structural pattern as meta-grid | `partials/exam_results_stats.html` or inline |
| **Results banner** (`.fc-result-banner`) | New template section in the results page; reuses `bg-white rounded-lg border border-border shadow-sm` with the pass/fail left-edge accent strip | Inline in results template |
| **Answer review accordion** (`.fc-review`) | New component; Alpine-driven collapse. Could reuse `c-modal` patterns but the accordion structure is distinct | `cotton/exam-review-item.html` |
| **History / attempts list** (`.ck-attempt`) | New template; `ck-attempt` rows with `bg-surface border border-border rounded-lg` | New view + template; structure similar to `.ck-prev-row` |

---

## 3. Icon Strategy

**FLS uses Heroicons by default** (set in `config/settings_base.py:60`: `FREEDOM_LS_ICON_SET = "heroicons"`). The FLS icon system renders icons as inline SVG from Iconify JSON data — there are no `<i>` tags, no font CSS files.

The design uses Phosphor icons via CSS font (`ph ph-*` classes, loaded from `unpkg.com/@phosphor-icons/web@2.1.1`). FLS has no font-icon rendering path at all — it would be wrong to add Phosphor's CSS font to FLS templates.

**Mapping approach:**

1. Use `c-icon` with FLS semantic names for all icons in the exam UI, exactly as the existing form templates do.
2. FLS already has a `PHOSPHOR_MAPPING` defined in `freedom_ls/icons/mappings.py:142` covering all the semantic names used in the design (next, previous, check, close, warning, star, etc.) — this mapping is available if someone sets `FREEDOM_LS_ICON_SET = "phosphor"` in settings.
3. For icons the design uses that have no existing FLS semantic name, the approach is:
   - Check if the icon conveys a reusable semantic meaning. If yes, add a new entry to `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py` and add corresponding entries to all four icon mappings in `mappings.py`.
   - If the usage is purely decorative/exam-specific (e.g. a "flag for review" bookmark icon), consider rendering the SVG inline directly rather than adding a semantic name.

**Specific design icons and their FLS mappings (under heroicons):**

| Design `ph` icon | Semantic name | Heroicons rendering |
|---|---|---|
| `ph-arrow-left` | `previous` | `arrow-left` |
| `ph-arrow-right` | `next` | `arrow-right` |
| `ph-check-circle` | `success` | `check-circle` |
| `ph-x-circle` | `error` | `x-circle` |
| `ph-warning` | `warning` | `exclamation-triangle` |
| `ph-clock` | `deadline` | `clock` |
| `ph-flag` | No existing semantic name — add `flag` | Heroicons: `flag` |
| `ph-check` | `check` | `check` |
| `ph-x` | `close` | `x-mark` |
| `ph-repeat` | `retry` | `arrow-path` |
| `ph-caret-down` | `expand` | `chevron-down` |
| `ph-trophy` | `achievement` | `trophy` |
| `ph-graduation-cap` | `course` | `academic-cap` |
| `ph-info` | `info` | `information-circle` |

The `flag` semantic name (for "flag this question for review") does not exist yet. It should be added to `semantic_names.py` and all four mappings in `mappings.py` when implementing that feature.

---

## 4. Layout Integration

### The challenge

The runner (test-questions) screen in the design is a **full-screen fixed layout** with no sidebar, no course-player chrome, and its own sticky progress bar and sticky footer nav. The spec (idea.md) explicitly states: "Don't display the whole course player interface and side panel. Once the learner is inside the test, that is its own interface."

The start screen and results screen, by contrast, can use the normal FLS chrome (global header, no sidebar needed).

### Existing base template structure

- `freedom_ls/base/templates/_base.html` — outermost shell: `<head>`, `<header>`, `<main>`. The `{% block body %}` is inside `<main>`. The `{% block header %}` renders the global site header bar.
- `freedom_ls/base/templates/_base_interface.html` — extends `_base.html`. Its `{% block body %}` renders the sidebar+content grid. Uses `{% block sidebar_content %}` and `{% block content %}`.
- `freedom_ls/student_interface/templates/student_interface/_course_base.html` — extends `_base_interface.html`. Fills sidebar with the course TOC via HTMX.

### Recommendation

**Start screen and results screen:** Extend `_base_interface.html` directly but override `{% block sidebar_content %}` with nothing (empty) and override `{% block sidebar_class %}` if needed to suppress the sidebar column. Actually, the cleaner approach is to extend `_base.html` directly (skipping `_base_interface.html` entirely) for these screens, giving a simple page-with-header layout via `{% block body %}` → `<c-page>`.

**Runner screen:** The runner needs to suppress the global header and own the full viewport. The cleanest approach is:

1. Create a new base template `freedom_ls/student_interface/templates/student_interface/_exam_runner_base.html` that extends `_base.html` but:
   - Overrides `{% block header %}` with `{# no global header — runner owns its own bar #}` (empty)
   - Sets `<body>` / `<main>` to `h-screen flex flex-col overflow-hidden` via a block
   - Provides `{% block runner_bar %}` (for the sticky top bar + progress strip)
   - Provides `{% block runner_body %}` (scrollable question area)
   - Provides `{% block runner_footer %}` (sticky footer nav)

2. The runner template (`course_form_page.html` equivalent for exams) extends `_exam_runner_base.html`.

The critical blocks in `_base.html` to leverage:
- `{% block header %}` (line 57) — override with empty string or exam-specific bar
- `{% block body %}` (line 65) — own the full layout here
- `{% block extra_head %}` (line 39) — add any exam-specific script/style if needed

This approach keeps `_base.html`'s `<head>`, HTMX/Alpine script loading, CSRF body attribute, and Tailwind CSS link intact without any duplication.

**Summary of template hierarchy:**

```
_base.html
├── _exam_start_base.html  (extends _base.html; normal header; narrow c-page content)
│   └── course_test_start.html
├── _exam_runner_base.html (extends _base.html; no header block; full-height flex shell)
│   └── course_test_runner.html
└── _exam_results_base.html  (extends _base.html; normal header; c-page content)
    └── course_test_results.html
```

Alternatively, start and results can share a single `_exam_base.html` if their chrome is identical. The runner must be separate.

---

## 5. Easy-to-Theme Recommendations

The following authoring rules ensure the exam UI remains zero-template-change for future theme overrides.

1. **Never write a hex colour in a template.** Every colour reference must be a Tailwind utility that resolves through an `@theme` token. Examples:
   - Use `bg-primary` not `bg-[#283593]`
   - Use `bg-secondary/10` not `bg-[rgba(0,206,201,0.1)]`
   - Use `bg-surface` / `bg-white` (for elevated panels) / `bg-surface-2` for the three surface levels
   - Use `text-muted` not `text-[#718096]`
   - Use `border-border` not `border-[#E2E8F0]`

2. **Use semantic token classes for status.** `bg-success-light text-on-success-light`, `bg-warning-light`, `border-success/30` etc. These are all tokenised — `default/theme.css:38–48` and FC override at `first_class/theme.css:37–45`.

3. **Use font utilities, not font-family CSS.** `font-display` (headings), `font-sans` (body), `font-mono` (numbers / labels). These resolve to different families per theme. The exam's "eyebrow" labels (uppercase mono labels like `Q1 •`) should use `font-mono text-xs tracking-widest uppercase text-muted`.

4. **Use radius utilities.** `rounded-md` (buttons/inputs), `rounded-lg` (cards), `rounded-pill` (chips/pills). The FC theme scales these slightly larger (`first_class/theme.css:67–69`); the default theme uses smaller values. Never hardcode `border-radius` in a `style=""` attribute.

5. **Express the progress bar fill with `bg-secondary`.** The design explicitly uses `--color-secondary` (teal) for the progress fill in the runner (`fc-runner-progress .fill`, runner.html:158). Under the default theme this maps to slate-grey; under first_class it's teal. This is intentional theme variation — do not hardcode the teal.

6. **Express the "almost" / in-progress state with `bg-secondary/10 text-secondary` chip or border.** The design uses secondary-tinted surfaces for encouraging/neutral states (`.fc-result-banner.almost::before`). In templates, write `border-secondary/40 bg-secondary/8` — these opacity modifiers work with any theme's secondary colour.

7. **The score ring SVG strokes.** The SVG circle uses `stroke` colours. Express these as `stroke="currentColor"` with a wrapper having `text-primary` or `text-success` as appropriate. This lets themes change the ring colour by overriding `--color-primary` / `--color-success`.

8. **Component-tier overrides (Tier 2).** If the first_class theme needs specific exam-component shapes (e.g. chunkier choice row radii), add them to `freedom_ls/themes/first_class/static/themes/first_class/theme.css` in an `@layer components` block (as the FC theme already does for `.btn`, `.chip`, `.surface` at lines 85–153). Do not patch the exam templates themselves.

9. **Do not add Phosphor CSS font links to any template.** Icons must go through `c-icon` → `icon_tags.py` → SVG rendering pipeline. This keeps icons theme-independent and avoids a CDN dependency.

---

## Appendix: Key File References

| File | Purpose |
|---|---|
| `freedom_ls/themes/default/static/themes/default/theme.css` | All FLS `@theme` token definitions (brand, status, surface, shape, type) |
| `freedom_ls/themes/first_class/static/themes/first_class/theme.css` | First-class overrides for brand, surfaces, radii, fonts |
| `tailwind.components.css` | `@layer components`: `.btn`, `.surface`, `.chip`, `.alert`, `.header` |
| `tailwind.input.css` | Import order: default tokens → components → active theme |
| `freedom_ls/base/templates/_base.html` | Root HTML shell; `{% block header %}`, `{% block body %}` |
| `freedom_ls/base/templates/_base_interface.html` | Sidebar+content grid shell |
| `freedom_ls/student_interface/templates/student_interface/_course_base.html` | Course TOC sidebar |
| `freedom_ls/student_interface/templates/student_interface/course_form_page.html` | Current question renderer (inline partials for question types) |
| `freedom_ls/student_interface/templates/student_interface/course_form.html` | Current form start/overview screen |
| `freedom_ls/student_interface/templates/student_interface/course_form_complete.html` | Current results screen |
| `freedom_ls/base/templates/cotton/button.html` | `c-button` — variant, icon_left/right, loading |
| `freedom_ls/base/templates/cotton/button-group.html` | `c-button-group` — space-between, centered, etc. |
| `freedom_ls/base/templates/cotton/chip.html` | `c-chip` — variant, size, icon |
| `freedom_ls/base/templates/cotton/modal.html` | `c-modal` — Alpine dialog with title/footer slots |
| `freedom_ls/base/templates/cotton/page.html` | `c-page` — max-width wrapper, flush mode |
| `freedom_ls/base/templates/cotton/form-page-link.html` | `c-form-page-link` — numbered page navigation dots |
| `freedom_ls/base/templates/cotton/markdown-container.html` | `c-markdown-container` — rendered markdown wrapper |
| `freedom_ls/icons/mappings.py` | Icon set mappings (heroicons default; phosphor mapping also available) |
| `freedom_ls/icons/semantic_names.py` | Authoritative list of valid semantic icon names |
| `config/settings_base.py:60` | `FREEDOM_LS_ICON_SET = "heroicons"` (active icon set) |
| `/home/sheena/workspace/lms/design/computed/exam/desktop/start_page.html` | Design source: start screen (CSS variables + markup) |
| `/home/sheena/workspace/lms/design/computed/exam/desktop/runner.html` | Design source: runner screen |
| `/home/sheena/workspace/lms/design/computed/exam/desktop/results_pass.html` | Design source: results screen |

status: ok
reason: all five deliverables completed with repo file:line references
