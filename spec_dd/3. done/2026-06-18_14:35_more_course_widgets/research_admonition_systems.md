# Research: Admonition / Callout Systems with Configurable Types, Icons, and Colours

Admonition and callout systems are a well-established pattern in documentation tooling (MkDocs Material, Docusaurus, Obsidian, GitHub alerts, Sphinx/Asciidoctor) and the design space is mature enough to extract clear patterns for FLS. The core insight across all systems is the same: a **type key** (string slug) maps to a **colour token** plus an **icon reference**, with a mandatory text label that does not rely on colour alone. The hard design question for FLS is not the UI rendering but the **configuration surface**: where does the type-to-(colour, icon, label) registry live, given that FLS is multi-tenant, theme-aware, and installed into other Django projects? The research below synthesises what the best existing systems do, maps it onto FLS's constraints, and makes concrete recommendations.

---

## 1. How Mature Systems Implement Custom Admonition Types

### MkDocs Material

**Declaration**: Built-in types (`note`, `tip`, `warning`, `danger`, `info`, `success`, etc.) are declared in the theme. Custom types require no Python or YAML config entry — you simply use `!!! my-type "Title"` in Markdown, and the rendering engine passes the type name as a CSS class. The custom type only becomes _styled_ by adding CSS.

**Icon and colour attachment**: Purely CSS-driven. Two rules per custom type are needed: (1) a `border-color` and `background-color` rule on `.md-typeset .admonition.my-type`, and (2) a `mask-image` rule on `.md-typeset .my-type > .admonition-title::before` pointing to an inline SVG via a CSS custom property (`--md-admonition-icon--my-type: url('data:image/svg+xml,...')`).

**Extensibility for non-developers**: Moderate. Requires basic CSS; SVG icon sourcing is the hardest part. No Python or YAML config needed for the type itself. Highly accessible once the CSS snippet is established.

**Fallback**: If a type has no CSS, the admonition renders without colour or icon — structural HTML is always emitted, just unstyled. There is no enforced default fallback at the engine level.

### Docusaurus

**Declaration**: Custom types are registered as strings in `docusaurus.config.js` under `docs.admonitions.keywords`. A React component file at `src/theme/Admonition/Types.js` maps each keyword to a full React component.

**Icon and colour attachment**: Per React component — full component freedom (inline styles, CSS modules, etc.).

**Extensibility for non-developers**: Low. Requires React knowledge and a code deploy. Not practical for domain-expert course authors.

**Fallback**: Undeclared keywords render as literal text without the admonition chrome, or throw a build-time warning.

### Obsidian Callouts

**Declaration**: Any string in `[!my-type]` is a valid callout type — no registration needed. Custom styling is provided via CSS snippets targeting `data-callout="my-type"`.

**Icon and colour attachment**:
```css
.callout[data-callout="regulation"] {
  --callout-color: 220, 38, 38;   /* RGB triplet, not hex */
  --callout-icon: lucide-scale;
}
```
Icon references a Lucide icon ID or inline SVG.

**Extensibility for non-developers**: Good if using CSS snippets. The `data-callout` attribute approach is elegant — the type name is the selector, so adding a type requires only a CSS snippet, not code.

**Fallback**: Unrecognised types fall back to the `note` type defaults (colour and icon), not a broken render. This is the best behaviour in any system surveyed.

### GitHub / GitLab Alerts

**Declaration**: Fixed set of 5 types: `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`. No custom types supported in GFM. GitLab extends slightly.

**Icon and colour**: Hardcoded per platform.

**Extensibility**: None. Closed system.

**Takeaway for FLS**: This is the anti-pattern to avoid — a fixed enum baked into the renderer.

### reStructuredText / Sphinx

**Built-in types**: `note`, `tip`, `warning`, `danger`, `important`, `hint`, `caution`. Also a generic `admonition` directive that accepts any title.

**Custom types**: Sphinx-Immaterial theme formalises this via `sphinx_immaterial_custom_admonitions` config — a list of dicts with `name`, `icon` (SVG path), and `color`. This generates both the custom directive and its CSS in one step. Other themes use pure CSS class targeting.

**Extensibility**: The Sphinx-Immaterial `config dict → CSS + directive` pattern is the closest equivalent to a data-driven registry.

