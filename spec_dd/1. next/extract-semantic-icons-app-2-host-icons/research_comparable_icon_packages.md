# Research: how comparable icon packages let the host define names and supply icons

## Recommendation (first)

Keep the current shape (closed built-in names, one mapping per set, active set picked in settings, a render backend) and add one thing the surveyed packages all have: a **host-owned registry** that is layered over the built-ins. Nothing in the package source is edited by the host.

Package-neutral settings (replacing `FREEDOM_LS_ICON_*`). Names are a proposal; use the package's own prefix, for example `SEMANTIC_ICONS`.

| Setting | Type | Replaces | Purpose |
|---|---|---|---|
| `SEMANTIC_ICONS["SET"]` | `str`, default `"heroicons"` | `FREEDOM_LS_ICON_SET` | Active Iconify set |
| `SEMANTIC_ICONS["NAMES"]` | `dict[str, dict[str, str]]`: `{new_name: {set_name: glyph}}` | none (new) | (1) Add new semantic names, with a mapping for the sets the host cares about |
| `SEMANTIC_ICONS["SVG"]` | `dict[str, str]`: `{name: "path/under/static-or-template-dir.svg"}` | none (new) | (2) Point any name (built-in or new) at the host's own SVG file |
| `SEMANTIC_ICONS["OVERRIDES"]` | `dict[str, str]`: `{existing_name: glyph}` | `FREEDOM_LS_ICON_OVERRIDES` | (3) Remap an existing name within the active set |
| `SEMANTIC_ICONS["BACKEND"]` | dotted path or `None` | `FREEDOM_LS_ICON_BACKEND` | Custom renderer (unchanged) |

(A single dict, as django-icons and djicons do, or flat `ICON_*` settings are both fine. Flat settings match the existing `AppSettings` class. The choice is cosmetic.)

