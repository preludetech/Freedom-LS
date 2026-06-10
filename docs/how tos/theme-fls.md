# Theming FreedomLS

FreedomLS ships a three-tier theming model. Each tier is cheaper than the next, so reach for Tier 1 first and only drop down when you genuinely need it.

| Tier | What it changes | When to use it |
|------|-----------------|----------------|
| 1 — CSS tokens | Colours, radii, fonts | 80% of rebrands. Write one `theme.css`, point `FLS_THEME` at it, rebuild. |
| 2 — Component classes | Button shape/size, chip style, alert colour, surface appearance | The token values are right but a component's structure needs adjusting. |
| 3 — Template overrides | Cotton component markup, page-shell blocks, full HTML structure | When neither tokens nor classes can get you there. Escape hatch only. |

Defaults stay in the FLS main project: component classes live in `tailwind.components.css`, and generic templates live in `freedom_ls/base/templates/` and their owning apps. A theme is sparse — it only ships what it overrides.

---

## Theme directory shape

Only `static/themes/<slug>/theme.css` is required. Everything else is optional.

```
themes/<slug>/
    theme.md                                       # manifest (recommended)
    static/
        themes/<slug>/
            theme.css                              # Tier 1 required; Tier 2 optional
            logo.svg                               # optional brand assets
    templates/
        cotton/
            <component>.html                       # optional Tier 3 cotton overrides
        <app>/
            ...                                    # optional Tier 3 app template overrides
        _base.html                                 # optional full page-shell replacement
```

The static path is namespaced as `static/themes/<slug>/` so collected static files do not collide between themes.

### The `theme.md` manifest

Add a `theme.md` at the theme root to document what the theme contains and which tiers it uses. Model it on the default theme's manifest:

```markdown
# My theme

- **Name:** my-theme
- **Version:** 1.0
- **Overrides:** Tier 1 — tokens only. Tier 2 — button and chip shape.
- **Brand reference:** link to design docs or brand guide
```

The manifest is documentation only — FreedomLS does not read it at runtime.

---

## `FLS_THEME` and `FLS_THEMES_DIRS` — resolution and failure modes

### How the resolver works

Two settings drive theme resolution. In your `settings.py`:

```python
import os
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR, configure_theme

FLS_THEME = os.environ.get("FLS_THEME", "default")
FLS_THEMES_DIRS = [BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]

RESOLVED_THEME_DIR = configure_theme(
    theme_slug=FLS_THEME,
    themes_dirs=FLS_THEMES_DIRS,
    templates=TEMPLATES,
    staticfiles_dirs=STATICFILES_DIRS,
)
```

`configure_theme` walks `FLS_THEMES_DIRS` in order and uses the first directory that contains a subdirectory matching the slug. The default list puts `BASE_DIR / "themes"` before the FLS package directory, so placing a `themes/default/` folder in your project root shadows the built-in default.

For each resolved theme directory, `configure_theme`:

- Prepends `<theme>/templates/` to `TEMPLATES[0]["DIRS"]` if that directory exists (Tier 3 wiring).
- Prepends `<theme>/static/` to `STATICFILES_DIRS` so collected static files resolve correctly. Static directories for all discovered themes — not just the active one — are also added, so `/static/themes/<slug>/` resolves for inactive themes as well (needed for email branding and design-system pages).

### Failure mode

If `FLS_THEME` is set to a slug that does not resolve to a directory in any entry of `FLS_THEMES_DIRS`, Django raises `ImproperlyConfigured` at startup with a message naming the slug and the directories searched:

```
ImproperlyConfigured: FLS theme 'my-theme' not found in any of: [PosixPath('...')]
```

The server will not start. This is intentional — silent misconfiguration is worse than a loud failure.

### Build-time half

The Django resolver handles the runtime half (template lookup, static file serving). Tailwind handles the build-time half separately.

`npm run tailwind_build` is two steps (see `package.json`):

1. `npm run _write_active_theme` — runs `manage.py write_active_theme_css`, which resolves `FLS_THEME` through Django settings and writes `tailwind.active_theme.css` as a single `@import` pointing at the active theme's `theme.css`.
2. `@tailwindcss/cli` compiles `tailwind.input.css` to `static/vendor/tailwind.output.css`.

To switch the active theme in the FLS repo: set `FLS_THEME` (e.g. `export FLS_THEME=first_class`), then run `npm run tailwind_build`. The compiled bundle now contains the new theme's tokens.

