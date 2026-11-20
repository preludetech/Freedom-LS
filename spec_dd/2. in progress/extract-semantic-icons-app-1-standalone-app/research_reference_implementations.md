# Research: how reference implementations ship icon data and let hosts override the source

Scope: complements `research_icon_data_distribution.md` (which compared options a to e). This file records
what real packages do for layout, upstream version recording, licence placement, regeneration, tests and
host override settings. Evidence is thin in places: several PyPI and docs pages failed to load or omitted
the detail. Each gap is marked "not confirmed" instead of guessed.

## Findings per package

### adamchainz/heroicons (Django and Jinja tags, ships SVG as one zip)
- Layout: all SVGs live in one file, `src/heroicons/heroicons.zip`. The tags read from the zip. Tests in `tests/`.
- Regeneration: a root script `download_heroicons.py` takes a version argument, downloads
  `https://github.com/tailwindlabs/heroicons/archive/v{version}.zip` with curl, keeps only
  `optimized/**/*.svg`, strips `data-slot="icon"`, renames style folders (`20/solid` to `mini`, `16/solid` to `micro`),
  and writes the zip deflate level 9. It is a manual maintainer command, not a package console script.
- Upstream version: not recorded in any data file. The version appears only in the download URL. The package
  version in `pyproject.toml` is hardcoded (`version = "2.14.0"`, build backend `uv_build`) and tracks the
  heroicons major. Takeaway: this is the weakest point; our manifest should do better.
- Licence: the script does no licence handling. A repo-root `LICENSE` exists but its text was not shown,
  and whether it covers the Tailwind icons was not confirmed.
- Host override: none found. The README documents usage only.
- Sources: https://github.com/adamchainz/heroicons ,
  https://raw.githubusercontent.com/adamchainz/heroicons/main/download_heroicons.py ,
  https://github.com/adamchainz/heroicons/blob/main/pyproject.toml

### dj-lucide (Django, Lucide)
- Per search snippets only (the PyPI page itself did not load): ships a bundled Lucide ZIP inside the package
  by default. A management command fetches the newest icons into the host's project root without a package
  release, and a host-supplied ZIP overrides the bundled one. Setting names, version recording and licence
  placement not confirmed.
- Pattern worth noting: "bundled default, host-supplied replacement, resolved at lookup time". Same shape as
  our `SEMANTIC_ICONS_ICONIFY_DIR`, but replacement rather than icon-by-icon fallback.
- Source: https://pypi.org/project/dj-lucide/

### cotton-icons (Django Cotton, Heroicons, Tabler, Lucide, Lucide Lab)
- Bundles several sets and states exact upstream versions in the README ("Supported Icon Libraries":
  Heroicons v2.2.0, Tabler v3.37.1, Lucide v1.57.0 at time of fetch) plus a CHANGELOG.md listing renames and removals.
- Each set has an `icon_map.json` that holds deprecated Lucide aliases (a rename map shipped as data).
- Only setting: add `cotton_icons` to `INSTALLED_APPS`. No data-path override. Package licence MIT; the
  handling of bundled icon licences is not described on the page.
- Takeaway: closest in spirit to us (Cotton plus several sets); versions are documented in prose only, not
  machine checked.
- Source: https://pypi.org/project/cotton-icons/

### django-iconify (server-side Iconify API)
- Does not ship data. The host supplies the Iconify JSON collections (`@iconify/json`, manual download or
  django-yarnpkg).
- Override setting: `ICONIFY_JSON_ROOT` points at the collections directory. Optional
  `ICONIFY_COLLECTIONS_ALLOWED` and `ICONIFY_COLLECTIONS_DISALLOWED` restrict which sets are served.
- Takeaway: confirms a single "root directory of Iconify JSON" setting is the established idiom, and an
  allow-list setting is a precedent. Package licence Apache-2.0.
- Source: https://pypi.org/project/django-iconify/

### django-iconx (CSS-only icons)
- `manage.py iconx add <set>` downloads SVGs from GitHub (no npm) into `static/icons/<set>/`, one subdirectory
  per set, then generates CSS. `--version v1.7.0` pins an upstream release (and skips the GitHub API call).
  `ICONX` setting lists scanned directories (string or dict with `path`, `prefix`, `color`).
- Takeaway: data is fetched into the host project, not bundled. Per-set directory layout and explicit
  version pin on the command line.
- Source: https://oliverhaas.github.io/django-iconx/0.2.0/getting-started/icon-packages/

### djicons, django-lucide-icons, python-lucide, lucide-py (snippets only)
- djicons: a `collect` command scans templates and downloads only used icons (a subset approach, but
  at host build time). Source: https://pypi.org/project/djicons/
