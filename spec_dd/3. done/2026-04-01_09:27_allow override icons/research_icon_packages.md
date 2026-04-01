# Research: Multi-Icon-Library Packages for Django

## Current Setup

FLS uses `django-heroicons` (by Adam Johnson) which provides template tags like `{% heroicon_outline "arrow-right" %}`. Our `<c-icon />` Cotton component wraps this, mapping semantic names (e.g. `"next"`) to Heroicon names (e.g. `"arrow-right"`) via a Python dict in `freedom_ls/base/icons.py`. The component currently hardcodes the use of Heroicon template tags in `cotton/icon.html`.

---

## 1. Multi-Icon Django Packages

### django-icons (zostera)

- **PyPI**: https://pypi.org/project/django-icons/
- **GitHub**: https://github.com/zostera/django-icons
- **Latest version**: 26.1 (January 2026), actively maintained
- **How it works**: Provides a `{% icon "name" %}` template tag with a pluggable renderer system. You configure renderers in `settings.py` via a `DJANGO_ICONS` dict with `DEFAULTS`, `RENDERERS`, and `ICONS` sections. Ships with renderers for Font Awesome, Material Icons, Bootstrap 3, and images. Custom renderers can be created by subclassing `IconRenderer`.
- **Relevance**: This is the most mature Django icon abstraction layer. It does not bundle SVG icon sets itself -- it is a rendering framework. You would still need to provide the actual icon data (via separate packages or custom renderers). It could serve as an abstraction layer but adds complexity without solving the core problem of bundling multiple SVG icon sets.

### django-svg-icons (djangomango)

- **PyPI**: https://pypi.org/project/django-svg-icons/
- **GitHub**: https://github.com/djangomango/django-svg-icons
- **How it works**: Loads icon path data from a JSON file (Iconify format) and renders SVGs via a `{% icon "name" %}` template tag. Supports `size`, `width`, `height`, and `className` kwargs. Can be populated with data exported from Iconify icon sets.
- **Relevance**: Interesting because it uses Iconify's JSON format as its data source. You could swap icon sets by changing the JSON file. However, the project appears to have low activity.

### django-local-icons (kytta)

- **Codeberg**: https://codeberg.org/kytta/django-local-icons
- **License**: BSD 3-Clause
- **How it works**: Template tags for including local SVG or Webfont icons. Includes a management command to download icons from Iconify for self-hosting. Icons are stored locally as static files.
- **Relevance**: Good approach for self-hosted Iconify icons. The management command for downloading icon packs is a useful pattern. However, the project appears to be in early stages.

### django-iconify

- **PyPI**: https://pypi.org/project/django-iconify/
- **Version**: 0.4.1
- **How it works**: An Iconify API implementation and tools for Django. Provides template tags and API access to Iconify icon sets.
- **Relevance**: Directly wraps Iconify, but low version number and unclear maintenance status.

### django-bootstrap-icons

- **PyPI**: https://pypi.org/project/django-bootstrap-icons/
- **How it works**: Template tags for Bootstrap Icons and Material Design Icons. Renders inline SVG.
- **Relevance**: Limited to two icon sets. Not a general solution.

### Single-Library Packages

These each wrap one icon set:
- `django-heroicons` (Adam Johnson) -- what we use now
- `django-lucide-icons` -- Lucide icons
- `django-remix-icon` -- Remix icons
- `django-material-icons` -- Material icons
- `django-hugeicons-stroke` -- Hugeicons

**Conclusion**: No single Django package cleanly bundles multiple high-quality SVG icon sets with a unified template tag interface. The closest is `django-icons` (zostera), but it is a rendering framework, not an icon data provider.

---

## 2. Popular Open-Source Icon Sets Comparison

| Icon Set | Icon Count | Styles/Variants | License | Notes |
|---|---|---|---|---|
| **Heroicons** | ~300 unique icons (~1,200 with variants) | Outline, Solid, Mini, Micro | MIT | Made by Tailwind Labs. Small but high quality. Our current set. |
| **Lucide** | ~1,600 | Outline only (stroke-based) | ISC (MIT-compatible) | Fork of Feather. Most popular. Very consistent style. |
| **Phosphor** | ~9,000 (across weights) | Thin, Light, Regular, Bold, Fill, Duotone | MIT | Excellent variety with 6 weights. Very flexible. |
| **Tabler Icons** | ~5,900 | Outline, Filled | MIT | Largest free outline set. Popular for dashboards/admin UIs. |
| **Bootstrap Icons** | ~2,000 | Outline, Fill | MIT | Designed for Bootstrap but usable anywhere. |
| **Feather Icons** | ~287 | Outline only | MIT | Small set, no longer actively maintained. Lucide is its successor. |
| **Material Symbols** | ~3,000+ | Outlined, Rounded, Sharp; plus variable weight/fill | Apache 2.0 | Google's icon set. Very comprehensive but complex axis system. |