Resolution order for a name at render time, first hit wins:
1. `SVG[name]` (host's own file).
2. `OVERRIDES[name]` (a glyph in the active set).
3. The set mapping from a registry layer: host `NAMES[name][active_set]`, then names registered by reusable apps, then the package built-ins for the active set.
4. Otherwise a loud failure (see validation). Never silent.

Answers to the four questions:

1. **New semantic names.** The host lists them in `NAMES` with a glyph per set. The package must not require a mapping for every built-in set. The host gives glyphs for the **active set** (plus any other set it may switch to). A name with no entry for the active set and no `SVG` entry is a system-check error. Built-in names keep full coverage of every shipped set (the existing E007 check stays, scoped to the package's own built-in tables).
2. **Own SVG.** `SVG[name]` is resolved through Django's static-files finders (django-includecontents does this, and inline_svg uses a pluggable asset finder). The SVG is parsed once at first use, cleaned of width, height and metadata, passed through the existing `_validate_svg_body` safety check, and fed to the same `build_svg` path so classes, aria and `data-icon` behave the same. Variants do not apply: a custom SVG is one fixed drawing, so `variant` is ignored for it. Document that and have the W001-style warning skip custom SVGs.
3. **Remap.** `OVERRIDES` stays as it is, except that its key may now be any registered name (built-in, host-added or app-registered), not only built-ins.
4. **Reusable apps register names.** Yes, through a registry API called at `AppConfig.ready()`, for example `semantic_icons.register({"panel_pin": {"heroicons": "map-pin", "lucide": "pin"}})`. This is the same pattern as Django's own registries (checks, admin autodiscover) and as djicons' library registration. Rules: an app may add names it owns, which are best prefixed with the app label (`panels_pin`). An app may not replace a package built-in or another app's name (that is a registration error at startup). The host always wins: host `NAMES`, `OVERRIDES` and `SVG` are layered above app registrations, so the host can restyle any app's icons without patching it. FLS-on-top-of-the-package uses the same API for its FLS-specific names, so the package stays generic (CLAUDE.md plugin rule: no FLS names in generic code). Also support a declarative form for simple cases: a module-level `SEMANTIC_ICON_NAMES`/mapping dict that the app's `ready()` passes to `register`. Avoid entry points: they give installed-package auto-registration, which hides which names exist and runs at import time, and no surveyed Django package needs them.

Validation via Django system checks (extends current `icons.E001..E007, W001`, with the registry as the source of truth instead of the hard-coded `SEMANTIC_ICON_NAMES`):
- Active set unknown / Iconify JSON missing: existing E001, E002.
- Every glyph in the **active set's merged mapping** (built-ins + apps + host `NAMES` + `OVERRIDES`) exists in the Iconify JSON, including variant-suffixed forms: existing E003, E004, E006, now applied to the merged table.
- `OVERRIDES` key is not a registered name: E005 (keys now come from the registry).
- `SVG` path not found by the finders, file unparsable or fails the dangerous-content test: new error.
- A registered name has neither an active-set glyph nor an SVG: new error (this replaces "mapping must cover everything" for non-built-ins).
- Two registrations of the same name from different apps, or an app shadowing a built-in: new error (raised at registration and also surfaced as a check so `manage.py check` shows it).
- Host `NAMES` entry for a set that is not a known set: error. Entry that is missing for a non-active known set: **no message** (optional). Optionally an info-level `Warning` when the host mapping covers the active set but not other sets the project lists as supported.
- Render time: an unregistered name raises `KeyError`-style `UnknownIconError` (django-heroicons style and the project's current "loud, never silent" rule in `IconResolutionError`). Do not copy includecontents' silent empty string at runtime. Do copy its "fail the build on missing icons" via checks.

Mapping coverage decision: **built-ins must cover every shipped set (checked in package tests and E007); host and app additions only need to cover the active set** (or supply an SVG). Requiring full coverage of all sets would force a host to research every Iconify set it will never use and would block simple adoption. The cost is that switching sets later surfaces missing glyphs as check errors at that moment, which is the right time.

Caching: keep `load_iconify_data` cached per set. Parse and sanitise `SVG` files once and cache per path in-process (inline_svg `CachedAssetFile`, django-includecontents `cache_timeout`). Build the merged registry once after `apps.ready()`; invalidate in tests on `setting_changed` (the existing `get_icon_backend.cache_clear()` pattern).

## Comparison table

| Package | Names declared | Aliases / semantic names | Custom SVGs | Unknown name | Variants | Caching |
|---|---|---|---|---|---|---|
| django-icons (zostera) | `DJANGO_ICONS["ICONS"]` settings dict: name -> string or dict (`name`, `renderer`, `attrs`, `extra_classes`, nested `content`) | Yes: `"delete": "trash"` is a semantic alias layer over the renderer's own names | Via a custom renderer registered in `RENDERERS` (name -> class path) | Not documented in fetched pages | Per-renderer (Font Awesome, Bootstrap, Material, image) | Not documented |
| django-heroicons (adamchainz) | Fixed template tags per variant, icons are bundled files | No | No (not covered) | Not documented in fetched pages (a missing file raises) | micro / mini / outline / solid tags | Not documented |
| django-tabler-icons | Bundled SVG directory; `TABLER_ICONS_DIR` setting changes directory | No | Drop files in the configured directory | Not documented | `tabler_icon_outline` / `tabler_icon_filled` tags | Not documented |
| tablericons / djicons (third-party) | `DJICONS` dict: `MODE`, `ICON_DIRS`, `MISSING_ICON_SILENT` (djicons); library registration | Not confirmed | `ICON_DIRS` (djicons) | Switchable: silent or raise (`MISSING_ICON_SILENT`) | Per library | Not documented |
| django-includecontents icons | `INCLUDECONTENTS_ICONS["icons"]` list; entries are Iconify ids or local SVG files; tuples `(alias, source)` | Yes: `('nav', 'tabler:navigation')` | Static-files finders, cleaned (strip width/height/class/id/metadata) | Runtime: empty string; build: fails on missing | Not applicable | Optional on-disk Iconify cache, `cache_timeout` |
| django-lucide / django-phosphor-icons | Could not fetch docs (404 / no results) | unknown | unknown | unknown | unknown | unknown |
| Iconify (frontend) | Icon-set JSON (`prefix`, `icons`, `aliases`, `width`, `height`) | Yes: JSON `aliases` map a name to a parent icon with optional transforms | `addCollection(json)` or `addIcon(name, data)` under a host-owned prefix, no change to the library | Component renders nothing / loads from API; no throw (from Iconify's documented behaviour, not re-fetched here) | Separate icons by name suffix, as in our `-solid`, per set | In-memory storage per prefix |
| Font Awesome kits | Hosted Kit config | Kit-level custom names for uploaded icons (Pro) | Upload to a Kit, served alongside FA icons | Not documented in fetched page | Style families | Hosted CDN |
| Rails inline_svg | Files in asset paths; helper takes a file name | No | Any file on asset path; custom `asset_file` loader (`named(filename)`) | Default: empty `<svg>` with a comment naming the file; `raise_on_file_not_found = true` raises; `svg_not_found_css_class` | Not applicable | `CachedAssetFile` preloads at boot |
| Rails icons gem (rails/icons) | Page not fetchable (404); not covered | unknown | unknown | unknown | unknown | unknown |

## Details and what we take from each

- **django-icons** is the closest to our semantic layer: a settings dict mapping host-chosen names to renderer icons, with per-name option dicts. Its weakness for us is that names are just a settings dict with no registry, so a reusable app cannot add names. We adopt the name -> mapping dict idea (`NAMES`) and add an app registry.
- **django-includecontents** shows the most useful pair of ideas: tuple aliases `(name, source)` where the source is either an Iconify id or a local SVG found through staticfiles, plus strict build-time validation with a lenient runtime. We adopt staticfiles-resolved custom SVGs and sanitising (our `_validate_svg_body` already covers the dangerous-content part), and check-time strictness, but keep render-time strict because the project's existing rule is no silent fallback in `IconResolutionError`.
- **heroicons / tabler / lucide / phosphor wrappers** are bundles with a fixed icon set and variant tags. They have no semantic layer; they confirm the host cannot extend them except by directory (`TABLER_ICONS_DIR`). Their main lesson is variants as separate entry points, which our `variants` suffix map already generalises.
- **djicons** (third-party) has the useful switch `MISSING_ICON_SILENT`, which supports making unknown-name behaviour a setting. Recommendation: do not add the switch; checks plus a loud error are enough, and an extra setting is functionality nobody asked for.
- **Iconify frontend** treats a custom icon set as data under a host-owned prefix (`addCollection`), with `aliases` in the JSON. This supports modelling a host's own SVGs as just another set (prefix `host`) in the long run, so one lookup path serves both. Option for the spec to weigh: implement `SVG[name]` as an auto-generated in-memory set with a single variant, instead of a separate code path. Simpler to reason about, but then `variant` handling must define "one variant for all".
- **Font Awesome kits** let a project upload icons served alongside the built-ins: the same "host icons live beside package icons under one name space" goal. It is a hosted service, so no mechanism to copy.
- **Rails inline_svg**: pluggable loader, preloading cache, and a choice between empty-svg and raise. Confirms the cache-once approach and shows a configurable not-found policy exists in the wild. The Rails `icons` gem page could not be fetched.

## Gaps

Docs for django-lucide, django-phosphor-icons, Rails `icons`, django-icons "missing icon" behaviour and Iconify `addCollection` pages did not load (404 or render errors). Iconify behaviour above is from general knowledge of its documented API, not verified in this session. Treat those cells as unverified.

## Reference URLs

- https://django-icons.readthedocs.io/en/latest/ and https://django-icons.readthedocs.io/en/latest/settings.html
- https://github.com/adamchainz/heroicons
- https://pypi.org/project/django-tabler-icons/
- https://pypi.org/project/djicons/ (via search result summary)
- https://smileychris.github.io/django-includecontents/3.1/icons
- https://github.com/jamesmartin/inline_svg
- https://docs.fontawesome.com/web/setup/use-kit
- https://iconify.design/docs/ (addCollection / aliases; not fetched successfully)

status: ok
