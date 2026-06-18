# Configuration and Extension

_Last updated: 2026-06-18_

## Summary

- Branding (logo, favicon, header title, email fonts/logo) is controlled by settings constants — no template editing required for basic customisation.
- A three-tier theming system lets downstream projects override CSS tokens, slot content within components, or shadow entire template files, in order of increasing depth.
- Two bundled themes ship with FLS (`default`, `first_class`); the active theme is selected by the `FLS_THEME` setting at Tailwind build time and runtime.
- The icon set is pluggable via `FREEDOM_LS_ICON_SET`; the only currently implemented set is `heroicons`.
- FLS is designed to be installed into a host Django project; downstream apps, templates, and cotton components take priority over FLS defaults, and additional cotton components can be registered as markdown widgets.

## Branding Settings

The following settings in `config/settings_base.py` control visual and email branding. All are optional overrides; FLS ships with defaults.

| Setting | Effect |
|---|---|
| `HEADER_LOGO_STATIC_PATH` | Logo displayed in the navigation bar |
| `FAVICON_STATIC_PATH` | Browser tab favicon |
| `HEADER_TITLE` | Text displayed in the navigation bar alongside or instead of the logo |
| `HEADER_TITLE_STYLE` | Inline CSS applied to the header title text |
| `EMAIL_LOGO_STATIC_PATH` | Logo embedded in outbound email templates |
| `EMAIL_FONT_FAMILY` | Font family used in outbound email templates |

These settings require no template changes; they are referenced directly by FLS templates.

## Three-Tier Theming

FLS supports three levels of theme customisation. Each tier is independent; they can be combined.

### Tier 1 — CSS Custom Properties (Tokens)

Override colour palette, shape (border-radius), and typography tokens by editing `theme.css` in the active theme directory. No template changes are required. This is sufficient for most branding adjustments (brand colours, fonts, rounded vs. sharp corners).

### Tier 2 — Cotton Slots and Mergeable Classes

Course card and course-row components expose named cotton slots (`eyebrow`, `footer`) that downstream templates can fill without forking the component. They also accept a mergeable `class` attribute for layout overrides. This level changes content or layout within a component while leaving the component's logic untouched.

### Tier 3 — Whole-File Template Shadowing

Any FLS leaf template can be replaced entirely by placing a file at the same relative path inside the downstream project's theme template directory. Django's template loader gives downstream project templates priority over FLS defaults. Use this tier when Tier 1 and Tier 2 are insufficient.

## Bundled Themes

Two themes ship with FLS:

- **`default`** — the standard FLS visual style.
- **`first_class`** — an alternative visual style.

