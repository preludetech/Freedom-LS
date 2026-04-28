# Research: Existing Python/Django Icon Libraries

Survey of prior art before extracting `freedom_ls/icons/` into a standalone package.
The goal is to learn from what is already established, not to reinvent.

Each entry lists API surface, icon picking, rendering strategy, custom-icon support,
icon-set switching, variants, accessibility, caching, strengths, and weaknesses.

---

## 1. `heroicons` (Adam Johnson)

Reference: https://github.com/adamchainz/heroicons / https://pypi.org/project/heroicons/

- **API surface.** Four template tags / Jinja functions, one per variant:
  `heroicon_outline`, `heroicon_solid`, `heroicon_mini`, `heroicon_micro`.
  Usage: `{% heroicon_outline "academic-cap" size=24 data_foo="bar" %}`.
- **Icon picking.** Raw heroicon names from heroicons.com grid. No semantic layer.
  Underscore-to-dash conversion is done for `data_*` HTML attribute names only.
- **Rendering.** Inline SVG, no wrapping.
- **Custom / brand icons.** Not supported. Locked to the bundled Heroicons set.
  A user has to fall back to a different package or hand-rolled `{% include %}` for
  a logo not in Heroicons.
- **Switching icon sets.** Not supported. Cannot use anything other than Heroicons.
- **Variants.** Four (outline, solid, mini, micro). Each is a separate template tag,
  which forces variant choice into the template name and hurts substitutability.
- **Accessibility.** Explicitly minimal: README states no default `class`, no default
  `role`, no default `aria-label`. Defers entirely to caller.
- **Caching / performance.** SVG strings are loaded from package data; not documented
  whether they are cached, but the file system reads are cheap.
- **Strengths.** Mature, popular (~120 stars), supported on Django 4.2-6.0,
  type hints, Jinja support, CLI to migrate v1->v2 names.
- **Weaknesses.** Single icon set. No semantic naming. No accessibility defaults.
  Variant baked into tag name (cannot switch variant via a setting).

---

## 2. `django-heroicons` (matix.io)

Reference: https://github.com/matix-io/django-heroicons

- **API surface.** Single tag: `{% heroicon 'chevron-right' style="solid" %}`.
- **Icon picking.** Raw Heroicons names.
- **Rendering.** Inline SVG.
- **Custom icons.** Not supported.
- **Switching icon sets.** Not supported.
- **Variants.** Two (`outline` default, `solid`) via a `style` kwarg. Better choice than
  Adam Johnson's per-variant tag pattern.
- **Accessibility.** None documented.
- **Caching.** None documented.
- **Strengths.** Simpler API than `heroicons`. Variant is a kwarg, not the tag.
- **Weaknesses.** Last meaningful release in 2020. Tiny user base. No tests of note.
  Probably unmaintained.

---

## 3. `django-icons` (Zostera)

Reference: https://github.com/zostera/django-icons / https://django-icons.readthedocs.io/

- **API surface.** Template tag: `{% icon 'edit' extra_classes='fa-2xs my-extra' %}`.
  Also a Python `icon()` function for programmatic rendering.
- **Icon picking.** **Has a real semantic layer.** Settings dict (`DJANGO_ICONS["ICONS"]`)
  maps preset names like `"edit"` to backend specifications like `"fa-solid fa-pencil"`.
  This is the closest thing in prior art to what we are doing.
- **Rendering.** Defers to a renderer class. Not inherently inline-SVG — its built-in
  renderers emit `<i class="fa-solid fa-pencil">` style markup for icon fonts. SVG is
  possible only through a custom subclass.
- **Custom / brand icons.** Add an entry to the `ICONS` setting. To support a brand mark
  not in any font, you write/extend a renderer.
- **Switching icon sets.** Pluggable `IconRenderer` subclasses (Font Awesome 4,
  Bootstrap 3, Material, Image, custom). The shipping renderers are dated.
- **Variants.** No formal variant axis. You jam variant into the underlying class string.
- **Accessibility.** Not addressed by defaults; user must pass attributes.
- **Caching.** None documented.
- **Strengths.** Solid abstraction: presets + pluggable renderer is the right shape.
  Multiple renderer backends. Python and template APIs.
- **Weaknesses.** Renderers ship for icon fonts, not modern inline-SVG sets.
  No bundled SVG renderer for Heroicons / Lucide / etc. No Cotton component.
  Variant story is weak.

---

## 4. `django-iconify` (jrief / AlekSIS)

References: https://pypi.org/project/django-iconify/, https://edugit.org/AlekSIS/libs/django-iconify

