# Configuration and Extension

_Last updated: 2026-07-18_

## Summary

- Branding (logo, favicon, header title, email fonts/logo) is controlled by settings constants — no template editing required for basic customisation.
- A three-tier theming system lets downstream projects override CSS tokens, slot content within components, or shadow entire template files, in order of increasing depth.
- Two bundled themes ship with FLS (`default`, `first_class`); the active theme is selected by the `FLS_THEME` setting at Tailwind build time and runtime.
- The icon set is pluggable via `FREEDOM_LS_ICON_SET`; the only currently implemented set is `heroicons`.
- FLS is designed to be installed into a host Django project; downstream apps, templates, and cotton components take priority over FLS defaults, and additional cotton components can be registered as markdown widgets.
- An opt-in conformance suite (`freedom_ls.contrib.conformance`) lets a downstream project verify its own FLS integration is wired correctly, checking only the pieces it has chosen to keep.

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

Course content can include typed "admonition" boxes — labelled, coloured callout panels such as *Note*, *Tip*, *Warning*, and *Key Takeaways*. The set of available types is configurable per deployment via the `ADMONITION_TYPES` setting: a downstream project can add its own types — each with a label, a status colour, and an icon — or override the built-ins, with no template edits, database changes, or migrations. An unrecognised type falls back to a default style rather than failing.

For example, an aviation course might want special admonition types for regulations, a parent support course could have a "try this with your child" admonition, etc.

For authoring the admonition widget in content, see [content editing workflow](./content-editing-workflow.md).

## Pluggable Course Access Backend

Each course carries an access configuration that controls what a learner may do — self-enrol, apply, view content — and what call-to-action they see on the course detail page and dashboard. The active backend is selected via `COURSE_ACCESS_BACKEND`.

FLS ships with the application-gated backend as the default, so both free and application-gated courses work out of the box. A deployment that does not want course applications sets `COURSE_ACCESS_BACKEND` to the free-only core default backend; the apply flow, its call-to-action, and its dashboard panel are all owned by the backend plugin, so switching backends removes them entirely — there is nothing to remove from any core screen.

Adding a future access model — for example a subscription or a per-course purchase — is a new backend class and a `COURSE_ACCESS_BACKEND` change, with no template, view, or migration work.

Access configuration is authored per course in the content-loading pipeline. For how a learner experiences the two current access types, see [learner experience](./learner-experience.md). For authoring a course's access type, see [content editing workflow](./content-editing-workflow.md).

A companion setting, `COURSE_ACCESS_CONFIG_VALIDATOR`, names the validator used to check each course's access configuration at content-load time. A custom backend that introduces its own configuration keys swaps this setting to point at its own validator; in most deployments it does not need to be set.