### Asciidoctor

**Built-in types**: `NOTE`, `TIP`, `WARNING`, `CAUTION`, `IMPORTANT`. Custom types require a Ruby extension to register new block styles. The icon is either a FontAwesome icon name or an image path configured in the theme YAML.

**Extensibility**: Requires Ruby code for genuinely new types. Config-driven for icon/colour of existing types.

---

## 2. Patterns for Mapping Type → (Icon, Colour, Default Fallback)

Three patterns exist in the wild:

### Pattern A: CSS class convention
The type name becomes a CSS class. Styling (colour, icon) is fully in CSS. Used by MkDocs Material and Obsidian.

**Pros**: Zero Python/backend code per new type. Theme switching just swaps the CSS. Types can be added by anyone who can edit CSS.

**Cons**: No single source of truth for "what types exist". Label text in the DOM requires the template or HTML to know the type-to-label mapping. The icon must be embedded as a CSS mask or data-URI — not compatible with FLS's icon abstraction (the `<c-icon>` component, which does server-side SVG injection from the active icon set). Colour validation at content-save time is impossible.

### Pattern B: Data-driven config dict / registry
A dict (settings, config file, or DB) maps `type_key → {label, icon_name, color_token}`. The template looks up the type and injects the resolved values into the HTML. Used by Sphinx-Immaterial.

**Pros**: Single source of truth. Labels are real text (no CSS content tricks). Icons use FLS's existing icon abstraction (semantic name → icon set → SVG). Colour tokens reference the FLS theme token vocabulary (`--color-warning`, `--color-info`, etc.) so they adapt to the active theme automatically. Content validation at save time can check that a used type exists in the registry. Graceful fallback is easy to implement: if a type key is not in the registry, fall back to a `default` entry.

**Cons**: Deploying a new type requires a settings change (and restart), or a DB record. Not zero-config for non-developers — but for FLS's use case (course platform admins), this is acceptable.

### Pattern C: Per-type template override
Each type maps to a separate template partial. Maximum flexibility, maximum duplication risk.

**Not recommended** for FLS — the registry approach subsumes this cleanly.

**Recommendation for FLS**: Pattern B (data-driven registry). The registry lives in Django settings (`ADMONITION_TYPES`). Each entry is a dict with keys `label`, `icon` (FLS semantic icon name), and `color_token` (FLS role token name like `"info"`, `"warning"`, or `"success"`). The Cotton template does a single dict lookup and uses the `<c-icon>` component with the resolved icon name and a Tailwind class derived from the resolved token. A `default` entry handles unknown types — the template falls back to it silently rather than rendering nothing or raising an error.

---

## 3. Making Types Configurable Per Theme and Per Site

### Options

| Approach | Where config lives | Per-theme | Per-site | DB migration required | Restart required |
|---|---|---|---|---|---|
| Django settings dict | `settings_base.py` | No (global) | No | No | Yes (code deploy) |
| Settings dict + theme override key | `settings_base.py` + theme metadata | Yes (at startup) | No | No | Yes |
| DB model (`AdmonitionType`, site-aware) | Database | Via override | Yes | Yes | No |
| Settings now, DB model later | Both | Both | Both | Only when DB layer added | Settings only |

### Recommendation

**Ship settings-first** (`ADMONITION_TYPES` dict in settings), matching the idea file's "lean" option. This is the right call because:

1. FLS is installed into other Django projects — settings is the established extension point.
2. No DB migration, no admin UI, no per-render DB query needed.
3. The registry is small and static for any given deployment.

**Theme integration**: Themes do not need to change the registry for colours to work. The registry stores a **role token name** (e.g., `"warning"`) not a hex value. The template emits Tailwind classes like `bg-warning/10`, `border-warning`, `text-warning` — these automatically pick up the active theme's `--color-warning` value. Themes that want to _add_ or _rename_ admonition types for domain branding would set `ADMONITION_TYPES` in their theme's `apps.py` ready-state or a dedicated `settings_theme.py` that the installer merges. This is a deployment concern, not a runtime one.