Theme files live in `freedom_ls/themes/default/` and `freedom_ls/themes/first_class/`. The active theme is selected by `FLS_THEME`. This setting is read at **Tailwind build time** (to determine which theme's CSS to compile) and at runtime (for template resolution). The Tailwind build must be re-run whenever `FLS_THEME` changes.

## Pluggable Icon Set

FLS uses a semantic icon name system: component templates reference icon names such as `lock`, `check`, `arrow-right` rather than library-specific glyph names. These semantic names are mapped to the active icon library's identifiers in `freedom_ls/icons/mappings.py`.

The active icon set is configured via `FREEDOM_LS_ICON_SET`. The only currently implemented set is `heroicons`. Adding a new icon set requires providing a mapping from FLS's semantic names to the new library's identifiers.

## Configurable Admonition Types

`ADMONITION_TYPES` is a deploy-time settings dict defined in `config/settings_base.py`. It is the registry that drives the `c-admonition` content widget — each entry maps a type key to the visual and semantic properties FLS uses when rendering an admonition box of that type.

Each entry has the following fields:

| Field | Required | Description |
|---|---|---|
| `label` | yes | Default visible heading text shown inside the box when the author does not supply a `title` attribute. |
| `color` | yes | One of the four status role tokens: `info`, `success`, `warning`, `error`. Maps to the theme's role-token colour pair; adapts automatically across all bundled themes. |
| `icon` | yes | Either a semantic icon name (from `freedom_ls/icons/`) or a literal glyph name from the active icon set. Resolved through the same shared resolver used for course icons — see [Pluggable Icon Set](#pluggable-icon-set) for resolution mechanics. |
| `icon_fallback` | no | A `<iconset>:<glyph>` string used when `icon` is a literal glyph that does not exist in the active icon set (e.g. `heroicons:scale`). Follows the same fallback mechanism as the course icon `icon_fallback` field. |

The four `color` values map directly to the theme's status role tokens (`--color-info`, `--color-success`, `--color-warning`, `--color-error` and their `-light` tint pairs), so every admonition type automatically adapts to every bundled theme without any per-theme configuration.

### Default registry

The following registry ships in `config/settings_base.py` and is available in all deployments:

```python
ADMONITION_TYPES = {
    "note":          {"label": "Note",         "icon": "info",    "color": "info"},
    "tip":           {"label": "Tip",          "icon": "star",    "color": "success"},
    "important":     {"label": "Important",    "icon": "warning", "color": "warning"},
    "warning":       {"label": "Warning",      "icon": "warning", "color": "warning"},
    "danger":        {"label": "Danger",       "icon": "error",   "color": "error"},
    "key_takeaways": {"label": "Key Takeaways","icon": "notes",   "color": "info"},
    "checklist":     {"label": "Checklist",    "icon": "check",   "color": "success"},
    "default":       {"label": "Note",         "icon": "info",    "color": "info"},
}
```

All default entries use semantic icon names and therefore do not require an `icon_fallback`.

The `default` entry is mandatory and acts as the graceful fallback for any unknown type. If an author writes `<c-admonition type="someunknowntype">`, FLS looks up the type in the registry, finds nothing, and silently falls back to the `default` entry. The widget always renders; it never errors or produces a blank box.

### Overriding or extending the registry per deploy

Downstream projects can add domain-specific types, or replace any default entry, by redefining `ADMONITION_TYPES` in their own settings file. Because the base registry is a plain Python dict imported via `from .settings_base import *`, the idiomatic pattern is to spread the inherited dict and add new entries:

```python
# config/settings_dev.py (or any host-project settings override)
ADMONITION_TYPES = {
    **ADMONITION_TYPES,  # noqa: F405
    "regulation": {
        "label": "Regulation",
        "icon": "scale",
        "icon_fallback": "heroicons:scale",
        "color": "warning",
    },
}
```

This example (the pattern used in `config/settings_dev.py`) adds a `regulation` type. The `icon` value `"scale"` is a literal glyph name; `icon_fallback` provides a fully-qualified `<iconset>:<glyph>` reference used if the literal name is not present in the active icon set. This is exactly how a course's `icon` and `icon_fallback` fields work — both go through the shared resolver in `freedom_ls/icons`, which lets domain-specific types use unusual icon glyphs that have no semantic alias.

This registry is settings-only: adding or changing admonition types requires only a settings change and a process restart — no database migration, no admin UI, and no schema change. Per-site database-backed admonition configuration is out of scope; the settings dict is the only configuration surface.

For the `c-admonition` widget authoring syntax (attributes, body markdown, examples), see [content editing workflow](./content-editing-workflow.md).

## Custom-App Extension Model

FLS is designed to be installed into an existing Django project using `git submodule add` and `uv add`. The host project retains control:

- **INSTALLED_APPS priority.** Apps listed after FLS apps in `INSTALLED_APPS` can override FLS behaviour through Django's standard app-override mechanisms.
- **Template priority.** The host project's template directories are searched before FLS template directories. Any FLS template can be replaced by providing a file at the same path in the host project.
- **Cotton component registration.** Downstream projects can register additional cotton component tags by adding entries to `MARKDOWN_ALLOWED_TAGS` in settings. Registered tags become available as markdown widgets in content authored for that installation.

This model means FLS is not a black-box package; the host project has full override capability at every layer.

## Per-Site Signup Policy and Additional Registration Forms

Each site in a multi-site FLS installation can have its own `SiteSignupPolicy`, which controls:

- Whether public signups are allowed (`allow_signups`).
- Whether users must provide their full name at registration (`require_name`).
- Whether terms acceptance is required (`require_terms_acceptance`).
- A list of additional registration form classes (`additional_registration_forms` — a JSONField of dotted-path form class strings).

Additional registration forms are presented to users after the standard signup step. The `RegistrationCompletionMiddleware` intercepts authenticated users with incomplete additional forms and redirects them to the completion view before they can access other parts of the site.

For the full isolation model that underpins per-site configuration, see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Other Configuration Flags

| Setting | Effect |
|---|---|
| `ALLOW_SIGN_UPS` | Global signup toggle (site-level `SiteSignupPolicy` takes precedence when set) |
| `REQUIRE_TERMS_ACCEPTANCE` | Global default for terms acceptance requirement |
| `REQUIRE_NAME` | Global default for requiring name at registration |
| `DEADLINES_ACTIVE` | Enables or disables the deadline UI features site-wide |
| `TRUSTED_PROXY_IP_HEADER` | Header to trust for client IP when running behind a reverse proxy (relevant to deployment configuration; not documented in the public how-to guides) |