A downstream project can confirm this setting is wired correctly, without a live request, using the conformance suite (see [Conformance Suite (Verifying a Downstream's Wiring)](#conformance-suite-verifying-a-downstreams-wiring)).

Course **visibility** (published, coming soon, or hidden) is layered on top of the access backend and is orthogonal to it: a course's access type (free vs. application-gated) and its visibility are independent concerns that compose freely. Visibility is enforced uniformly across every backend — the free backend, the application-gated backend, and any future custom backend a deployment adds — with no per-backend configuration and no way to bypass or opt out of it; a new access backend added via `COURSE_ACCESS_BACKEND` automatically honours coming-soon and hidden without any extra work. Visibility is also independent of `COURSE_ACCESS_CONFIG_VALIDATOR`: it is not part of `access_config` and is not subject to access-configuration validation, so the two remain separate pipelines. For the learner-facing effect of each visibility state, see [learner experience](./learner-experience.md); for how visibility is authored on a course, see [content editing workflow](./content-editing-workflow.md).

## Preview Overrides for Course Visibility and Access (Dev/Staging Only)

Two global settings, owned alongside `COURSE_ACCESS_BACKEND`, let a dev or staging deployment preview coming-soon, hidden, or access-gated courses exactly as they will behave once launched, without editing any course data. `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` makes every course reachable and present as fully published — no "Coming soon" badge or "I'm interested" prompt, and a coming-soon course's enrol action self-registers the learner. `OVERRIDE_COURSE_ACCESS_TO_FREE` makes every course show a "Free" badge and be freely self-registerable and enterable, regardless of its configured access type. Both apply uniformly across every site's courses.

Both settings default to `False`, so a deployment that never sets them is unaffected, and neither writes to the database — a course's stored visibility and access configuration are untouched; only how it is presented and entered changes. Because leaving either on in production would be damaging, a system check emits a warning (not a blocking error) whenever either is `True` while `DEBUG` is `False`, naming the settings and prompting the operator to unset them; they are intended only for a settings module that also keeps `DEBUG = True`, and are not enabled by default in any shipped settings module.

For the learner-facing effect of course visibility and access states, see [learner experience](./learner-experience.md).

## Custom-App Extension Model

FLS is designed to be installed into an existing Django project using `git submodule add` and `uv add`. The host project retains control:

- **INSTALLED_APPS priority.** Apps listed after FLS apps in `INSTALLED_APPS` can override FLS behaviour through Django's standard app-override mechanisms.
- **Template priority.** The host project's template directories are searched before FLS template directories. Any FLS template can be replaced by providing a file at the same path in the host project.
- **Cotton component registration.** Downstream projects can register additional cotton component tags by adding entries to `MARKDOWN_ALLOWED_TAGS` in settings. Registered tags become available as markdown widgets in content authored for that installation.

This model means FLS is not a black-box package; the host project has full override capability at every layer.

## Conformance Suite (Verifying a Downstream's Wiring)

Because FLS is designed to be installed, extended, and partially overridden, a downstream project can get its settings and URL wiring wrong in ways that pass Django's own configuration checks yet still fail for a learner at runtime — a required setting left unset, or a URL include quietly missing. FLS addresses this with a conformance suite: an importable module, `freedom_ls.contrib.conformance`, that a downstream project brings into its own test suite to answer one question — "have I wired FLS up correctly?"

The suite is opt-in rather than automatic: a downstream chooses to import it into its own tests, so it never runs unannounced in a project that hasn't asked for it. FLS is its own first user of the suite, so it is proven green against FLS's own reference configuration before any downstream relies on it.

The suite is built around the same override philosophy as the rest of FLS. It checks only the seams a downstream project actually chose to keep. If a downstream removes an FLS app entirely, that app's checks are skipped rather than failed. If a downstream keeps an app but customises one of its own internal pages, that individual check can be turned off, while the checks covering routes that other parts of FLS depend on continue to enforce that the integration hasn't silently broken.

At a product level, the suite confirms that:

- FLS's page and feature wiring reverses correctly, including the sitemap and robots wiring every deployment is expected to provide.
- The configured course-access backend actually loads and can be created, not just that a setting for it exists.
- The active visual theme and icon set resolve to real, usable assets.
- The database schema and the code's data model are in step, with no pending changes that were never turned into a migration.

The checks are fast and require no database connection or network access, so they are cheap enough to run as part of a downstream's ordinary test run.

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
| `COURSE_ACCESS_BACKEND` | Selects the pluggable course-access backend (see "Pluggable Course Access Backend" above). Default is the application-gated backend; set to the free-only core default to disable the course-application flow entirely. |
| `COURSE_ACCESS_CONFIG_VALIDATOR` | Dotted-path to the validator called at content-load time to check each course's access configuration. Swap this when using a custom backend with its own configuration keys. |
| `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` | Dev/staging-only preview override that makes every course present as published, regardless of its real visibility. See "Preview Overrides for Course Visibility and Access" above. |
| `OVERRIDE_COURSE_ACCESS_TO_FREE` | Dev/staging-only preview override that makes every course present and behave as freely accessible, regardless of its real access configuration. See "Preview Overrides for Course Visibility and Access" above. |
