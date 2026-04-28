# Research: Plugging Custom Icons into the Semantic Icon System

**Scope:** patterns for handling icons that are missing from the active icon set
(e.g. brand icons like `bluesky`, `github`, `slack`, `discord` when the user has
chosen `heroicons`, `lucide`, `tabler`, or `phosphor`).

**Existing state of the codebase** (`freedom_ls/icons/backend.py`):

- One `FREEDOM_LS_ICON_SET` setting picks an Iconify-format JSON bundle
  installed via `npm install @iconify-json/<set>`.
- `FREEDOM_LS_ICON_OVERRIDES` is a flat `dict[str, str]` mapping a semantic name
  to an icon name in the *same* set (no cross-set, no raw SVG).
- A regex (`<script|<foreignObject|on\w+\s*=`) sanitises every body before
  rendering. Output is wrapped in `<svg ...>{body}</svg>` with `class`,
  `aria-label`, `role="img"`, etc.

The four existing semantic mappings cover ~40 generic concepts; none cover
brands, since none of the four general-purpose sets ship brand icons.

---

## 1. Raw-SVG injection patterns in similar libraries

### `heroicons` (Python, adamchainz)
No public API for registering custom SVG. The package ships only Tailwind
Heroicons; users add their own SVGs in their own templates outside the package.
This is the simplest "punt to the user" approach but provides no consistent
rendering pipeline.
Source: <https://github.com/adamchainz/heroicons>.

### `lucide-react`
Officially supports two paths for icons not in the core set:

1. **Lucide Lab** (`@lucide/lab`) — community/experimental icons consumed
   through the same `<Icon iconNode={coconut} />` component.
2. **`createLucideIcon(name, iconNode)`** — the underlying factory that
   produces a component from an array describing SVG children. Users can
   supply their own `iconNode` literal.

Notable: lucide doesn't accept *raw SVG strings*. It accepts a structured
`iconNode` (tag name + attribute object + children) so the renderer can apply
its own `stroke`, `stroke-width`, viewBox, etc. uniformly.
Sources: <https://lucide.dev/guide/react/advanced/with-lucide-lab>,
<https://github.com/lucide-icons/lucide/blob/main/packages/lucide-react/src/createLucideIcon.ts>.

### `feather-icons`
No native custom-icon API. The maintainers' guidance is "Feather is just SVGs;
inline your own elsewhere." The library has been fork-source for lucide partly
because of this gap. Source: <https://github.com/feathericons/react-feather/issues/87>.

### `django-bootstrap-icons`
Has a `BS_ICONS_CUSTOM_PATH` setting that points at a directory of SVGs on disk;
icons in that directory are looked up by filename. Source:
<https://pypi.org/project/django-bootstrap-icons/>.

### `django-icons` (zostera)
Subclass `IconRenderer` and register it. More plumbing for a user, but very
flexible. Source: <https://github.com/zostera/django-icons>.

### Synthesis
Two distinct shapes in the wild:

- **String-keyed registry** (django-bootstrap-icons): "the file `bluesky.svg`
  in the configured directory wins."
- **Structured icon nodes** (lucide): pre-parsed AST so the renderer keeps
  control of attributes.

For our app a string-keyed registry plus the existing regex sanitiser is the
better fit — we already render Iconify `body` strings verbatim and trust them
because they come from `npm` packages we control.

---

## 2. Cross-set borrowing — does Iconify do this natively?

Yes — at the React/web-component layer Iconify uses fully prefix-qualified
names: `mdi:home`, `heroicons:check-circle`, `simple-icons:bluesky`. Any icon
component or the `<iconify-icon>` web component will load whichever set is
referenced. This is the canonical "borrow from another set" pattern in the
Iconify ecosystem. Source:
<https://iconify.design/docs/icons/>.

Our `DefaultIconBackend.render()` does *not* support this today: it loads
exactly one set (`FREEDOM_LS_ICON_SET`) and resolves the semantic name within
that set. To borrow `phosphor:bluesky` while the rest of the app uses
`heroicons` we'd need to load a *second* iconify JSON file on demand.

`load_iconify_data(set_name)` is already parameterised by set name and cached
by `_cache`, so adding cross-set lookups is mostly a lookup-key change in the
backend, not infrastructure.

**Idiomatic ergonomics:** Iconify's `prefix:name` syntax is the obvious
convention. Anyone who has used Iconify will recognise it.

---

## 3. API design for `FREEDOM_LS_ICON_OVERRIDES`