- django-lucide-icons: renders SVG from a directory set in settings, ships no icons (per socket.dev listing).
  Source: https://socket.dev/pypi/package/django-lucide-icons
- python-lucide: prebuilt SQLite database plus a `lucide-db` build command and a custom database path.
  Source: https://pypi.org/project/python-lucide/
- lucide-py: generates Python modules from a cloned upstream Lucide repo. Source: https://pypi.org/project/lucide-py/
- None of these detail licence placement or CI checks (not confirmed).

### zostera/django-icons
- Settings live in one `DJANGO_ICONS` dict (`ICONS`, `RENDERERS`, `DEFAULTS`), renderer given as dotted path
  or name. It ships no icon data (it emits class names for font-based sets), so it is a settings-shape
  reference only. Source: https://django-icons.readthedocs.io/en/stable/settings.html
- Note: it uses one nested dict; our spec settled on flat `SEMANTIC_ICONS_*` names, which is also the
  `django-iconify` style (`ICONIFY_JSON_ROOT`).

### Simple Icons Python packages, django-phosphor
- Searches found no Django package named django-phosphor or a Django wrapper for Simple Icons. Phosphor
  appears only through django-iconx. Nothing to learn here beyond absence.

### Iconify `@iconify/utils` (the subset tool itself)
- `getIcons(data, icons)` extracts named icons from an IconifyJSON set, described as the way to trim a set
  to the icons a project uses. Also `getIconData`, `parseIconSet`, `validateIconSet`, `quicklyValidateIconSet`,
  `mergeIconData(icon, alias)`.
- Format facts relevant to our generator: root `width`/`height` are defaults used only for icons that lack
  their own; aliases need a `parent` and may override dimensions; transforms merge. A subset
  that copies an icon's `body` but drops the root defaults would change rendered size. Our generator must
  either keep root `prefix`, `width`, `height`, or inline them per icon. If a mapping value is an alias in
  upstream, resolve it (our loader's alias handling should be checked) or copy the parent too.
- I could not confirm from the fetched page whether `getIcons` copies aliases and parents automatically
  (the docs page was brief). Verify against the source in `@iconify/utils` before relying on it. Since the
  answers file chose a Python generator, this logic is reimplemented in Python and needs its own tests.
- Sources: https://iconify.design/docs/libraries/utils/ ,
  https://iconify.design/docs/types/iconify-json.html ,
  https://github.com/iconify/iconify/tree/main/packages/utils

## Cross-cutting patterns

| Concern | What reference packages do | Implication for this spec |
|---|---|---|
| Bundled layout | One archive (heroicons, dj-lucide) or per-set directories (iconx, cotton-icons) | Per-set JSON files fit our Iconify format; no archive needed at about 0.1 MB. |
| Upstream version | heroicons: none in data; cotton-icons: README prose; iconx: CLI flag | No reference has a machine-readable manifest. Ours (version per set next to data, checked by the drift test) goes beyond them. |
| Licence | Mostly unhandled or unconfirmed | Ship the four licence texts next to the data as already settled. Nothing to copy from. |
| Regeneration | Maintainer script at repo root (heroicons) or a host-run management command (dj-lucide, iconx, djicons) | Maintainer-only script outside the app matches heroicons. A host-run refresh command is a different feature; out of scope. |
| Tests of data | Only heroicons mentions tests and 100% coverage; no reference was seen testing generated data against upstream | Our drift test is novel; keep the generator a pure function so it is testable. |
| Host override | `ICONIFY_JSON_ROOT` (django-iconify), host ZIP (dj-lucide), directory setting (django-lucide-icons, iconx) | A single directory setting is the norm. None seen does icon-by-icon fallback to a bundled copy; that is our own decision (already in answers.md). |
| Missing directory | Not documented by any reference | Our startup check error is a reasonable choice, unprecedented rather than contradicted. |

## Recommendations for the spec
- Keep the setting a single path setting with a neutral name; matches the `ICONIFY_JSON_ROOT` idiom.
- Record upstream versions in a small machine-readable manifest (for example `manifest.json` mapping set to
  npm package, version and licence id) beside the data, and have the drift test read it. No reference does so.
- Have the generator keep root `prefix`, `width` and `height` (or inline them) and copy alias parents, per the
  IconifyJSON inheritance rules above.
- Do not copy heroicons' practice of leaving the version only in the download URL.
- Gaps to verify during implementation: dj-lucide settings names and licence handling; `getIcons` alias behaviour.

status: ok