- **API surface.** Mirrors the Iconify HTTP API but in-process. Provides a URL endpoint
  that returns an SVG (or sprite) for an `iconify-prefix:name` request, plus a template
  tag. The intended client-side use is `<iconify-icon icon="mdi:home" />` powered by
  Iconify's JS framework that hits the local endpoint.
- **Icon picking.** Raw Iconify `prefix:name` (e.g. `mdi:home`, `heroicons:check`).
  Access to **200,000+ icons across 100+ sets**. No semantic layer.
- **Rendering.** Two paths: server returns inline SVG via the API, or a sprite/symbol
  endpoint returns `<symbol>` definitions referenced by `<use>`.
- **Custom / brand icons.** Add a custom Iconify JSON file or override per-icon SVG body.
- **Switching icon sets.** Trivial — every Iconify set is addressable by prefix.
- **Variants.** None at the API layer. Variants are encoded in the icon name itself
  (e.g. `heroicons:check-solid`).
- **Accessibility.** Inherited from Iconify's defaults.
- **Caching.** Loads JSON once; Django's HTTP cache headers on the API endpoint.
- **Strengths.** Massive catalog. Iconify is the most powerful upstream abstraction in
  this space. Supports both inline and sprite delivery.
- **Weaknesses.** Treats icons as a runtime API — needs a URL routed and JS to call it
  for the headline use case. No Django-template-first ergonomics. Activity on the repo
  is light. No semantic mapping.

---

## 5. `django-tabler-icons`

I could not find a maintained PyPI/GitHub package by that exact name. The closest hits:

- `tablerpy` — returns SVG file paths from an enum (`OutlineIcon.BRAND_GITHUB`).
  Archived Feb 2026 because Tabler stopped publishing release zips.
  Reference: https://github.com/tahv/tablerpy
- `cotton-icons` (below) bundles Tabler.

So Tabler's Python story today is "use Iconify or use Cotton-icons."

---

## 6. `cotton-icons` / `cotton-heroicons` (wrabit)

References: https://github.com/wrabit/cotton-icons, https://pypi.org/project/cotton-heroicons/

- **API surface.** Cotton dotted components: `<c-heroicon.check-circle />`,
  `<c-tablericon.graph variant="filled" />`, `<c-lucideicon.arrow-down />`.
  All extra attrs pass through to the SVG element.
- **Icon picking.** Raw icon names from each source set, kebab-case, encoded as the
  component name suffix. No semantic layer.
- **Rendering.** Inline SVG, generated as Cotton component templates at package build
  time (one Cotton component file per icon).
- **Custom icons.** Not supported. You can author your own Cotton component to match the
  style, but there is no plug-in slot.
- **Switching icon sets.** Choose a different prefix (`heroicon` / `tablericon` /
  `lucideicon`) at the call site. No global "set the default set" knob.
- **Variants.** Heroicons: `outline`/`solid`/`mini`/`micro`. Tabler: `outline`/`filled`.
  Lucide: none.
- **Accessibility.** Not handled.
- **Caching.** Each icon is a separate template file; Django's template caching applies.
- **Strengths.** Cotton-native ergonomics. Multi-set out of the box.
- **Weaknesses.** No semantic layer — call site has to know "Tabler calls it `home`,
  Phosphor calls it `house`." Tied to one set per call. No custom-icon plug-in. Many
  template files (one per icon) bloats the package.

---

## 7. `djc-heroicons` (django-components)

Reference: https://pypi.org/project/djc-heroicons/

- **API surface.** A registered django-components component:
  `{% component "icon" name="academic-cap" variant="solid" stroke_width=1.5 %}`.
- **Icon picking.** Raw Heroicon names.
- **Rendering.** Inline SVG.
- **Custom icons.** Not supported.
- **Switching icon sets.** Locked to Heroicons.
- **Variants.** `outline` / `solid`.
- **Accessibility.** None by default.
- **Caching.** Inherits django-components' rendering pipeline.
- **Strengths.** Type aliases (`IconName`, `VariantName`) enable IDE autocomplete and
  static analysis — first library that takes name validation seriously.
- **Weaknesses.** Tied to django-components, not Cotton. Single icon set. No custom slot.

---

## 8. `pyheroicons`

Reference: https://pypi.org/project/pyheroicons/

A framework-agnostic Python wrapper that returns SVG strings from an icon name. Useful
in Flask/FastAPI; mostly redundant if you have `heroicons[django]`.

---

## 9. `django-bootstrap-icons`

Reference: https://github.com/christianwgd/django-bootstrap-icons

- Tags: `{% bs_icon 'name' size=... color=... %}`, `{% custom_icon ... %}`,
  `{% md_icon ... %}` for Bootstrap, custom, and Material Design respectively.
