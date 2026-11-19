# Semantic icons: host projects add names, own SVGs and whole icon sets

Spec 2 of 4 in the Semantic icons extraction effort. Read the "Semantic icons extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A project that installs the icons app can make its icons its own without editing the app. It does
this entirely from settings, plus a registry call for reusable apps, in three ways:

1. **Add semantic names and remap.** The host declares new names with a glyph for the sets it uses
   (`SEMANTIC_ICONS_NAMES`). The existing overrides setting remaps a name within the active set, and
   its key may now be any registered name, not only a built-in.
2. **Point a name at the host's own SVG file** (`SEMANTIC_ICONS_SVG`), for a built-in name or a
   host-added one. The file is read once, passes the existing SVG safety check and renders through
   the same path as every other icon, so class, accessible name and `data-icon` behave the same.
3. **Register a whole custom icon set** (`SEMANTIC_ICONS_SETS`): the host's own Iconify-format JSON,
   with its mapping and its variants, selectable as the active set like the four shipped ones.

Reusable Django apps add the names they own through a registry API called in `AppConfig.ready()`, so
an app that renders icons ships its own names without the host listing them.

Every path is checked at startup by Django system checks run over the merged registry. A misconfigured
host fails `manage.py check`, not a page render.

FLS's own test and demo settings exercise each path: an added name, an own SVG, a remap of an
added name, a registered custom set, and an app registration.

## Why

The effort exists so other Django projects can use the icons app. Today a closed name set means a
project that wants one more icon edits the app (four mapping dicts), and a project cannot use an icon
set the app does not ship. The panel framework's icon host contract is a checked list of 21 names;
a project that needs more than the built-ins has no way to supply them. This spec is what makes the
app usable, as opposed to merely installable, outside FLS.

## What is settled

- **Settings are flat `SEMANTIC_ICONS_*`**, read through the app's settings class, alongside the
  names `extract-semantic-icons-app-1-standalone-app` delivers (`SEMANTIC_ICONS_SET`, `SEMANTIC_ICONS_OVERRIDES`, `SEMANTIC_ICONS_BACKEND`).
  This spec adds `SEMANTIC_ICONS_NAMES` (`{new_name: {set_name: glyph}}`), `SEMANTIC_ICONS_SVG`
  (`{name: file}`) and `SEMANTIC_ICONS_SETS`.
- **The package ships all 63 current names**, FLS-domain ones (course, cohort, topic, audio, deadline
  and the rest) included. FLS registers no names of its own and needs no registration code.
- **Precedence, first hit wins: host settings, then app registrations, then built-ins.** Within the
  host: own SVG, then override, then host-added name. The host can restyle any app's icons without
  patching the app.
- **Registration rules.** An app may add only names it does not collide with. It may not shadow a
  built-in name or another app's name, and that is an error at startup, also shown by
  `manage.py check`. Apps are encouraged to prefix names with their app label. No entry-point
  auto-registration: registration is an explicit call in `ready()`.
- **Coverage.** Built-in names keep full coverage of all four shipped sets, as today. A host-added or
  app-registered name needs a glyph only for the active set, or an SVG. A custom icon set must cover
  every registered name, because it can be chosen as the active set.
- **Custom SVGs ignore `variant`.** One file is one fixed drawing. The warning about unsupported
  common variants skips them.
- **A custom set is a first-class set.** Its Iconify JSON is checked as the shipped sets are: every
  mapped glyph exists, and every variant-suffixed glyph exists.
- **Unknown names raise at render, loudly.** An unregistered name never renders blank, never
  falls back silently, and there is no setting to switch that off. Strictness lives in the
  startup checks as well.
- **Checks run over the merged registry, not the hard-coded name list.** They extend the existing
  `icons.E001` to `E007` and `W001`: every glyph in the active set's merged mapping exists in the
  JSON including variant forms, an override key is a registered name, a host-added name for a set
  that is not a known set is an error, a registered name with neither an active-set glyph nor an
  SVG is an error, an SVG that cannot be found, parsed or passes the safety check is an error.
  A host-added name with no glyph for a known but non-active set is not reported.
- **The merged registry is built once after apps are ready** and cached. Tests that change icon
  settings invalidate it, as the backend cache is invalidated today.
- **The app stays at `freedom_ls/icons`** here, standalone after `extract-semantic-icons-app-1-standalone-app`.
  `<c-icon>` and its arguments do not change.
- **Skill doc.** `fls-dev:icon-usage`'s configuring-icons resource documents the new settings and
  the registry call, since FLS's settings and FLS usage change in this spec.
- **Tests** follow `ds:testing`: unit tests for the registry and precedence, check tests for each
  new error, a render test per path, and the FLS settings used as the demonstrable outcome.

## Open until the spec

- The exact shape of `SEMANTIC_ICONS_SETS`: where a custom set's JSON file is named, how its
  mapping and variants are declared, and whether a set can be declared in a module instead of
  inline in settings.
- How `SEMANTIC_ICONS_SVG` locates a file: Django's static-files finders (the research
  recommendation), template directories or a settable directory. Where the parsed SVG is cached.
- Whether an own SVG is implemented as an in-memory single-variant set so one lookup path serves
  every icon, or as a separate path.
- How the literal-glyph step of `render_icon` treats a custom set, and whether a custom set's
  glyphs are reachable through an `<iconset>:<glyph>` fallback.
- The registry API's exact call shape and module name, and whether a declarative
  module-level mapping form is offered besides the call.
- Check IDs and severities for the new errors, and whether the info-level warning for a host name
  that covers the active set but not other supported sets is worth shipping.
- How the sanitising of an own SVG is done (strip width, height, class, id and metadata, as
  `django-includecontents` does) beyond the existing safety check.

## Out of scope

- The renamed settings, data bundling and the removal of the npm step (`extract-semantic-icons-app-1-standalone-app`).
- The public repo, the tag and the install into FLS and First-Class (`extract-semantic-icons-app-3-package-and-install`).
- The Claude Code plugin and the host-facing docs in the package repo (`extract-semantic-icons-app-4-claude-plugin`).
- A switch for silent unknown-name behaviour, an icon picker UI, new icon sets beyond the four, and
  changing how templates call `<c-icon>`.

## Resources

- Research: `spec_dd/1. next/extract-semantic-icons-app-2-host-icons/research_comparable_icon_packages.md`
  (comparable packages, the registry and precedence recommendation, checks);
  `spec_dd/1. next/extract-semantic-icons-app/research_coupling_audit.md` (couplings the app still carries);
  `spec_dd/1. next/extract-semantic-icons-app-1-standalone-app/research_icon_data_distribution.md`
  (how set data is stored, which a custom set must match).
- Original brief: `spec_dd/1. next/extract-semantic-icons-app/idea.md`.
- The code: `freedom_ls/icons/` (`config.py`, `checks.py`, `backend.py`, `render.py`, `loader.py`,
  `mappings.py`, `semantic_names.py`, `apps.py`).
- Skills: `fls-dev:icon-usage` (its `resources/configuring-icons.md` is updated here),
  `fls-dev:app-settings`, `ds:testing`.
