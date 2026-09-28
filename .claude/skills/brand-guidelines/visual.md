# FreedomLS visual system

The brand as it reaches markup. FLS is themed: every colour, face and radius reaches a template through a role token or a component, and the `default` theme maps the brand onto those tokens. Style through the token and the component, so a theme that repoints one gets it everywhere. `Skill(fls-dev:frontend-styling)` owns the token mechanics (the `on-*` pairings, which roles have `*-hover`); this file owns what the brand means by them.

## Colour

### Palette

The brand names are vocabulary for talking about the design. The token column is what goes in markup: there is no `bg-midnight` or `text-ocean`.

| Name     | Hex       | Use in markup                 | Role |
|----------|-----------|-------------------------------|------|
| Midnight | `#1A2332` | `text-on-surface`             | Primary dark: headings and body text on light |
| Ocean    | `#2B6CB0` | `bg-primary` / `text-primary` | Primary blue: logo, headings, links, primary buttons |
| Chalk    | `#F7F8FA` | `bg-surface-2`                | Secondary surface: table headers, tinted panels |
| Signal   | `#E8553D` | `bg-error` / `text-error`     | Warm accent: alerts, destructive actions |
| Forest   | `#38A169` | `bg-success` / `text-success` | Success: progress, completion, positive CTAs |
| Sand     | `#F6E05E` | `bg-warning`                  | Warning: callouts, non-critical alerts |
| Slate    | `#4A5568` | `text-muted`                  | Secondary text, captions, icons |
| White    | `#FFFFFF` | `bg-surface`                  | Primary surface, text on dark (`text-on-primary`) |

Two brand colours have no token of their own. **Horizon** `#4A9BD9` was the hover blue; hover is now derived, so use `hover:bg-primary-hover`. The amber `accent` role `#F59E0B` is a theme addition for highlights with no brand name yet.

The theme carries more roles than this palette names (`secondary`, `info`, the `-light` status tints, `border`, `focus-ring`). `freedom_ls/themes/default/static/themes/default/theme.css` is the authoritative list.

### Contrast

Sand and Forest are background colours only: as text on a light background they fail contrast. For status text on a pale tint, use the `-light` pair.

The brand's tested text pairings (WCAG AA minimum), for checking a theme that repoints them:

| Text     | Background | Ratio  | Use for |
|----------|------------|--------|---------|
| Midnight | Chalk      | 15.7:1 | Body text (primary) |
| Slate    | Chalk      | 7.1:1  | Body text (secondary) |
| Ocean    | White      | 5.1:1  | Headings, links |
| White    | Midnight   | 15.7:1 | Inverted sections, footer |
| White    | Ocean      | 5.1:1  | Primary buttons |
| Midnight | Sand       | 10.8:1 | Warning callouts |

Ratios are against the brand hexes. The `default` theme renders Chalk as `#F3F4F6`, which takes Midnight to ~14.3:1 and Slate to ~6.8:1.

## Typography

| Role                  | Brand face    | Utility |
|-----------------------|---------------|---------|
| Headings, UI, nav     | Inter (Bold / Semibold / Medium) | `font-display` |
| Body text             | Source Sans 3 (Regular / Semibold) | `font-sans`, the default |
| Code, block and inline | Source Code Pro (Regular) | `font-mono` |

These faces are the brand's intent, not what ships. `default` uses system stacks and `first_class` uses DM Sans / Outfit / IBM Plex Mono. Style with the `font-*` utilities: they resolve through the theme's `--fls-font-*` tokens, so a theme that adopts Inter gets it everywhere. Adopting the brand faces is theme work: see `docs/how tos/theme-fls.md`.

Sizes and weights for headings, prose, tables and form inputs live in the `@layer base` block of `tailwind.components.css`.

## UI principles

1. **Content first, chrome second**: foreground the learning content (rendered Markdown). Every pixel of navigation, toolbar and chrome earns its place.
2. **Obvious over clever**: navigation, progress and actions read at a glance. If it's clickable, it looks clickable. Clarity beats minimalism.
3. **Whitespace is the structure**: build hierarchy from generous, consistent spacing on Tailwind's scale. Surfaces stay flat; a shadow or border appears only where a component already carries one.
4. **Progressive disclosure**: essentials by default, detail on demand.
5. **Respect the content author**: content is authored in Markdown, and default rendering must look excellent with zero custom CSS. Honour the author's structure.

Icons are single-colour outline icons, placed through `<c-icon>`: see `Skill(fls-dev:icon-usage)`.

## Components

FLS already builds each of these, and the brand decisions above are encoded in them. Reach for the component or class; `Skill(fls-dev:frontend-styling)` has the full inventory.

| You need | Use |
|---|---|
| A button | `<c-button variant="primary\|secondary\|ghost\|link\|accent\|success\|error" size="small">`, or the `.btn .btn-<variant>` classes directly |
| A destructive action | `variant="error"`, reserved for irreversible actions |
| A card or panel | `.surface`, or `<c-media-card>` for one with an image |
| A status badge | `<c-panel-status-badge tone="success\|warning\|error\|info\|muted" label="…">`, on any screen: panel-framework pages, dashboards, learner-facing views. Choose it by what the badge says, not where it sits. If it names the state of a record (Active, Stalled, Overdue, Draft), it's a status badge. It wraps `c-chip`, limits the tones to the five status meanings and keeps the badge legible in forced-colours mode. |
| A label that isn't a status | `<c-chip variant="primary\|secondary\|success\|warning\|error\|info\|muted" size="xs">` for tags, levels and categories. `primary` and `secondary` live here because they carry no status meaning. The `.chip-success`, `.chip-warning`, `.chip-error` and `.chip-info` tints are the `-light` pairs. |
| A callout in a page | `<c-callout level="info\|warning\|error\|success" title="…">` |
| A callout in course content | `<c-admonition type="note\|tip\|important\|warning\|danger\|key_takeaways\|checklist">` |
| A page wrapper | `<c-page width="wide\|narrow">` |
| A progress bar | `<c-course-progress-bar>`, tinted to the course's own accent |
| A modal | `<c-modal>`; a native `<dialog>` gets the shared scrim from `.modal-backdrop-host` |

**Headings, body text, links, lists, tables and form inputs take no classes.** The base layer already sizes and colours them: write `<h1>Title</h1>`, and the stylesheet stays the one place those styles live.

Where you do write utilities, keep to Tailwind's spacing scale and use `rounded-md` (`--fls-radius-md`) unless the component says otherwise.

## Example page

Most of the styling comes from the base layer, the components and the active theme:

```html
{% extends "_base.html" %}

{% block content %}
    <c-page width="narrow">
        <div class="space-y-6">
            {# The base layer sizes and colours headings and prose. #}
            <h1>Page Title</h1>
            <h2>Section Heading</h2>
            <p>
                Body text. Links inside prose are already
                <a href="#">styled by the base layer</a> too.
            </p>

            <c-button href="https://github.com/…" variant="primary">
                Fork it on GitHub
            </c-button>

            <c-callout level="info" title="Note">
                FreedomLS uses Django's Sites framework for multi-tenancy.
            </c-callout>

            {# A panel, when content needs to sit apart from the page. #}
            <div class="surface space-y-2">
                <h3>Enrolment</h3>
                <p class="text-muted text-sm">Secondary text uses the muted role.</p>
                <c-panel-status-badge tone="success" label="Complete" />
            </div>
        </div>
    </c-page>
{% endblock content %}
```