**Recommendations for FLS**:
- **Heroicons** (current) -- good default for Tailwind projects, small but sufficient
- **Lucide** -- best alternative for clean outline style, very popular, actively maintained
- **Tabler Icons** -- best if large icon count is needed
- **Phosphor** -- best if multiple weights/styles per icon are needed

All four are MIT (or MIT-compatible) licensed and have consistent, professional design.

---

## 3. Iconify as a Meta-Solution

**Iconify** (https://iconify.design/) is a unified framework providing access to 200+ icon sets and 200,000+ icons through a single API.

### How It Works

- Each icon is identified as `prefix:name` (e.g. `mdi:home`, `heroicons:arrow-right`, `lucide:check`)
- Icon data is available as JSON packages (`@iconify/json` for all sets, or `@iconify-json/lucide` etc. for individual sets)
- Multiple consumption methods: CDN API, self-hosted API, build-time generation, or direct JSON parsing

### Django Integration Options

#### Option A: CDN (runtime)
Include `<script src="https://code.iconify.design/3/3.1.0/iconify.min.js">` and use `<span class="iconify" data-icon="lucide:check"></span>`. Icons are fetched from Iconify's public API at runtime.

- **Pros**: Zero build step, instant access to all icon sets
- **Cons**: External dependency, requires internet, slight FOUC, not true inline SVG

#### Option B: Self-Hosted API Server
Run the Iconify API as a Node.js service (Docker available: `iconify/api`). Serves icon data on demand.

- **Pros**: No external dependency, full control
- **Cons**: Extra infrastructure (Node.js server), still runtime fetching
- **GitHub**: https://github.com/iconify/api

#### Option C: Build-Time Generation (recommended approach for Django)
Install `@iconify-json/<set>` npm packages. At build time (e.g. during Tailwind build), extract SVG data and write to files that Django templates can include.

A detailed approach is described at: https://enzircle.com/enhancing-your-django-apps-inline-svg-icons-with-iconify-and-tailwind

This uses `addDynamicIconSelectors` in `tailwind.config.js` to scan templates, find icon identifiers, and generate SVG files. Templates then use `{% include "icons/icon-[mdi-light--home]" %}`.

- **Pros**: No runtime dependency, true inline SVG, works with any icon set
- **Cons**: Requires npm build step (we already have one for Tailwind), more complex pipeline

#### Option D: Python JSON Parsing
The `@iconify/json` npm package (or individual `@iconify-json/*` packages) contain JSON files with all icon SVG path data. A Django template tag or management command could parse these JSON files and render SVGs directly.

The `pyconify` package (https://pypi.org/project/pyconify/) provides Python bindings for Iconify data.

- **Pros**: Pure Python, no JavaScript runtime needed, offline
- **Cons**: Need to handle SVG rendering yourself

### Iconify Verdict

Iconify is powerful but adds complexity. It is most useful if we want to support arbitrary icon sets chosen by downstream projects. The JSON data format is well-structured and could be parsed by a custom Django template tag.

---

## 4. SVG Sprite Approaches

### How SVG Sprites Work

All icons are combined into a single SVG file using `<symbol>` elements. Individual icons are referenced via `<use href="#icon-name">`. This reduces HTTP requests and allows caching.

### Django Tooling

- **Build-time with npm scripts**: Use `svg-sprite` or `svgo` npm packages to combine individual SVG files into a sprite sheet. Add as a step in the existing npm/Tailwind build pipeline.
- **Gulp/Grunt workflows**: A Gist by krzysztofjeziorny shows a Gulp workflow for building SVG sprites and placing symbols in Django templates: https://gist.github.com/krzysztofjeziorny/d5fd454fe33d5067a7fbe5d5704d8d20
- **django-svg-icons**: Can load from a JSON file that acts similarly to a sprite definition.
- **Manual approach**: Store individual SVG files in a templates directory and use `{% include %}`. Simple but no sprite optimization.

### Django + Cotton Considerations

For our Cotton component setup, sprites have a complication: the `<use href="#icon-name">` approach requires the sprite SVG to be present in the DOM (or referenced via an external file). This interacts awkwardly with HTMX partial page loads. Inline SVG (where the full SVG markup is rendered into the HTML) is more reliable with HTMX.

---

## 5. Practical Recommendations for FLS

Given the current architecture (semantic name registry in Python, Cotton `<c-icon />` component, Tailwind + HTMX stack), the most practical approaches ranked:

### Approach A: Multiple Django Icon Packages (Simplest)

Install 3-4 single-library Django packages alongside `django-heroicons`:
- `django-heroicons` (current)
- `django-lucide-icons`
- A Tabler or Phosphor package (if one exists with template tags)

Add a Django setting like `FLS_ICON_LIBRARY = "heroicons"` and update `cotton/icon.html` to dispatch to the right template tag based on the setting. Each icon set would need its own name mapping in `icons.py`.

**Pros**: Simple, no build step changes, each package is well-tested
**Cons**: Multiple packages to maintain, mapping tables needed per icon set, limited to sets that have Django packages

### Approach B: Iconify JSON + Custom Template Tag (Most Flexible)

Install `@iconify-json/<set>` npm packages for desired icon sets. Write a custom Django template tag that reads the Iconify JSON files and renders inline SVG. The semantic name registry maps to `prefix:icon-name` pairs.

**Pros**: Access to 200+ icon sets, single rendering mechanism, offline, true inline SVG
**Cons**: More upfront work to build the template tag, npm dependency for icon data

### Approach C: Build-Time SVG File Generation (Hybrid)

During the Tailwind build step, extract needed icons from Iconify JSON packages into individual SVG template files. The Cotton component uses `{% include %}` to render them.

**Pros**: No runtime overhead, works with any icon set, simple template includes
**Cons**: Build step complexity, generated files in templates directory

### Summary Table

| Approach | Flexibility | Complexity | Build Step Changes | Offline |
|---|---|---|---|---|
| A: Multiple Django pkgs | Low (3-4 sets) | Low | None | Yes |
| B: Iconify JSON + tag | High (200+ sets) | Medium | npm install only | Yes |
| C: Build-time generation | High (200+ sets) | Medium-High | Yes | Yes |

---

## References

- [django-icons (zostera)](https://github.com/zostera/django-icons)
- [django-icons on PyPI](https://pypi.org/project/django-icons/)
- [django-svg-icons](https://github.com/djangomango/django-svg-icons)
- [django-local-icons](https://codeberg.org/kytta/django-local-icons)
- [django-iconify on PyPI](https://pypi.org/project/django-iconify/)
- [django-heroicons](https://github.com/adamchainz/heroicons)
- [django-lucide-icons on PyPI](https://pypi.org/project/django-lucide-icons/)
- [Iconify Design](https://iconify.design/)
- [Iconify API (self-hosted)](https://github.com/iconify/api)
- [Iconify API Documentation](https://iconify.design/docs/api/)
- [Iconify Hosting Guide](https://iconify.design/docs/api/hosting.html)
- [pyconify on PyPI](https://pypi.org/project/pyconify/)
- [Inline SVG Icons with Iconify and Tailwind in Django (Enzircle)](https://enzircle.com/enhancing-your-django-apps-inline-svg-icons-with-iconify-and-tailwind)
- [Lucide Icons](https://lucide.dev/)
- [Lucide Comparison Page](https://lucide.dev/guide/comparison)
- [Phosphor Icons](https://phosphoricons.com/)
- [Tabler Icons](https://tabler.io/icons)
- [Bootstrap Icons](https://icons.getbootstrap.com/)
- [Heroicons](https://heroicons.com/)
- [Feather Icons](https://feathericons.com/)
- [Best Django Icon Libraries for 2026 (Hugeicons)](https://hugeicons.com/blog/development/best-django-icon-libraries)
- [SVG Sprite Gulp Workflow for Django (Gist)](https://gist.github.com/krzysztofjeziorny/d5fd454fe33d5067a7fbe5d5704d8d20)
