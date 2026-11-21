# Research: where icon data comes from for a standalone icons package

## Summary and recommendation

Recommended: **a hybrid of (c) and (a), with (e) as the custom-icon escape hatch.**

1. **Default: vendor a generated subset (c).** The package ships one small JSON file per icon set. Each file is in Iconify format and holds only the icons that the package's default mappings reference. A script in the package repo generates the files from `@iconify-json/*`. A host that installs the package by git tag gets working icons with no npm step. The data is a few hundred KB in total instead of roughly 10+ MB.
2. **Host-extensible via setting (a).** An optional setting, for example `ICONS_ICONIFY_DIR`, points at a directory laid out like `node_modules/@iconify-json`. When it is set, the loader reads the full set from there first. It falls back to the vendored subset when a set or icon is missing. A host that overrides a mapping to an icon outside the subset sets this one path, typically `<BASE_DIR>/node_modules/@iconify-json`.
3. **Host SVG directory (e)** as a source for fully custom icons (brand logos, etc.), under a setting such as `ICONS_SVG_DIRS`. This is a small addition to the loader.

Reasons:
- Git-tag installs have no build step. Option (a) alone makes the package non-functional until the host runs `npm install` of four packages and sets a path. That is poor first-run friction for a public package.
- Vendoring the full sets (b) works, but the repo and every install would carry about 10 MB or more. Every upstream release would produce a large diff.
- Python packages that ship Iconify data are absent or immature (d). Nothing can be depended on.
- The system checks keep working in all three because they go through `load_iconify_data`.

Caveat on sizes: this tool environment had no shell, so file byte sizes could not be measured. The icon counts below were read from `info.json` in `node_modules/@iconify-json`. The byte sizes are estimates from the icon counts and general knowledge of these files. Measure with `du -h node_modules/@iconify-json/*/icons.json` before the spec fixes any numbers.

## Facts from the repo

- `freedom_ls/icons/loader.py` has `PACKAGE_MAP` (`heroicons`, `lucide`, `tabler`, `phosphor` -> `ph`). `iconify_json_path()` builds `BASE_DIR/node_modules/@iconify-json/<pkg>/icons.json`. `load_iconify_data()` caches the parsed JSON per set.
- `checks.py` imports `PACKAGE_MAP` and `iconify_json_path` for `check_iconify_json_exists`. The other checks (`check_mapping_values_exist`, `check_overrides_exist`) call `load_iconify_data`. Only the existence check depends on the file location. Moving the location behind one resolver function covers it.
- Installed versions and icon counts:

| Set | npm package | Version | Licence (package.json) | Icons |
|---|---|---|---|---|
| heroicons | @iconify-json/heroicons | 1.2.3 | MIT | 1288 |
| lucide | @iconify-json/lucide | 1.2.101 | ISC | 1694 |
| tabler | @iconify-json/tabler | 1.2.33 | MIT | 6092 |
| phosphor | @iconify-json/ph | 1.2.2 | MIT | 9072 |

- `mappings.py` is about 300 lines, so the default mapping references on the order of a few hundred icons in total, which is a small fraction of the roughly 18,000 available.
- Estimated byte sizes of `icons.json` (not measured): heroicons about 1 MB, lucide about 0.7 to 1 MB, tabler about 3 to 5 MB, ph about 4 to 6 MB. Total about 10 to 13 MB uncompressed, about 2 to 3 MB gzipped. A subset of roughly 300 icons would be about 50 to 150 KB in total.

## Comparison

| | a) host npm + setting | b) vendor full JSON | c) vendor generated subset | d) existing Python pkg | e) host SVG dir |
|---|---|---|---|---|---|
| Install friction, new host | High: npm install of 4 pkgs and set a path. Hosts use npm already, so moderate in practice. | None | None | Depends on a package that is unmaintained or lacks data | None |
| Host adds an icon outside the default mapping | Any icon in the installed sets | Any icon in the 4 sets | Not in the subset. Needs (a) or (e), or regenerating | Varies | Drop an `.svg` in the directory and map to it |
| System checks | Existence check is meaningful (path and files). Mapping checks work on full data. | Work unchanged. Existence check is trivial. | Work. Mapping checks run against the subset, so an override outside it fails unless (a) is configured. | Rewrite | Need a new check: file exists and parses as SVG |
| Package size | About 0 | About 10 to 13 MB | About 0.1 MB | Extra dependency | About 0 |
| Update path when sets add icons | `npm update`, nothing for the package | Re-vendor and release (large diff) | Rerun the script only when the mapping changes or when the pinned upstream version is bumped | Wait on the maintainer | Host owns the files |
| Licence notices | Host's npm install carries the notices | Ship all four licence texts in the package | Ship the four licence texts and the upstream copyright lines for the used icons | Depends | Host's responsibility |

## Details per option

### a) Host installs `@iconify-json/<set>`, a setting points at it