- Inline SVG. Loads from CDN by default; can load from `node_modules` or a local dir.
- Built-in caching of fetched SVG bodies — only library here that documents an explicit
  cache layer for fetch results.
- Three icon sources but no unified semantic layer.
- Also offers a `custom_icon` tag that points to user SVGs in a directory — the most
  honest "drop in your own SVG" story of any library reviewed.

---

## 10. `django-local-icons` (kytta)

Reference: https://codeberg.org/kytta/django-local-icons

Mentioned in the "django icon libraries 2026" listicle. Lets you ship local SVG files or
import Iconify packs and render them via a template tag without a runtime API. Closest
philosophical sibling to our app: bundle Iconify JSON locally, render server-side. I
could not load the source (Codeberg returned 404 in this run) but the description matches
the same architectural choice we made.

---

## 11. `djangocms-icon`

Reference: https://github.com/django-cms/djangocms-icon

Django CMS plugin. Multi-pack picker (Font Awesome, Material, Bootstrap, Octicons,
Typicons, custom, SVG sprite). Configuration is heavy because it ships an editorial UI.
Useful as a reference for "how does an icon picker UI configure available sets" but not
relevant to our headless renderer.

---

## 12. Iconify itself (the upstream concept)

References: https://iconify.design/docs/, https://iconify.design/docs/api/, https://github.com/iconify/api

Worth treating as its own entry because every modern icon system either uses it or
duplicates its concepts.

- **Concept.** `prefix:name` is the universal identifier (e.g. `heroicons:check`,
  `mdi:home`). One namespace, ~200k icons, ~150 sets.
- **Format.** `@iconify-json/<set>` ships an `icons.json` with `prefix`, default `width`/
  `height`, and an `icons` map of `name -> {body, width?, height?}`. Optionally an
  `aliases` map. The `body` is everything inside `<svg>...</svg>`.
- **Variants.** Encoded in the icon name (`-solid`, `-fill`, `-bold`, `-20-solid`, etc.)
  rather than as separate sets. There is no first-class "variant" axis.
- **Rendering.** Iconify offers SVG, sprite, web component, and framework components
  (React, Vue, Svelte). Server-side, you do exactly what we do: load the JSON, look up
  body+viewBox, emit `<svg>`.
- **Transformations.** The Iconify HTTP API supports color, width/height, rotate, flip,
  and "download as data URL" via query string. Not available in any Django wrapper
  surveyed here.
- **Strengths.** Universal address space; vast catalog; a documented JSON schema.
- **Weaknesses (for our purposes).** No opinion on accessibility, no semantic layer,
  variants are stringly typed.

---

## What our app does differently

- **Semantic-first naming.** `success`, `next`, `topic` are call-site-stable. The icon
  set, the icon name within that set, and the visual style can change behind the scenes
  without touching templates. `django-icons` is the only other library with anything
  comparable, and its presets target font icons.
- **Set-agnostic abstraction with built-in equivalents.** Four sets (Heroicons, Lucide,
  Tabler, Phosphor) all expose the same semantic vocabulary, so swapping
  `FREEDOM_LS_ICON_SET` is a global re-skin. No other library reviewed lets you swap
  sets via a single setting and keep templates untouched.
- **First-class variant axis.** `variant="outline" | "solid" | "mini" | ...` is a
  parameter, normalized across sets. Most libraries either fold variant into the icon
  name or split it across multiple template tags.
- **Pluggable backend.** `FREEDOM_LS_ICON_BACKEND` lets users swap the renderer entirely.
  Closest to `django-icons`' renderer pattern, but with a single render method instead of
  a class hierarchy.
- **Override slot.** `FREEDOM_LS_ICON_OVERRIDES` lets a project re-bind one semantic name
  to a different icon-set name without forking the package.
- **System checks.** Seven checks (E001-E007 + W001) validate the configuration at startup.
  None of the surveyed libraries ship anything similar — they all fail at render time.
- **Cotton-aware out of the box.** `<c-icon name="success" />`. Most libraries are
  template-tag only; the one Cotton-native library (`cotton-icons`) is not semantic.
- **SVG sanitisation.** We block `<script>`, `<foreignObject>`, and inline event handlers
  in icon bodies. Of the surveyed libraries, none documents an XSS guard on SVG content.
  This matters once you accept user-supplied SVG (see gaps below).
- **Inline-SVG only, by design.** Forces a single rendering model. Simpler than Iconify's
  multi-mode delivery but also less flexible (see gaps).

---

## Gaps in our app revealed by this research

