# Themable Freedom LS

## Goal

Freedom LS is installed as a dependency into other Django applications (e.g. Bloom — soft, purple, rounded; FirstClass — polished, corporate). Those applications need to rebrand FLS without re-implementing complicated templates.

We want a theming mechanism that:

- Lets a downstream project drop in a self-contained theme directory and select it via a single setting.
- Covers cheap rebranding (colours, corner radius, brand fonts) with **no template work and no Tailwind rebuild downstream is forced into**.
- Lets a theme override individual cotton components or page shells when variables aren't enough — without forking the rest of FLS.
- Ships a `default` theme that doubles as the reference / template for downstream themes.

## Approach: three tiers

Research (`research_component_library_dx.md`, `research_tailwind_v4_theming.md`) converges on a layered surface. Variables alone fail (Bootstrap), template overrides alone are brittle (Oscar). FLS gets all three, layered cheapest-first.

**Tier 1 — Design tokens (CSS custom properties).**
A small, role-named token set on `:root` (and later `[data-theme="…"]`). Narrow scope to start:

- Colour roles: `surface`, `on-surface`, `surface-muted`, `accent`, `on-accent`, `accent-muted`, `success`, `on-success`, `danger`, `on-danger`, `border`, `focus-ring`. (Largely a rename/extension of the current `--color-primary` / `--color-on-primary` set.)
- Shape: `--fls-radius-sm`, `--fls-radius-md`, `--fls-radius-lg`, `--fls-radius-pill`.
- Type: `--fls-font-sans`, `--fls-font-display` (two knobs only).

Use Tailwind v4's `@theme inline` so utilities compile to `var(--…)` and follow the cascade — that way a static rebrand (downstream redeclares `@theme`) and a future runtime swap (set `data-theme`) both work without further code changes. Density / full 50–950 ramps / spacing scale tokens are explicitly **out of scope** until a real use-case demands them.

**Tier 2 — Semantic component classes consumers extend in their own Tailwind input.**
FLS keeps its `btn`, `btn-primary`, `chip`, `chip-success`, `surface` etc. as the public visual contract. A downstream project re-opens these inside `@layer components` in its own `tailwind.input.css` to tweak shape or add shadows — no template fork required:

```css
@layer components {
  .btn-primary { @apply rounded-2xl shadow-sm; }
}
```

These class names become public API with deprecation rules (treated like a Python signature — don't rename casually).

**Tier 3 — Template overrides via the theme directory.**
For genuine restructure (different page shell, replaced header, custom card layout), a theme is a directory of templates that wins the loader race. Cotton components are overridable by dropping `cotton/<name>.html` into the theme dir; cotton already delegates to Django's standard template loader chain.

The `<c-vars …>` surface of every cotton component is the public contract. Overriding a cotton component means honouring its full `<c-vars>` declaration plus `{{ attrs }}` and `{{ slot }}` forwarding.

## Theme directory shape

A theme is a self-contained directory:

```
themes/<theme_slug>/
    templates/
        cotton/                  # override any cotton component
        partials/                # override page-shell partials (header, footer, logo)
        _base.html               # optional: full page-shell override
    static/
        themes/<theme_slug>/
            theme.css            # token bundle + Tier-2 component tweaks
            logo.svg             # brand assets
            ...
    theme.md                     # human-readable manifest: name, version, what it overrides
```

Themes contain *only* visual primitives — cotton components, page shells, brand assets, the token CSS. App-level templates (student dashboards, educator views, etc.) stay in their FLS apps; they consume cotton components and naturally pick up theme overrides.

## Default theme — first-class, not a fallback

FLS ships `freedom_ls/themes/default/` containing the current cotton components, page shells and tokens. The default theme is selected when no override is configured. It is structured and documented well enough to be **copied wholesale as a starting point** for a downstream theme — i.e. the reference implementation for theme authors. Migration moves the existing cotton component templates and `tailwind.components.css` content into this directory; FLS app templates stay where they are.

## Selecting a theme

One setting, one env var:

```python
FLS_THEME = env("FLS_THEME", default="default")
FLS_THEMES_DIRS = [BASE_DIR / "themes", FREEDOM_LS_PACKAGE / "themes"]
```

Resolution: walk `FLS_THEMES_DIRS` in order, use the first directory whose name matches `FLS_THEME`. The downstream project's own `themes/` dir comes first, so a downstream theme named `default` shadows the FLS one cleanly. The resolved theme's `templates/` dir is prepended to `TEMPLATES[0]["DIRS"]`; its `static/` dir is prepended to `STATICFILES_DIRS`.

## Tailwind build ownership

The current "copy `tailwind.input.css` and edit it" install step is replaced by a documented downstream input file:

```css
@import "tailwindcss";
@source "<path-to-freedom_ls>/**/templates/**/*.html";
@source "./themes/<theme_slug>/templates/**/*.html";
@import "<path-to-freedom_ls>/themes/default/static/themes/default/theme.css";
@import "./themes/<theme_slug>/static/themes/<theme_slug>/theme.css";

@theme {
    /* downstream project-level overrides, optional */
}
```

The install guide (`docs/how tos/incorperate into another project.md`) is rewritten to describe this. No backward-compatibility path is needed.

## Out of scope (deferred)

- **Per-site theming on a single deployment.** Architecturally feasible (custom site-aware template loader, `cached.Loader` cache-key plumbing) but adds real complexity and breaks for management-command/email rendering. Defer until a deployment actually needs to host two brands.
- **Per-site Tailwind-variable-only override.** A lighter form of the above — same `data-theme="…"` attribute on `<body>` based on current Site, with a per-site CSS variable bundle. Easier than full per-site theming because it needs no template loader changes; revisit when the demand arrives.
- **Full 50–950 colour ramps**, density tokens, fine-grained spacing scale — only if a real component needs them.
- **Theme inheritance / composition** (a theme that extends another). Out of scope for v1; can be added later if themes start sharing pieces.

## References

- `research_django_theming.md` — patterns from allauth, Wagtail, Oscar, Mezzanine, Saleor.
- `research_django_template_overrides.md` — template loader mechanics, cotton override resolution, per-site loader sketch.
- `research_tailwind_v4_theming.md` — `@theme inline`, `data-theme`, downstream Tailwind composition, OKLCH notes.
- `research_component_library_dx.md` — three-tier token consensus, naming pitfalls, what shadcn/daisyUI/MD3/Bootstrap got right and wrong.