- Smallest package and no licence burden. The host's npm install already includes each `LICENSE` file.
- The change is mechanical: replace `Path(settings.BASE_DIR) / "node_modules" / ...` with `Path(settings.ICONS_ICONIFY_DIR) / pkg / "icons.json"`. A default of `BASE_DIR / "node_modules" / "@iconify-json"` keeps the current behaviour when `BASE_DIR` exists.
- Friction: the package is unusable on a fresh install. Install docs must list four npm packages, and CI and Docker builds must run npm before `check` or tests. Python-only deployments, such as a Docker stage without node, need an extra build stage.
- Version drift: the host's `^1.x` range can change the icon bodies and can remove icons that the mapping names. The checks catch this, but only at check time.

### b) Vendor the full `icons.json` files

- Licences are permissive (Heroicons MIT, Lucide ISC, Tabler MIT, Phosphor MIT). Redistribution requires keeping each copyright and licence notice, so ship the four licence texts, for example under `icons/data/LICENSES/`. Lucide also has portions under MIT (Feather-derived). The `@iconify-json/lucide` `LICENSE` file lists this, so copy it verbatim.
- The size cost is large and affects a git-tag install for every host. Upstream bumps (Lucide releases frequently, version 1.2.101 so far) create multi-MB diffs in the repo.
- Benefit: any icon works with no host action, and the checks are simple. This suits a package where the icon choice should be fully open to the host.

### c) Vendor only the mapped subset, generated by a script

- A script reads the mapping tables plus the package's default overrides. It writes per-set Iconify JSON containing only those icons (keep `prefix`, `width`, `height`, and `icons` with `body` and optional dimensions, and copy aliases that mappings use). It is deterministic, and a test or CI check can confirm that the vendored file matches what the script would generate from the pinned upstream version.
- Reuse of the Iconify format means the loader needs no format change, and `IconifyData` stays as it is.
- Host extension: set the (a) directory, or use (e). Without either, a host override naming a non-subset icon gets a clear check error saying which setting to configure. The error message should name the setting.
- Maintenance: bump the dev-time npm dependencies, run the script, commit the small diff. Licence notices as for (b), reduced to the icons used, but ship the full licence texts anyway.

### d) Existing Python packages

Search results (PyPI search and ecosystem pages, not exhaustive):
- `pyconify` wraps the Iconify HTTP API with a local cache. The first fetch needs network access, so it is unsuitable for offline and reproducible rendering.
- `django-iconify` reads Iconify JSON collections that the user supplies (for example from `@iconify/json`). It does not ship the data, so it is the same as option (a) with a third-party layer. I could not confirm its maintenance status because the PyPI page did not load.
- `iconify` on PyPI (0.0.103) is a Qt icon library that reads SVG directories. It is unrelated to the Iconify JSON format.
- `iconipy` and `icon-mcp` bundle some sets (Lucide and others) in their own formats, for different purposes, so they do not cover the four sets and the Iconify format.
- I found no maintained package that ships all four Iconify sets as data. Taking a dependency would add risk without removing the data problem. Not recommended.

### e) Host-supplied SVG directory

- A setting lists directories. The loader resolves a mapping value such as `custom:logo` to `<dir>/logo.svg`. It parses the SVG (extract `viewBox`, inner markup) into the same `IconEntry` shape (`body`, `width`, `height`), so the renderer is unchanged.
- This is the right route for brand and custom icons, which no Iconify set has. It is not a substitute for the default sets.
- Needs a new check: referenced file exists, parses, and contains no `<script>` or event-handler attributes if the markup is rendered unescaped. Because the host controls the files, the risk is low, but the check is cheap.
- Licence: the host's own responsibility. The package docs should say so.

## Open points for the spec

- Fix an upstream pin policy: record in the vendored file (or a manifest) the `@iconify-json` version it came from.
- Decide whether the subset script lives in the package repo (dev-only, requires npm) or in the host-facing CLI. Recommendation: package repo only.
- Decide the precedence between the (a) directory, the vendored subset, and (e) SVG directories. Suggested: an explicit custom prefix for (e), then (a) directory, then the vendored subset.
- Measure the real file sizes before quoting numbers in docs.

## References

- django-iconify and pyconify search results: https://pypi.org/project/pyconify/ and https://pypi.org/project/django-iconify/0.3
- iconify (Qt) 0.0.103: https://pypi.org/project/iconify/0.0.103
- iconipy: https://pypi.org/project/iconipy/0.2.0
- icon-mcp: https://pypi.org/project/icon-mcp/
- Local facts: `node_modules/@iconify-json/*/package.json` and `info.json`; `freedom_ls/icons/loader.py`; `freedom_ls/icons/checks.py`.
- Licence statements for the four sets are taken from the installed `package.json` files (MIT, ISC, MIT, MIT). They were not re-verified against upstream LICENSE files. Check Lucide's `LICENSE` for the extra Feather MIT notice before shipping.

status: ok