**Downstream projects** (those consuming FLS as a submodule or package) own their own `tailwind.input.css`. In that file the active-theme import is hardcoded rather than generated:

```css
@import "./themes/<theme_slug>/static/themes/<theme_slug>/theme.css";
```

Downstream consumers still run `npm run tailwind_build` to recompile, but they do not use `write_active_theme_css` — they edit the import directly when switching themes. The FLS repo's generated `tailwind.active_theme.css` mechanism only applies inside the FLS project itself.

---

## Token contract reference

All tokens are declared in `freedom_ls/themes/default/static/themes/default/theme.css`. That file is the source of truth. The tables below reproduce every value.

### Colour roles

Every coloured background role has a paired `on-*` foreground. Always use the pair together — a button with `bg-primary` text should use `text-on-primary`.

#### Brand

| Role | Token | Default |
|------|-------|---------|
| Primary | `--color-primary` | `#2B6CB0` |
| On-primary | `--color-on-primary` | `#FFFFFF` |
| Secondary | `--color-secondary` | `#475569` |
| On-secondary | `--color-on-secondary` | `#FFFFFF` |
| Accent | `--color-accent` | `#F59E0B` |
| On-accent | `--color-on-accent` | `#1A2332` |

#### Status

| Role | Token | Default |
|------|-------|---------|
| Success | `--color-success` | `#38A169` |
| On-success | `--color-on-success` | `#FFFFFF` |
| Warning | `--color-warning` | `#F6E05E` |
| On-warning | `--color-on-warning` | `#1A2332` |
| Error | `--color-error` | `#E8553D` |
| On-error | `--color-on-error` | `#FFFFFF` |
| Info | `--color-info` | `#0EA5E9` |
| On-info | `--color-on-info` | `#FFFFFF` |

#### Status light tints

Light tints are named replacements for ad-hoc opacity modifiers in chip and alert backgrounds. The paired `on-*-light` foregrounds are darker and legible on near-white tints (the normal `on-*` whites are not).

| Role | Token | Default |
|------|-------|---------|
| Success light | `--color-success-light` | `#F0FFF4` |
| On-success-light | `--color-on-success-light` | `#22543D` |
| Warning light | `--color-warning-light` | `#FFFFF0` |
| On-warning-light | `--color-on-warning-light` | `#744210` |
| Error light | `--color-error-light` | `#FFF5F5` |
| On-error-light | `--color-on-error-light` | `#742A2A` |
| Info light | `--color-info-light` | `#EBF8FF` |
| On-info-light | `--color-on-info-light` | `#2A4365` |

#### Surfaces and structural

| Role | Token | Default |
|------|-------|---------|
| Surface | `--color-surface` | `#FFFFFF` |
| Surface 2 | `--color-surface-2` | `#F3F4F6` |
| On-surface | `--color-on-surface` | `#1A2332` |
| Border | `--color-border` | `#D1D5DB` |
| Muted | `--color-muted` | `#4A5568` |

`--color-surface-2` uses `--color-on-surface` as its foreground (no dedicated pair).
`--color-border` and `--color-muted` have no `on-*` pair.

#### Focus ring

`--color-focus-ring` is an `@theme inline` **alias** to `--color-primary`, not a standalone token:

```css
@theme inline {
    --color-focus-ring: var(--color-primary);
}
```

Because it is an alias, overriding `--color-primary` automatically updates the focus ring colour. A theme that wants a distinct focus colour must explicitly redeclare `--color-focus-ring` in its own `@theme` block. A theme that only sets `--color-primary` does not need to touch the focus ring at all.

### Hover-mix knobs

Hover variants are auto-derived from the base colour using `color-mix`. The two knobs control the mix:

| Token | Default | Notes |
|-------|---------|-------|
| `--fls-hover-mix-color` | `white` | Dark themes set this to `black` to invert direction |
| `--fls-hover-mix-amount` | `12%` | Increase for stronger hover contrast |

Tokens `--color-primary-hover`, `--color-secondary-hover`, `--color-accent-hover`, `--color-success-hover`, `--color-warning-hover`, `--color-error-hover`, and `--color-info-hover` are computed automatically. Any single hover token can be overridden with an explicit value when the auto-mix is not right.

### Shape tokens

