# FreedomLS visual system

The brand as it reaches markup. FLS is themed: every colour, face and radius reaches a template through a role token or a component, and the `default` theme maps the brand onto those tokens. Style through the token and the component, so a theme that repoints one applies everywhere. `Skill(fls-dev:frontend-styling)` owns the token mechanics (the `on-*` pairings, which roles have `*-hover`); this file owns what the brand means by them.

## Colour

### Palette

The brand names are vocabulary for talking about the design. The token column is what goes in markup: there is no `bg-midnight` or `text-ocean`.

| Name     | Hex       | Use in markup                 | Role |
|----------|-----------|-------------------------------|------|
| Midnight | `#1A2332` | `text-on-surface`             | Primary dark: headings and body text on light |
| Ocean    | `#2B6CB0` | `bg-primary` / `text-primary` | Primary blue: logo, headings, links, primary buttons |
| Chalk    | `#F7F8FA` | `bg-surface-2`                | Secondary surface: table headers, tinted panels |
| Signal   | `#D23319` | `bg-error` / `text-error`     | Warm accent: alerts, destructive actions, error text |
| Forest   | `#38A169` | `bg-success` / `text-success` | Success: progress, completion, positive CTAs |
| Sand     | `#F6E05E` | `bg-warning`                  | Warning: callouts, non-critical alerts |
| Slate    | `#4A5568` | `text-muted`                  | Secondary text, captions, icons |
| White    | `#FFFFFF` | `bg-surface`                  | Primary surface, text on dark (`text-on-primary`) |

Two brand colours have no token of their own. **Horizon** `#4A9BD9` was the hover blue; hover is now derived, so use `hover:bg-primary-hover`. The amber `accent` role `#F59E0B` is a theme addition for highlights with no brand name yet.

The theme carries more roles than this palette names (`secondary`, `info`, the `-light` status tints, `border`, `focus-ring`). `freedom_ls/themes/default/static/themes/default/theme.css` is the authoritative list.

### Contrast

Sand and Forest are background colours only: as text on a light background they fail contrast. For status text on a pale tint, use the `-light` pair. Signal is dark enough to set error text directly on white and on Chalk, and to carry white text as a button fill; a theme that repoints `--color-error` keeps both pairings at 4.5:1 (the theme contrast invariants check this).

The brand's tested text pairings (WCAG AA minimum), for checking a theme that repoints them:

| Text     | Background | Ratio  | Use for |
|----------|------------|--------|---------|
| Midnight | Chalk      | 15.7:1 | Body text (primary) |
| Slate    | Chalk      | 7.1:1  | Body text (secondary) |
| Ocean    | White      | 5.1:1  | Headings, links |
| White    | Midnight   | 15.7:1 | Inverted sections, footer |
| White    | Ocean      | 5.1:1  | Primary buttons |
| Midnight | Sand       | 10.8:1 | Warning callouts |
| Signal   | White      | 5.0:1  | Error text, field errors |
| White    | Signal     | 5.0:1  | Destructive buttons |

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

FLS already builds each of these, and the brand decisions above are encoded in them. Reach for the component or class. `ls freedom_ls/*/templates/cotton/` lists every component; this table holds the ones a brand or layout decision rides on.

| You need | Use |
|---|---|
| A button | `<c-button variant="primary\|secondary\|ghost\|link\|accent\|success\|error" size="small">`, or the `.btn .btn-<variant>` classes directly |
| A link to a person | `<c-panel-person-link name="…" user_id="…" href="…">`: avatar and name, the one way a learner or staff member is linked from a row, a card, an attention list or a dialog |
| A back link above a heading | `<c-back-link href="…">Back to messages</c-back-link>`, the one style for a back link |
| A text action ("Change", "Edit", "Clear all", "Export CSV") | `<c-button variant="link">`, or `variant="secondary" size="small"` with an icon when it sits among buttons |
| A clickable row | the row-link style, `text-on-surface no-underline`, as the `link` data-table cell and the conversation rows |
| Buttons in a table cell or card | `<c-data-table-actions>` around `<c-modal-trigger size="small">` or `<c-button size="small">`; the wrapper owns the gap |
| A dialog's buttons | `<c-modal-footer>`: Cancel in its `cancel` slot at the left, the actions in the default slot at the right, the primary last. `<c-button-group>` is for buttons outside a dialog |
| A page header | `<c-panel-page-header>`: the `badge` slot carries a state only when it differs from the default (Inactive, Pending), stats stay out when the tabs already count them, and actions that change the record live in the page's Settings tab |
| Filter and sort on a phone | the data table's toolbar: Filter opens the filter sheet (selects and grouped checklists, never a chip cloud) and Sort opens a menu of columns |
| A destructive action | `variant="error"`, reserved for irreversible actions |
| A card or panel | `.surface`, or `<c-media-card>` for one with an image |
| A status badge | `<c-panel-status-badge tone="success\|warning\|error\|info\|muted" label="…">`, on any screen: panel-framework pages, dashboards, learner-facing views. Choose it by what the badge says, not where it sits. If it names the state of a record (Active, Stalled, Missed deadline, Draft), it's a status badge. It wraps `c-chip`, limits the tones to the five status meanings and keeps the badge legible in forced-colours mode. |
| A label that isn't a status | `<c-chip variant="primary\|secondary\|success\|warning\|error\|info\|muted" size="xs">` for tags, levels and categories. `primary` and `secondary` live here because they carry no status meaning. The `.chip-success`, `.chip-warning`, `.chip-error` and `.chip-info` tints are the `-light` pairs. |
| A callout in a page | `<c-callout level="info\|warning\|error\|success" title="…">` |
| A callout in course content | `<c-admonition type="note\|tip\|important\|warning\|danger\|key_takeaways\|checklist">` |
| A page wrapper | `<c-page width="wide\|narrow">` |
| A progress bar | `<c-course-progress-bar>`, tinted to the course's own accent |
| A modal | `#app-modal` (the shared native `<dialog>`) opened by `<c-modal-trigger>`; it gets its scrim from `.modal-backdrop-host` |

**Headings, body text, links, lists, tables and form inputs take no classes.** The base layer already sizes and colours them: write `<h1>Title</h1>`, and the stylesheet stays the one place those styles live.

The base layer underlines every `<a>`, and the underline means "a link inside prose". A link that works as a control takes the component for its job: a person gets `<c-panel-person-link>`, a back link `<c-back-link>`, a text action `<c-button variant="link">`, a clickable row the row-link style. Text links and text buttons then look the same, and `test_no_control_link_is_hand_styled` in `freedom_ls/panel_framework/tests/invariants/test_templates.py` fails on a control link that still carries the prose underline or a hand-typed `text-primary`.

Where you do write utilities, keep to Tailwind's spacing scale and use `rounded-md` (`--fls-radius-md`) unless the component says otherwise. Padding, gaps, dialog footers and phone sizing follow "Controls, spacing and small screens" in `Skill(ds:frontend-styling)`; the components above already obey it.

## Example page

The base layer, the components and the active theme supply most of the styling:

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