**Per-site customisation without a deploy**: If a genuine per-site need is confirmed (e.g., one site needs a "regulation" type and another needs "lab safety"), a DB-backed `AdmonitionType` model (site-aware, via FLS's `site_aware_models`) can be added later without breaking the settings-based path. The template resolution order would be: DB override for this site → settings registry → hardcoded `default` fallback.

**Graceful fallback**: When a `type` attribute value is not in the registry:
- Render using the `default` entry (always present, maps to `info` token + `info` icon + label "Note").
- Do not raise an exception or render nothing — silent fallback is the right behaviour for published course content.
- Content validation at save time (`content_validate`) can warn that an unregistered type was used, without blocking publish.

---

## 4. UX Patterns and Pitfalls for Admonitions

### Visual hierarchy
- Admonitions interrupt reading flow. They should be used sparingly — no more than one or two per page section.
- Splunk's style guide (industry reference) explicitly warns: "avoid overusing text callout boxes so readers don't start ignoring them." The 'boy who cried wolf' failure mode is real: if everything is highlighted, nothing is.
- A left border (as used by the existing `c-callout`) is lighter than a full-colour background box — appropriate for inline notes. A background tint is acceptable for high-severity types (`warning`, `error`).

### Accessibility (critical)
- **WCAG 1.4.1 (Use of Colour)**: Severity may never be communicated by colour alone. Every type must have a visible text label AND an icon. The icon reinforces meaning; the label is the primary semantic signal.
- **WCAG 1.4.3 / 1.4.6 (Contrast)**: Body text on the tinted background must meet 4.5:1. FLS's `--color-on-*-light` tokens (e.g., `--color-on-warning-light: #744210` on `--color-warning-light: #FFFFF0`) are designed to satisfy this — use them, not the base `--color-on-warning` white (which will fail on a near-white tint).
- **ARIA role**: Use `role="note"` on the container. This is semantically correct for supplementary course content. Do **not** use `role="alert"` (reserved for dynamic announcements) or `role="complementary"` (too broad). Pair with `aria-labelledby` pointing at the visible title element.
- **Icons**: Decorative icons get `aria-hidden="true"`. The label text carries the accessible meaning.
- **Title text**: Must be real DOM text, not a CSS `::before` pseudo-element or `content` property. Screen readers and translation tools need real text.
- **Collapsible admonitions**: If a collapsible variant is added (similar to MkDocs `???` syntax), the toggle must be keyboard-reachable, use `aria-expanded`, and the content region must have `aria-hidden` toggled accordingly.

### Title vs. no-title
- Most systems allow both. MkDocs defaults to using the type name as the title if none is given. For FLS, the `label` from the registry (e.g., "Regulation", "Best Practice") should serve as the default visible title when no explicit title attribute is passed.

### Collapsible
- Useful for "optional depth" content. The accordion widget in the same spec covers this use case. Avoid making admonitions collapsible by default — it hides important supplementary information.

---

## 5. Single Admonition Widget vs. Separate Key Takeaways and Checklist Widgets

The `idea.md` explicitly asks whether key takeaways and checklists can be admonition types or need separate widgets. The answer is nuanced:

### Key Takeaways — can be an admonition type
A "key takeaways" or "summary" box is structurally identical to any other admonition: a styled container with a label, icon, and markdown body. In MkDocs Material, an `abstract` or `summary` type is the standard pattern for this. In FLS, `<c-admonition type="key-takeaways">` with a bulleted list as body would work perfectly. The Markdown content within handles the list formatting.

**Recommendation**: Ship `key_takeaways` (or `summary`) as a named type in the default `ADMONITION_TYPES` registry, with a suitable icon (`notes` or `star` from FLS's semantic names) and a colour token (e.g., `primary`). No separate widget needed.

### Checklists — a separate widget is better
The idea file envisions checklists as Markdown task lists (`- [ ] item`) inside a styled container. An admonition could hold this content, but a checklist widget has distinct behaviour from an admonition:
- The task items may need to be interactive (checkable), which admonitions do not address.
- The visual treatment (tick boxes, progress indication) is distinct from a callout border.
- The semantic purpose is task-completion tracking, not informational supplementation.

**Recommendation**: Implement checklist as a **separate widget** (`c-checklist`). The body markdown contains standard GFM task-list syntax (`- [ ]` / `- [x]`), and the widget renders it with appropriate interactive styling. This is a distinct concern from admonition's informational role. If a static (non-interactive) checklist is the only requirement, it can be an admonition type (`type="checklist"`) as a short-term measure, with a dedicated widget following later.

### Summary
| Widget need | Approach |
|---|---|
| Note / tip / warning / important / regulation / etc. | Admonition type in registry |
| Key takeaways / summary box | Admonition type (`key_takeaways`) in registry |
| Collapsible optional-depth content | Separate accordion widget |
| Interactive checklist (checkable boxes) | Separate checklist widget |
| Static checklist (read-only ticks) | Admonition type if simple, else separate widget |

---

## Concrete Recommendations for FLS

1. **Registry in settings**: `ADMONITION_TYPES: dict[str, dict]` in `settings_base.py`. Each entry: `{"label": str, "icon": str, "color_token": str}` where `icon` is an FLS semantic icon name and `color_token` is a role name matching a `--color-<token>` in `theme.css`. Include a `"default"` key as the fallback. Seed the dict with `note`, `tip`, `important`, `warning`, `key_takeaways`, and `remember`.

2. **Template resolution**: The Cotton `c-admonition` component looks up `type` in `settings.ADMONITION_TYPES` (via a template tag or context processor), falls back to `"default"` silently if not found. It uses `<c-icon :name="icon" aria-hidden="true">` and emits the `label` as real DOM text in a `role="note"` container with `aria-labelledby`.

3. **Colour classes**: Use `bg-{token}-light`, `border-{token}`, and `text-on-{token}-light` where `{token}` is the resolved `color_token`. These classes use the FLS theme token pairs that are already designed for tinted background legibility (e.g., `bg-warning-light` + `text-on-warning-light`).

4. **Theme-per-type customisation**: Not needed at runtime — colour is fully resolved through the token system. Deploy-level theme customisation is handled by the installer overriding `ADMONITION_TYPES` in their own settings.

5. **Content validation**: Register `c-admonition` in `MARKDOWN_ALLOWED_TAGS` with `{"type", "title"}` as permitted attributes. The existing `content_validate` machinery will strip unknown attributes. Optionally extend validation to warn if `type` is not in the registry.

6. **Accessibility checklist**: `role="note"`, `aria-labelledby` on the label `<h4>` or `<p>` id, `aria-hidden="true"` on the icon, visible label text always present (defaulting to registry `label` if no `title` attribute given), contrast from `-light` / `on-*-light` token pairs.

7. **Key takeaways**: Ship as `type="key_takeaways"` admonition, not a separate widget.

8. **Do not touch `c-callout`**: It stays as the application-level alert widget (currently in `content_engine`; the idea file proposes moving it to `base`). The `c-admonition` is the new content-layer widget. Existing demo content using `c-callout` must not be migrated as part of this feature.

---

## References

- [MkDocs Material — Admonitions](https://squidfunk.github.io/mkdocs-material/reference/admonitions/)
- [Docusaurus — Admonitions](https://docusaurus.io/docs/markdown-features/admonitions)
- [Creating Custom Admonitions in Docusaurus (Stackademic)](https://blog.stackademic.com/creating-custom-admonitions-in-docusaurus-react-app-cbe00c39339b)
- [Obsidian Help — Callouts](https://obsidian.md/help/callouts)
- [Custom Callouts in Obsidian with CSS Snippets](https://www.obsidianstats.com/posts/2025-06-10-custom-callouts-in-obsidian)
- [Asciidoctor — Admonitions](https://docs.asciidoctor.org/asciidoc/latest/blocks/admonitions/)
- [Sphinx-Immaterial — Admonitions](https://sphinx-immaterial.readthedocs.io/en/latest/admonitions.html)
- [GitHub Markdown Alerts (GFM)](https://www.showmemymd.com/blog/github-callouts-guide)
- [Markdown Admonitions and Callouts — Complete Guide (MarkdownTools)](https://blog.markdowntools.com/posts/markdown-admonitions-callouts-complete-guide)
- [MDN — aria-hidden attribute](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-hidden)
- [MDN — aria-label attribute](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-label)
- [Albritton Analytics — Admonition Configuration (MkDocs Material)](https://albrittonanalytics.com/features/admonition-configuration/)

status: ok