| Token | Default | Tailwind alias |
|-------|---------|----------------|
| `--fls-radius-sm` | `0.25rem` | `--radius-sm` → `rounded-sm` |
| `--fls-radius-md` | `0.375rem` | `--radius-md` → `rounded-md` |
| `--fls-radius-lg` | `0.5rem` | `--radius-lg` → `rounded-lg` |
| `--fls-radius-pill` | `9999px` | `--radius-pill` → `rounded-pill` |

These are aliased into Tailwind's `--radius-*` slots via `@theme inline` so `rounded-md` etc. resolve through the FLS-namespaced variables. Override the `--fls-*` values; the Tailwind utilities follow.

### Type tokens

| Token | Default | Tailwind alias |
|-------|---------|----------------|
| `--fls-font-sans` | system-ui stack | `--font-sans` → `font-sans` |
| `--fls-font-display` | same as `--fls-font-sans` | `--font-display` → `font-display` |
| `--fls-font-mono` | monospace stack | `--font-mono` → `font-mono` |

Override the `--fls-*` values to swap typefaces. Make sure external font files are loaded (e.g. via a Google Fonts `<link>` or bundled font files) before the declaration takes effect.

### Header and side-panel component-tier tokens

These are `@theme inline` aliases that default to brand role tokens, so a theme that only sets `--color-primary` gets a consistent header automatically. Override them explicitly when the header needs a different colour from the primary brand.

| Token | Default |
|-------|---------|
| `--color-header` | `var(--color-primary)` |
| `--color-on-header` | `var(--color-on-primary)` |
| `--color-header-action` | `var(--color-primary)` |
| `--color-on-header-action` | `var(--color-on-primary)` |
| `--color-sidepanel` | `var(--color-surface)` |

`--color-sidepanel` controls the docked/overlay navigation panel in `_base_interface.html`. It defaults to the page surface colour.

### Course-card accent palette

Five gradient slots are used by course-card hero tiles and progress bars. They are intentionally separate from the semantic role tokens so card vibrancy is independent of UI colours.

For each slot N (1–5), the relevant tokens are:

| Token | Default slot 1 | Purpose |
|-------|---------------|---------|
| `--fls-course-accent-N-from` | `#4F46E5` | Gradient start colour |
| `--fls-course-accent-N-to` | `#2563EB` | Gradient end colour |
| `--fls-course-accent-N-icon` | `#FFFFFF` | Hero glyph foreground |

The composite `--fls-course-accent-N` gradient and `--fls-course-accent-N-soft` tint are computed automatically from `-from`, `-to`, and the surface colour. Override only the `-from`, `-to`, and `-icon` values.

An optional `--fls-course-accent-pattern` token adds a texture layer above every accent gradient (e.g. a repeating grid). Set it to a CSS `background-image` value. `--fls-course-accent-N-pattern` targets a single slot.

### Course-card shape tokens

| Token | Default | Notes |
|-------|---------|-------|
| `--fls-card-radius` | `1rem` | Corner radius of cards |
| `--fls-card-hero-height` | `7rem` | Height of the hero colour band |
| `--fls-card-padding` | `1rem` | Body padding inside cards |

---

## Tier 2 — Re-opening component classes

FLS component classes (`.btn`, `.btn-primary`, `.chip`, `.chip-success`, `.surface`, `.alert`, `.course-card`, `.header`, etc.) are defined in `tailwind.components.css` at the FLS repo root. Their defaults live there — not in any theme.

A theme extends a class by re-opening it inside `@layer components` in its `theme.css`:

```css
@layer components {
    .btn {
        @apply px-6 py-3 text-sm font-semibold rounded-md;
    }

    .btn-secondary {
        @apply border-2;
    }
}
```

The cascade order in `tailwind.input.css` is: default tokens → component classes → active theme. Because the active theme's `theme.css` is imported last, its `@layer components` declarations win over the defaults without needing `!important`.

The `first_class` theme's `@layer components` block in `freedom_ls/themes/first_class/static/themes/first_class/theme.css` is the reference implementation for Tier-2 overrides. It overrides `.btn`, `.btn-secondary`, `.chip`, `.chip-*`, `.surface`, `.course-card`, `.signup-panel`, `.alert-*`, and `.header`.

---

## Tier 3 — Template overrides

Template overrides let a theme replace an individual cotton component, partial, or full page shell. Defaults live in the owning FLS app — not in the `default` theme — so Tier 3 is purely additive in a theme directory.