### Option A — single dict with prefix conventions (recommended)
```python
FREEDOM_LS_ICON_OVERRIDES = {
    # current behaviour: same-set rename
    "deadline": "calendar-days",
    # cross-set borrow (iconify-style prefix)
    "bluesky": "simple-icons:bluesky",
    "github":  "simple-icons:github",
    # raw SVG (file path)
    "discord": "file:icons/discord.svg",
    # raw SVG (inline literal)
    "internal_brand": "raw:<path d='M3 3h18v18H3z' fill='currentColor'/>",
}
```
Pros: one setting; one mental model; trivial to migrate (existing entries are
unchanged, no prefix == "current set"); easy to lint with a system check.
Cons: the parser has to recognise three sentinel prefixes. The literal `:`
separator is unambiguous because Iconify icon names never contain colons.

### Option B — separate dicts
```python
FREEDOM_LS_ICON_OVERRIDES        = {"deadline": "calendar-days"}
FREEDOM_LS_ICON_CROSS_SET        = {"bluesky": ("simple-icons", "bluesky")}
FREEDOM_LS_ICON_RAW_SVG          = {"internal": "<path .../>"}
FREEDOM_LS_ICON_SVG_DIR          = BASE_DIR / "icons"
```
Pros: each setting has one type; static checks are simpler; no string parsing.
Cons: four settings to remember; harder to grep "where is the bluesky icon
configured?"; ordering/precedence has to be documented.

### Option C — dataclass values
```python
FREEDOM_LS_ICON_OVERRIDES = {
    "bluesky": IconRef(set="simple-icons", name="bluesky"),
    "discord": RawSvg(body="<path .../>", width=24, height=24),
    "github":  SvgFile(path="icons/github.svg"),
}
```
Pros: maximally typed, IDE-friendly, no prefix parsing.
Cons: heavier for the user to write — they must import three classes to add
two icons. Settings files become less skim-able. Doesn't compose naturally
with environment variables / JSON config.

### Recommendation
Go with **Option A** (string-prefix convention). It's the lightest possible
extension to the current setting, mirrors Iconify's `prefix:name` everyone
already knows, and the prefix vocabulary stays small (`raw:`, `file:`, plus
any unprefixed value meaning "the current set" and any `<set>:<name>` meaning
"borrow from that set"). Add a Django system check (similar to existing
`E005`/`E006`) that validates each value at startup.

---

## 4. Where should custom SVGs live?

For a developer adding 5–10 brand icons:

| Location                    | Pros                                                              | Cons                                                                            |
| --------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Inline string in settings   | Zero extra files; obvious                                         | Settings file balloons; awful diffs; no editor SVG preview                      |
| Directory of `.svg` files   | Native dev experience; preview in IDE; fits Django staticfiles    | Must sanitise on load; needs a `FREEDOM_LS_ICON_SVG_DIR` setting                |
| Single user-authored JSON   | Reuses Iconify's own format                                       | A bit fiddly to author by hand; no preview                                      |
| Database / admin            | Editable at runtime by site admins                                | Heavy for what's almost always config; needs migrations; per-site complications |

**Recommendation:** support both **directory of `.svg` files** *and*
**`raw:<...>` inline** for tiny one-off cases, with the directory as the
recommended path. Inline is mostly there for tests and edge cases. The
directory loader can scan once at startup, run the existing
`_validate_svg_body` over each file's `<svg>` body, and cache by filename.

For developers wanting to share a custom set across projects, point them at
**option 5 below**.

---

## 5. Iconify custom icon sets — should we just lean on this?

**Yes, as a first-class third path.** Iconify's own format is a flat JSON file:

```json
{
  "prefix": "freedom-brand",
  "icons": {
    "bluesky": { "body": "<path .../>" },
    "github":  { "body": "<path .../>" }
  },
  "width": 24,
  "height": 24
}
```

Source: <https://iconify.design/docs/types/iconify-json.html>,
<https://iconify.design/docs/icons/json.html>.

Our `loader.py` already understands this format. Add a setting like:

```python
FREEDOM_LS_ICON_CUSTOM_SETS = {
    "freedom-brand": BASE_DIR / "icons" / "freedom-brand.json",
}
```

…and the backend can resolve `simple-icons:bluesky` (npm-installed) or
`freedom-brand:bluesky` (project-local JSON) through the same code path. This
gives users a clean, sharable, ecosystem-compatible way to bundle custom icons,
and keeps our backend logic uniform: there is only ever one resolver,
`(set, name) -> body`.

