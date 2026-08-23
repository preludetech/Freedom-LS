# Configuration and Extension

_Last updated: 2026-08-23_

## Summary

- Branding (logo, favicon, header title, email logo) is set through configuration — no template editing needed.
- Theming works at three increasing depths: override CSS tokens, fill slots inside components, or replace whole template files.
- Two themes ship (`default`, `first_class`), selected by `FLS_THEME`. Four icon sets are available, selected by `FREEDOM_LS_ICON_SET`.
- Course access is a pluggable backend, so a deployment can offer free enrolment, application-gated courses, or a model of its own.
- FLS is designed to be installed into a host Django project, which retains override priority at every layer.
- An opt-in conformance suite lets a downstream project verify it has wired FLS up correctly.
- Common wiring mistakes are reported by Django's configuration checks at boot, rather than as a runtime error on a learner's first request.

## Branding

These settings control visual and email branding without any template change. All are optional; FLS ships with defaults.

| Setting | Effect |
|---|---|
| `HEADER_LOGO_STATIC_PATH` | Logo in the navigation bar |
| `FAVICON_STATIC_PATH` | Browser tab favicon |
| `HEADER_TITLE` | Text in the navigation bar, alongside or instead of the logo |
| `HEADER_TITLE_STYLE` | Inline CSS applied to the header title |
| `EMAIL_LOGO_STATIC_PATH` | Logo embedded in outbound emails |

## Three-Tier Theming

Each tier is independent and they can be combined.

**Tier 1 — CSS tokens.** Override colour, shape, and typography tokens in the active theme's stylesheet. No template changes. This covers most branding work: brand colours, fonts, rounded versus sharp corners.

**Tier 2 — component slots.** Course card and course row components expose named slots (`eyebrow`, `footer`) a downstream template can fill without forking the component, and accept a mergeable `class` attribute for layout tweaks. Changes content and layout within a component while leaving its logic alone.

**Tier 3 — whole-file shadowing.** Any FLS template can be replaced entirely by placing a file at the same relative path in the downstream project's theme template directory, which the template loader searches first. Use this when tiers 1 and 2 are not enough.