- **No story for arbitrary brand icons / SVG drop-ins.** This is the headline gap and
  exactly what the `idea.md` flags. `django-bootstrap-icons` (`custom_icon` tag pointing
  at a folder of SVGs), `django-iconify` (custom Iconify JSON), and `django-icons`
  (subclass a renderer) all solve this. We do not. Concretely, a "Bluesky logo" cannot
  be plumbed in without either editing the package or writing a custom backend. The
  override mechanism only re-points to existing icons in the chosen set.
- **No cross-set borrowing.** If the active set is Lucide and we want one specific
  Heroicon, there is no way to express that. `django-iconify`'s `prefix:name` model
  handles this trivially. We could allow override values like `"heroicons:check-circle"`.
- **Hard dependency on `node_modules/`.** The loader reads
  `BASE_DIR/node_modules/@iconify-json/<pkg>/icons.json`. This is fine for an FLS-shaped
  project that already has Tailwind, but as an installable package it forces every
  consumer to set up an npm pipeline. `heroicons` ships SVGs as Python package data
  with zero JS toolchain — that is the ergonomics bar to clear. Either bundle the JSON
  in the package or document a Python-only fallback.
- **Variant-name normalization is incomplete.** We expose `mini`/`micro` from Heroicons,
  `bold`/`light`/`thin` from Phosphor, and nothing comparable from Lucide. A user who
  templates `variant="mini"` and then switches to Lucide gets a runtime `ValueError`.
  Either define a canonical variant vocabulary and let sets opt out, or document
  `variant` as set-specific.
- **No size/color transformation primitives.** Iconify's API supports rotation, flip,
  recolor, and inline size — common needs (e.g. an icon mirrored for RTL). We pass a
  Tailwind `css_class` and call it done. That's pragmatic but limiting for non-Tailwind
  consumers.
- **Accessibility default is weak.** We default `aria-label` to the semantic name
  (`role="img" aria-label="success"`). Decorative icons should be `aria-hidden="true"`
  with no label. We have no way to mark an icon as decorative. Heroicons (Adam Johnson)
  side-steps this by emitting nothing; we make a different mistake by always labelling.
- **No `presentational` / `decorative` flag.** Related to above. Most icons in real
  templates are decorative, sitting next to text.
- **Caching is only of the JSON file.** Each `render()` re-runs string formatting and
  escape calls. The result of `(semantic_name, variant, css_class, aria_label)` is
  deterministic and could be `lru_cache`d. None of the surveyed libraries cache rendered
  output either, but it's cheap to add.
- **No type-safe icon name surface.** `djc-heroicons` exposes `IconName` and
  `VariantName` literal types. Our `name: str` lets a typo slip until runtime (or system
  check time). A `Literal[...]` over `SEMANTIC_ICON_NAMES` would make IDE typos visible.
- **No sprite / use-symbol delivery option.** Inline SVG bloats HTML with ~40 SVGs on a
  long topic page. Iconify and `djangocms-icon` both offer sprite output. We could
  add it as an alternate backend later — note it but do not block the v1 extraction.
- **Discoverability for end users is poor.** A consumer needs to read
  `semantic_names.py` to know what `name=` values exist. Nothing surfaces this in the
  Cotton component or `dir()`-style introspection. Consider an `icons` management command
  or an exported `available_names()` helper.
- **No docs on extending the semantic vocabulary.** `SEMANTIC_ICON_NAMES` is package-internal.
  A consumer who wants to add `"library"` and `"shopping_cart"` semantics must currently
  monkey-patch. The override mechanism only handles already-registered names. The
  package needs an "add semantic name + per-set mapping" extension point.
- **No Jinja support.** `heroicons` ships both Django and Jinja interfaces. Probably out
  of scope for v1 but worth flagging.

---

## Summary: who does what well

| Concern | Best in show |
|---|---|
| Semantic naming | `django-icons` (presets) — closest to ours |
| Multi-set with one tag | `django-iconify` (Iconify prefix:name) |
| Cotton ergonomics | `cotton-icons` |
| Custom / brand drop-ins | `django-bootstrap-icons` (`custom_icon` tag) |
| Type-safe names | `djc-heroicons` |
| Accessibility | None really. Open lane. |
| Caching | `django-bootstrap-icons` |
| Sprite delivery | `django-iconify`, `djangocms-icon` |
| Documented JSON schema | Iconify itself |

The combination we currently ship — semantic names + multi-set + Cotton component +
system checks — is genuinely novel in the Python ecosystem. The biggest gaps to close
before publishing are: custom-icon plug-in slot, decorative/presentational flag,
node_modules dependency, and cross-set borrowing.