Because `configure_theme` prepends the active theme's `templates/` directory to Django's template search path, a file placed at `themes/<slug>/templates/cotton/<name>.html` resolves before the FLS app's version of the same component.

No shipped FLS theme uses Tier 3 today; the mechanism is the override path, not a shipping example. The pattern is:

**1. Cotton component override**

Drop a same-named file in the theme's templates directory:

```
themes/my-theme/templates/cotton/button.html
```

The file must honour the full `<c-vars>` contract of the component it replaces — same props with the same defaults — plus forward `{{ attrs }}` and `{{ slot }}`:

```django
<c-vars
    variant="primary"
    href=""
    class=""
/>

<button
    {% if href %}onclick="location.href='{{ href }}'"{% endif %}
    class="btn btn-{{ variant }} my-custom-class {{ class }}"
    {{ attrs }}
>
    {{ slot }}
</button>
```

Removing a prop or changing a default is a breaking change — callers that rely on the original signature will silently break.

**2. App template or partial override**

Drop a file at the same relative template path:

```
themes/my-theme/templates/student_interface/partials/course_card_registered.html
```

The file resolves before the FLS app version.

**3. Full page-shell replacement**

Drop `templates/_base.html` in the theme directory to replace the entire page shell. This is rarely necessary — prefer overriding individual cotton components or adding a CSS layer.

---

## Build pitfalls

### `@source` and `.gitignore`

Tailwind's `@source` glob honours `.gitignore`. If FLS is installed under a path excluded by an ancestor `.gitignore` — such as `.venv/`, `node_modules/`, or a nested vendor directory — the glob silently skips all templates in that subtree. You will not see build errors; utility classes that appear only in those templates will simply be absent from the compiled bundle.

**Workarounds:**

- Adjust the ancestor `.gitignore` entry to un-exclude the FLS path.
- Create a symlink from an unignored location to the FLS package directory:
  ```
  ln -s submodules/Freedom-LS/freedom_ls freedom_ls
  ```
  Then point the `@source` glob at the symlink.
- Copy the FLS templates into an unignored location as part of your build pipeline.

The `@source` path in your `tailwind.input.css` must resolve to an unignored path at build time.

### New utility classes in theme templates

If a Tier-3 template override (or a new cotton component in a theme) uses Tailwind utility classes that do not appear anywhere else in the codebase at build time, those classes will not be generated. The template file must be covered by at least one `@source` glob in `tailwind.input.css`. The downstream template example in the install guide already includes:

```css
@source "./themes/<theme_slug>/templates/**/*.html";
```

Run `npm run tailwind_build` after adding any new template file that introduces new utility classes.

---

## Worked examples

### Example A — minimal Tier-1-only theme

The smallest possible theme is a `theme.css` that redeclares the token values you want to change, plus a `theme.md` manifest.

**`themes/coral/theme.md`:**

```markdown
# Coral theme

- **Name:** coral
- **Version:** 1.0
- **Overrides:** Tier 1 — brand colour tokens only.
```

**`themes/coral/static/themes/coral/theme.css`:**

```css
@theme {
    --color-primary: #E05C4A;
    --color-on-primary: #FFFFFF;
    --color-secondary: #4A5568;
    --color-on-secondary: #FFFFFF;
}
```

Only the tokens you redeclare change. Everything else inherits from the default theme.

To activate the theme in the FLS repo: set `FLS_THEME=coral` and run `npm run tailwind_build`.

In a downstream project: add the `@import` for your theme's `theme.css` in `tailwind.input.css` (as shown in the install guide), set `FLS_THEME=coral` in your environment, and run `npm run tailwind_build`.

### Example B — Tier-1 + Tier-2 reference

`freedom_ls/themes/first_class/` is a complete Tier-1 + Tier-2 example. It:

- Overrides every token (brand, status, surfaces, shape, type) in `@theme { ... }`.
- Reopens `.btn`, `.chip`, `.surface`, `.alert-*`, `.header`, and several other component classes in `@layer components { ... }` to apply the "Modern Altitude" brand treatment.
- Uses `@theme inline { ... }` to override header and side-panel component-tier tokens.
- Adds a plain-CSS rule block (outside any `@layer`) for course-outline counter styling.

It has no `templates/` directory — Tier-3 overrides are not required and the theme works fully without them.