**Report typography.** The [cohort report](./reports.md) follows the same model: it names no colour and no font family of its own. It takes its colours from the built theme stylesheet, so it matches whichever theme is active, and its typefaces from settings. A downstream project rebrands the report by supplying its own font files and overriding those settings — no template changes needed. The settings are listed [below](#settings-reference).

## Themes and Icons

Two themes ship: **`default`** (the standard FLS style) and **`first_class`** (an alternative). The active one is chosen by `FLS_THEME`, which is read both at Tailwind build time — to decide which theme's CSS to compile — and at runtime for template resolution. **The Tailwind build must be re-run whenever `FLS_THEME` changes**; it cannot be switched at runtime alone.

Icons are referenced by semantic name (`lock`, `check`, `arrow-right`) rather than library-specific glyph names, and those names are mapped onto the active library. Four icon sets are implemented — `heroicons`, `lucide`, `tabler`, and `phosphor` — selected by `FREEDOM_LS_ICON_SET`. Adding another requires supplying a mapping from FLS's semantic names to that library's identifiers.

## Configurable Admonition Types

Course content can include typed "admonition" callout panels — *Note*, *Tip*, *Warning*, *Key Takeaways* and so on. The available set is configurable per deployment via `ADMONITION_TYPES`: a downstream project can add its own types, each with a label, a status colour, and an icon, or override the built-ins — with no template edits, database changes, or migrations. An unrecognised type falls back to a default style rather than failing.

For example, an aviation course might add a type for regulations; a parenting course might add "try this with your child".

For authoring admonitions in content, see [content editing workflow](./content-editing-workflow.md).

## Pluggable Course Access

Each course carries an access configuration controlling what a learner may do — self-enrol, apply, view content — and what call-to-action they see. The active backend is chosen by `COURSE_ACCESS_BACKEND`.

FLS's reference configuration selects the application-gated backend, so both free and application-gated courses work out of the box. A deployment that does not want course applications points `COURSE_ACCESS_BACKEND` at the free-only backend instead; the apply flow, its call-to-action, and its dashboard panel all belong to the backend, so switching removes them entirely — there is nothing left behind on any core screen. The setting has no built-in fallback value: a downstream project must set it.

Adding a future access model — a subscription, a per-course purchase — is a new backend class and a settings change, with no template, view, or migration work.

`COURSE_ACCESS_CONFIG_VALIDATOR` names the validator that checks each course's access configuration when content is loaded. A custom backend introducing its own configuration keys points this at its own validator; most deployments never set it.

Access configuration is authored per course — see [content editing workflow](./content-editing-workflow.md). For how learners experience the two current access types, see [learner experience](./learner-experience.md).

## Course Visibility

Course **visibility** (published, coming soon, or hidden) is orthogonal to access: the two compose freely, so an application-gated course can also be coming soon. Visibility is enforced uniformly across every backend — including any custom one a deployment adds — with no per-backend configuration and no way to opt out. It is also outside access-configuration validation entirely, so the two remain separate pipelines.

See [learner experience](./learner-experience.md) for the learner-facing effect of each state, and [content editing workflow](./content-editing-workflow.md) for how visibility is authored.

## Preview Overrides (Dev and Staging Only)

Two settings let a dev or staging deployment preview coming-soon, hidden, or access-gated courses as they will behave once launched, without editing course data:

- `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` — every course presents as fully published: no "Coming soon" badge, no "I'm interested" prompt, and the enrol action self-registers the learner.
- `OVERRIDE_COURSE_ACCESS_TO_FREE` — every course shows a "Free" badge and is freely self-registerable and enterable, whatever its configured access type.

Both default to off and neither writes to the database — stored visibility and access configuration are untouched, only presentation changes. Because leaving either on in production would be damaging, a system check warns (without blocking) whenever either is on while debug mode is off. They are intended only for settings modules that also run in debug mode, and no shipped settings module enables them in production.

## Custom-App Extension Model

FLS is designed to be installed into an existing Django project as a git submodule. The host project keeps control:

- **App priority.** Apps listed after FLS's own can override FLS behaviour through Django's standard app-override mechanisms.
- **Template priority.** The host project's template directories are searched first, so any FLS template can be replaced by providing a file at the same path.
- **Content widget registration.** A downstream project can register additional content widgets by adding them to the markdown tag allowlist, making them available in that installation's authored content.

FLS is not a black box; the host project has override capability at every layer.

**One stated exception — the report's at-risk rules.** The rules that flag learners as needing attention in the [cohort report](./reports.md) are a fixed, ordered list in code. There is no setting pointing at a downstream rule list and no database-backed configuration, so a project needing a rule of its own — or a different inactivity threshold — must fork until rule selection moves into the database. See the [roadmap](./roadmap.md).

## Conformance Suite

Because FLS is meant to be installed, extended, and partially overridden, a downstream project can wire it up wrongly in ways that pass Django's own configuration checks yet still fail for a learner at runtime — a required setting left unset, a URL include quietly missing. The conformance suite is an importable module a downstream project brings into its own test suite to answer one question: *have I wired FLS up correctly?*

It is opt-in, so it never runs unannounced in a project that has not asked for it, and FLS is its own first user, so it is proven green against FLS's reference configuration before any downstream relies on it.

It follows the same override philosophy as the rest of FLS: it checks only the seams a downstream actually chose to keep. Remove an FLS app entirely and its checks are skipped rather than failed. Keep an app but customise one of its own pages and that individual check can be turned off, while the checks covering routes other parts of FLS depend on keep enforcing that the integration has not silently broken.

The suite confirms that:

- FLS's page and feature wiring resolves, including the sitemap and robots wiring every deployment is expected to provide.
- The configured course-access backend actually loads and can be created, not merely that a setting exists.
- The active theme and icon set resolve to real, usable assets.
- The database schema and the code's data model are in step, with no model change left un-migrated.

The checks need no database connection or network access, so they are cheap enough to run in an ordinary test run. A concrete project should run them as a pre-launch check — see [deployment](./deployment.md).

## Boot-Time System Checks

Some wiring mistakes are caught earlier still. FLS registers checks with Django's own configuration-check framework, so they run automatically on every `manage.py check`, `runserver`, and `migrate` — unlike the conformance suite above, which is opt-in and runs in a test suite. Two integration mistakes now fail at boot rather than as a runtime error on a learner's first request: pointing `COURSE_ACCESS_BACKEND` at one of FLS's own backends whose app has been removed from the project is an error, and wiring a sitemap URL without Django's sitemaps app installed is a warning — a warning rather than an error because a deployment supplying its own sitemap page is a legitimate configuration. A deployment's own custom backend is left alone, and removing an FLS app removes that app's checks with it.

Each check identifies exactly one condition, so a deployment can silence one precisely through Django's standard silenced-checks setting. As part of that, a course-access error ID that previously covered two conditions was split: a deployment silencing `freedom_ls_course_access.E001` because of course access-configuration validation must move that entry to `freedom_ls_course_access.E002`, or it will keep suppressing the unset-required-setting error too.

## Settings Reference

| Setting | Effect |
|---|---|
| `FLS_THEME` | Active theme. Read at Tailwind build time and runtime; requires a rebuild to change. |
| `FREEDOM_LS_ICON_SET` | Active icon set: `heroicons`, `lucide`, `tabler`, or `phosphor`. |
| `ADMONITION_TYPES` | The admonition callout types available to content authors. |
| `COURSE_ACCESS_BACKEND` | Selects the course-access backend. Must be set; the reference configuration uses the application-gated backend. |
| `COURSE_ACCESS_CONFIG_VALIDATOR` | Validator for each course's access configuration at content-load time. |
| `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` | Dev/staging preview override — every course presents as published. |
| `OVERRIDE_COURSE_ACCESS_TO_FREE` | Dev/staging preview override — every course presents as free. |
| `ALLOW_SIGN_UPS` | Installation-wide signup toggle; a site's own signup policy takes precedence. |
| `REQUIRE_NAME` | Installation-wide default for requiring a name at registration. |
| `REQUIRE_TERMS_ACCEPTANCE` | Installation-wide default for requiring terms acceptance. |
| `DEADLINES_ACTIVE` | Enables or disables deadline features site-wide. |
| `FORCE_SITE_NAME` | Pins the installation to one site instead of resolving by host. |
| `TRUSTED_PROXY_IP_HEADER` | Header to trust for the client IP behind a reverse proxy. |
| `DJANGO_ADMIN_URL` | Path the Django admin is mounted at. See [admin interface](./admin-interface.md). |
| `REPORTS_STORAGE_ALIAS` | Storage the cohort report PDF is written to. See [security and data handling](./security-and-data-handling.md). |
| `REPORTS_MAX_LEARNERS` | Caps the cohort size a report will generate for, bounding render time and memory. |
| `REPORTS_MAX_QUIZ_COLUMNS` | Caps how many quiz columns a course's landscape summary table carries before splitting into a continued table. |
| `REPORTS_FONT_FACES` | The font files embedded in the report PDF. |
| `REPORTS_FONT_DISPLAY` | Font stack for the report's headings. |
| `REPORTS_FONT_BODY` | Font stack for the report's body text. |
| `REPORTS_FONT_MONO` | Font stack for the report's monospace text. |

Branding settings are listed [above](#branding). Deployment and storage settings are covered in [deployment](./deployment.md); per-site signup policy in [authentication](./authentication.md). What the cohort report contains is documented in [cohort reports](./reports.md).
