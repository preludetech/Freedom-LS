# Extract the icons app into an installable Django package

## Goal

Pull `freedom_ls/icons/` out into its own installable Python package with its own GitHub repo so it can be reused in other Django projects. Use this work to also establish a repeatable extraction pattern, captured as a Claude skill, so future apps can be extracted the same way.

## Background

The icons app currently lives at `freedom_ls/icons/` and provides:

- Semantic icon names (`success`, `next`, `topic`, …) that decouple templates from concrete icon-set names.
- Four icon sets out of the box (Heroicons, Lucide, Tabler, Phosphor) via Iconify JSON loaded from `node_modules/`.
- Pluggable backend, per-icon overrides, system checks, and a `<c-icon />` Cotton component.

Research (see `research-icon-libraries.md`) confirms this combination — semantic names + multi-set + Cotton + system checks — is genuinely novel in the Python ecosystem and worth publishing. The same research surfaces a small set of gaps that have to close before extraction is sensible.

## Scope

### 1. Close the gaps that block redistribution

These are not optional — leaving any of them in place would make the package painful (or impossible) to use outside FLS:

- **Custom icon plug-in.** The four bundled sets don't ship brand icons (e.g. bluesky, github, slack). Recommended approach (see `research-custom-icons.md`): extend the existing override setting with an Iconify-style prefix grammar:
  - `"plain-name"` — same-set rename (current behaviour).
  - `"set:name"` — borrow from another installed Iconify set.
  - `"file:rel/path.svg"` — load from a configured SVG directory.
  - `"raw:<svg-body>"` — inline literal.
  Pair with a setting for project-local Iconify-format JSON files so users can author their own sharable custom set. Document `@iconify-json/simple-icons` as the recommended brand source.
- **Drop the `BASE_DIR / node_modules` assumption.** The loader currently assumes the host project has `BASE_DIR` set and an npm pipeline. Replace with an explicit `*_DATA_DIR` setting (defaulting to today's behaviour where it works) so non-FLS-shaped projects can install the package.
- **Fix the template namespace.** `templates/cotton/icon.html` lives in the global cotton namespace and will collide with consumer projects. Move into a package-namespaced subdirectory.
- **Stronger SVG sanitisation for raw / file inputs.** The existing regex is fine for trusted Iconify JSON but misses several known SVG XSS vectors (`xlink:href="javascript:..."`, `<animate>` attribute swaps, `<style>` with `url(...)`, external `<use>`). Use a bleach-based allowlist for any `raw:` / `file:` body. Trusted Iconify-JSON sources keep the cheap path.

### 2. Make tests standalone

Tests must run in the new package with no host project, no FLS settings, no custom user model, no multi-tenancy. See `research-testing.md` for the recommended layout (top-level `tests/` directory, embedded `tests/settings.py`, fixture Iconify JSON, `pytest-django` + `tox-uv` matrix).

`test_no_font_awesome.py` walks `freedom_ls/` templates — that test is a project-level guard rail, not a property of the icons library, so it stays in FLS, not in the package.

### 3. Publish as a separate installable package

- Own GitHub repo, PyPI release, README, CHANGELOG, LICENSE, CI (test matrix + tag-triggered release via Trusted Publishing).
- See `research-packaging.md` for the recommended layout (`src/` + hatchling), classifiers, version-bump flow, and the list of host-project leaks to clean up.
- FLS becomes a consumer of the published package; the in-tree `freedom_ls/icons/` is deleted only after the new package is published, pinned, and the FLS test suite passes against it.

### 4. Build a generic Claude skill for extracting Django apps

A reusable `extract-django-app` skill in `fls-claude-plugin/skills/` so this and future extractions follow the same procedure. See `research-extract-skill.md` for the recommended shape: one `SKILL.md`, a phase-split checklist under local `resources/`, and a `file-templates/` directory of literal scaffolding templates (`pyproject.toml`, `README.md`, `tests/conftest.py`, GitHub Actions YAML, etc.).

The skill standardises grep-driven inventory, dependency classification, file scaffolding, and the host-update procedure. It explicitly defers per-app judgement (PyPI naming, license choice, version targets, vendor-data tradeoffs, breaking-API decisions) to the human — the skill prompts, never decides.

### 5. API quality improvements that ship with v1

- **Decorative / `aria-hidden` flag.** Currently every icon emits `role="img" aria-label="..."`, which is wrong for icons sitting next to text. Add a flag on the Cotton component that swaps the labelling for `aria-hidden="true"` when the icon is decorative.
- **Rotate / flip props.** `rotate` (90/180/270) and `flip` (horizontal/vertical) on the Cotton component, emitted as a `transform` attribute on the `<svg>` root. Cheap parity with Iconify HTTP-API expectations.
- **Extension point for the semantic vocabulary.** Right now consumers can't add `"shopping_cart"` without monkey-patching.
- **Caching of rendered output** (cheap, deterministic; not currently done).

## Smaller follow-on improvements (optional for v1)

These were surfaced by `research-icon-libraries.md`. Worth noting but not essential to ship a useful package:

- **Type-safe icon name surface.** `Literal[...]` over the semantic vocabulary so typos surface in the IDE, not at runtime.
- **Sprite / `<use>` delivery option.** Inline SVG bloats long pages; defer to a future major version.

Decide which of these (if any) ride along with the v1 extraction.

## Out of scope

- Jinja support.
- Multicolour recolour primitives à la the Iconify HTTP API. Monochrome icons already recolour via `currentColor`, so no work is needed there.
- An admin / picker UI for icons.
- Migrating the host project off the published package back to in-tree (one-way move).

## Open questions for the user

1. **Package & module name.** **Decided: `django-semantic-iconify`** (PyPI) / `django_semantic_iconify` (module).
2. **Settings prefix.** **Decided: rename `FREEDOM_LS_ICON_*` to `SEMANTIC_ICONIFY_*`** — breaking change accepted, no deprecation alias.
3. **Audience / version matrix.** **Decided: track FLS's own floor** — Python ≥ 3.13, Django ≥ 6.x.
4. **License.** **Deferred** — defer the decision; the plan must include a research-and-decide task before publishing. Candidates so far: BSD-3-Clause (matches Django itself, debug-toolbar, the official Django reusable-apps tutorial), MIT, Apache-2.0.
5. **Iconify JSON shipping strategy.** **Decided: host installs `@iconify-json/<set>` via npm** (current behaviour). The package README must document the install steps for each supported set, and the loader must surface a clear, actionable error message when an expected `@iconify-json/<set>` package is missing or unreadable (naming the set, the expected path, and the npm command to fix it) — not a stack trace or a silent fallback.
7. **Repo home.** **Decided: `preludetech` GitHub organisation.**

## Reference research

- `research-packaging.md` — project layout, `pyproject.toml`, MANIFEST, naming, releases.
- `research-testing.md` — standalone test harness, settings, tox-uv matrix, CI.
- `research-icon-libraries.md` — survey of prior art and where our app stands out / falls short.
- `research-custom-icons.md` — design for the missing-icon plug-in (overrides grammar, custom Iconify sets, sanitisation).
- `research-extract-skill.md` — design for the generic `extract-django-app` Claude skill.


Add:
The icons app should have its own clawed code plugin within its repo.