**Tooling bonus:** Iconify provides
[`@iconify/tools`](https://iconify.design/docs/libraries/tools/import/json.html)
which can compile a folder of SVGs into a single JSON. That's the
"production-grade" path for users with many custom icons — they author SVGs,
build to JSON, ship the JSON.

---

## 6. Brand icon options in the Iconify ecosystem

| npm package                  | Icon count | Coverage                                                                | Licence      |
| ---------------------------- | ----------:| ----------------------------------------------------------------------- | ------------ |
| `@iconify-json/simple-icons` | ~3000+     | Comprehensive monochrome brand glyphs, includes bluesky/github/slack/discord/etc. | CC0          |
| `@iconify-json/logos`        | ~1700+     | Multi-colour brand logos (full marks, not just glyphs)                  | Per-brand    |
| `@iconify-json/brandico`     | 45         | Tiny set, mostly older social brands                                    | CC BY-SA     |
| `@iconify-json/fa-brands`    | ~500       | Font Awesome brand icons (subset, monochrome)                           | CC BY 4.0    |
| `@iconify-json/mdi`          | ~7000      | Material Design Icons — includes some brand glyphs as part of MDI       | Apache 2.0   |

Sources:
<https://www.npmjs.com/package/@iconify-json/simple-icons>,
<https://www.npmjs.com/package/@iconify-json/logos>,
<https://icon-sets.iconify.design/>.

**Recommendation:** the documentation should call out **`simple-icons`** as
the obvious recommendation for brand glyphs (single colour, matches the look
of heroicons/lucide/tabler/phosphor, CC0 licence, near-universal coverage of
the brands an LMS would ever need). `logos` is the fallback for "I want the
multi-colour brand mark." `brandico` is too small to recommend. We do *not*
need to build our own brand icon set — we just need the cross-set borrow path
to work.

---

## 7. Security

### Threat surface for raw / external SVG bodies
SVG can carry XSS in several forms (sources:
<https://portswigger.net/research/svg-animate-xss-vector>,
<https://rietta.com/blog/svg-xss-injection-attacks/>,
<https://github.com/cure53/DOMPurify>):

1. `<script>` and event-handler attributes (`onload`, `onclick`, `onmouseover`,
   `onfocus`, …).
2. `<foreignObject>` containing arbitrary XHTML, including `<script>`.
3. `xlink:href` / `href` with `javascript:`, `data:text/html;...`, or
   `data:image/svg+xml;base64,...` payloads.
4. `<animate attributeName="href" to="javascript:...">` / `<set>` —
   animation-driven attribute mutation. CVE-2026-22610 (Angular) is the
   recent example.
5. CSS in `<style>` containing `expression(...)`, `url(javascript:...)`, or
   `@import` of remote stylesheets.
6. External entity references in `<!DOCTYPE>` (XXE, mostly relevant when the
   SVG is parsed server-side rather than inlined).
7. `<use href="...">` referencing external documents, which can leak data
   cross-origin or import malicious markup.

### Where our existing regex falls short
`<script|<foreignObject|on\w+\s*=` catches (1) and (2) and basic event
handlers, but **misses** (3) (`xlink:href="javascript:..."`),
(4) animation-driven attribute swaps, (5) inline `<style>` with
`url(javascript:...)`, (6) DTD trickery, and (7) external `<use>` references.

Risk in practice today is low because every `body` we render comes from the
official Iconify JSON, which is pre-cleaned by the Iconify maintainers
(<https://github.com/iconify/icon-sets>). The moment we let users supply raw
SVG, the threat model widens.

### Recommendation for raw-SVG paths
Use **bleach** with an allowlist tailored to SVG bodies. Bleach is already
common in Django apps, ships its own SVG-aware sanitiser flags
(`svg_attr_val_allows_ref`, `svg_allow_local_href`), and is
HTML5-parser-based, so we don't have to maintain a regex jungle. Source:
<https://bleach.readthedocs.io/en/latest/clean.html>.

A defensible allowlist for SVG `body` content (not full `<svg>` documents) is:

- **Tags:** `path`, `circle`, `ellipse`, `rect`, `line`, `polyline`, `polygon`,
  `g`, `defs`, `linearGradient`, `radialGradient`, `stop`, `title`, `desc`,
  `clipPath`, `mask`, `pattern`, `symbol`, `use`.
- **Attributes:** geometry attributes (`d`, `cx`, `cy`, `r`, `rx`, `ry`, `x`,
  `y`, `width`, `height`, `points`, `transform`), styling (`fill`, `stroke`,
  `stroke-width`, `stroke-linecap`, `stroke-linejoin`, `opacity`,
  `fill-rule`, `clip-rule`), structural (`id`, `class`, `viewBox`),
  presentation (`color`, `style` — *with* a CSS allowlist).
- **Block:** `<script>`, `<foreignObject>`, `<animate*>`, `<set>`, `<style>`
  containing `url(...)` with non-allowed protocols, all `on*=` handlers,
  `xlink:href`/`href` whose value is not a same-document `#fragment`, all
  external `<use href="https://...">` references, `<!DOCTYPE>`, `<!ENTITY>`.
- **Defence in depth:** add `Content-Security-Policy: default-src 'self'`
  with no `unsafe-inline` for scripts, so even a sanitiser bypass won't
  execute. (Most FLS deployments will already have this.)

### Recommendation for cross-set borrows
No additional sanitisation needed beyond our existing `_validate_svg_body`
because the source is still trusted Iconify JSON. We just need to load the
extra JSON.

### Recommendation for `simple-icons`-style installed sets
Same: trusted upstream, treat identically to the four sets we already
support.

---

## Recommended overall design

1. Keep the single `FREEDOM_LS_ICON_OVERRIDES` setting. Extend the value
   grammar:
   - `"plain-name"` — same-set override (current behaviour).
   - `"set:name"` — borrow from another *installed* iconify set.
   - `"file:relative/path.svg"` — read from `FREEDOM_LS_ICON_SVG_DIR`.
   - `"raw:<svg-body>"` — inline body literal.
2. Add `FREEDOM_LS_ICON_CUSTOM_SETS = {prefix: path_to_iconify_json}` for
   project-local sets — these participate in `set:name` lookups exactly like
   npm-installed sets.
3. Add `FREEDOM_LS_ICON_SVG_DIR` for the `file:` resolver.
4. Replace the regex sanitiser with a bleach-based SVG allowlist for any body
   that originates from `raw:` or `file:`. Trusted iconify-JSON sources keep
   the cheap path.
5. Add Django system checks (`E008`–`E010`) covering: unknown borrow-set,
   missing file, body that fails sanitiser.
6. Document `simple-icons` as the recommended brand source and `@iconify/tools`
   as the recommended way to build a project-local set when there are many
   custom icons.

This collapses every plausible "icon not in my set" use case into one
`(set_prefix, icon_name) -> svg_body` resolver and reuses Iconify's own data
format end-to-end.

---

## Reference URLs

- Iconify JSON type — <https://iconify.design/docs/types/iconify-json.html>
- Iconify custom icon sets — <https://iconify.design/docs/icons/custom.html>
- Iconify icon-sets repo — <https://github.com/iconify/icon-sets>
- Iconify import tools — <https://iconify.design/docs/libraries/tools/import/json.html>
- `@iconify-json/simple-icons` — <https://www.npmjs.com/package/@iconify-json/simple-icons>
- `@iconify-json/logos` — <https://www.npmjs.com/package/@iconify-json/logos>
- All Iconify sets browser — <https://icon-sets.iconify.design/>
- `lucide-react` createLucideIcon — <https://github.com/lucide-icons/lucide/blob/main/packages/lucide-react/src/createLucideIcon.ts>
- Lucide Lab usage — <https://lucide.dev/guide/react/advanced/with-lucide-lab>
- `heroicons` (Python) — <https://github.com/adamchainz/heroicons>
- `feather-icons` custom icon issue — <https://github.com/feathericons/react-feather/issues/87>
- `django-bootstrap-icons` — <https://pypi.org/project/django-bootstrap-icons/>
- `django-icons` (zostera) — <https://github.com/zostera/django-icons>
- DOMPurify — <https://github.com/cure53/DOMPurify>
- bleach Python sanitiser — <https://bleach.readthedocs.io/en/latest/clean.html>
- SVG XSS via animate — <https://portswigger.net/research/svg-animate-xss-vector>
- SVG XSS overview — <https://rietta.com/blog/svg-xss-injection-attacks/>
- Fortinet SVG attack-surface anatomy — <https://www.fortinet.com/blog/threat-research/scalable-vector-graphics-attack-surface-anatomy>
- Angular CVE-2026-22610 (xlink:href) — <https://github.com/angular/angular/security/advisories/GHSA-v4hv-rgfq-gp49>
