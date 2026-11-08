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
| A back link above a heading | `<c-back-link href="…">Back to messages</c-back-link>`, the one style for a back link |
| A text action ("Change", "Edit", "Clear all", "Export CSV") | `<c-button variant="link">`, or `variant="secondary" size="small"` with an icon when it sits among buttons |
| A panel-framework page or component (a table, an action, a filter, the quick view, a dialog or sheet, the selection bar) | `Skill(fls-dev:panel-framework)`: it names the component for each job and how it looks |
| A destructive action | `variant="error"`, reserved for irreversible actions |
| A card or panel | `.surface`, or `<c-media-card>` for one with an image |
| A status badge | `<c-panel-status-badge tone="success\|warning\|error\|info\|muted" label="…">`, on any screen: panel-framework pages, dashboards, learner-facing views. Choose it by what the badge says, not where it sits. If it names the state of a record (Active, Stalled, Draft), it's a status badge. It wraps `c-chip`, limits the tones to the five status meanings and keeps the badge legible in forced-colours mode. A learner-facing deadline is never a badge: see Learner deadlines. |
| A label that isn't a status | `<c-chip variant="primary\|secondary\|success\|warning\|error\|info\|muted" size="xs">` for tags, levels and categories. `primary` and `secondary` live here because they carry no status meaning. The `.chip-success`, `.chip-warning`, `.chip-error` and `.chip-info` tints are the `-light` pairs. |
| A callout in a page | `<c-callout level="info\|warning\|error\|success" title="…">` |
| A page a learner cannot use (a closed or blocked course item) | A large centred `<c-icon>` (`size-12`) with the explanation as plain text under it, never a callout box |
| A callout in course content | `<c-admonition type="note\|tip\|important\|warning\|danger\|key_takeaways\|checklist">` |
| A page wrapper | `<c-page width="wide\|narrow">` |
| A progress bar | `<c-course-progress-bar>`, tinted to the course's own accent |
| A modal | `#app-modal` (the shared native `<dialog>`) opened by `<c-modal-trigger>`; it gets its scrim from `.modal-backdrop-host` |

**Headings, body text, links, lists, tables and form inputs take no classes.** The base layer already sizes and colours them: write `<h1>Title</h1>`, and the stylesheet stays the one place those styles live.

**The base layer underlines every `<a>`, and that underline means "a link inside prose".** A control (a person, a back link, a text action, a clickable row) takes the component for its job and never the prose style. On a panel-framework page every anchor is a control, and `Skill(fls-dev:panel-framework)` names the component for each and the invariant test that fails on a hand-styled one.

Where you do write utilities, keep to Tailwind's spacing scale and use `rounded-md` (`--fls-radius-md`) unless the component says otherwise. Padding, gaps, dialog footers and phone sizing are set by the panel-framework components; `Skill(fls-dev:panel-framework)` says what they do.

**A button label fits on one line, down to a 375px phone.** Keep it to a verb and a noun ("Download errors", "Upload a corrected file"). A count or a sentence goes in the heading or text beside the button, not in the label. A label wraps only when no shorter wording names the action.

**A long list inside a block scrolls in its own region.** When a block can hold more than about ten rows (an import's error rows, say), cap its height (`max-h-96 overflow-y-auto`) so the page around it stays short. Make the region focusable (`tabindex="0"`, `role="region"`, an `aria-label`) and keep the table header sticky.

**Separate outcomes get separate panels.** A result page puts what succeeded and what failed in two sibling panels, never one card holding both. The learner import result shows the "Added…" summary in one `<c-panel-card>` and the error block as its own panel beside it in the stack.

## Learner deadlines

Follow the registered design for every learner deadline surface. Never add a chip, badge, card, border or tint that the design does not draw.

- **Treatment**: a deadline is a tier-coloured `<c-icon>` and text. The tier word (and title) is bold in the tier colour; the date and any "Closes …" detail are muted beneath or beside it. It never sits in a chip, badge, bordered card or tinted box. This holds on course cards, course rows, the outline header, the outline rows and the content header.
- **Outline rows**: the date is icon plus text at the right of the row, coloured by tier, with no pill behind it.
- **Course cards and rows**: the deadline is the bottom line of the card, below the progress bar, with Details at its right.
- **Card hero**: the hero holds only the course icon. The organisation avatar overlaps the hero's bottom edge with the name beside it, below the hero. Nothing else goes inside the hero or along its bottom edge, and the avatar does not move.
- **Content header**: the deadline line above the item title has clear space above it and below it (at least `mt-6` above, `mt-3` to the title).

## Placement

A control that changes a thing sits where the thing is shown, so the person changes what they are
looking at without going somewhere else:

| Thing shown | Control beside it |
|---|---|
| A learner's Cohorts panel (Overview tab) | Add to cohort, Remove, Move |
| A learner's Courses tab | Register for a course |
| A learner's Course registrations list (Overview tab) | Deactivate / Reactivate a registration: the list is the only place an inactive registration is shown, so Reactivate has no other home |
| A cohort's Settings tab | The name field, the Staff list with Add staff member, Deactivate, Delete |
| A cohort's Learners tab | Add learners, Remove, Move |
| A learner's Settings tab | Edit name, Resend setup email, Deactivate / Reactivate: the actions with no home of their own |

A new panel or action goes next to what it changes. The Settings tab is the last resort, not the
default.

## Visual checklist

What QA checks in a screenshot of any FLS page.

- A person is linked with the avatar-and-name person link, never a bare name.
- A link that acts as a control carries no prose underline; a link inside prose does.
- A control that changes a thing sits beside the thing it changes, as the Placement table says; a
  Settings tab holds only the actions with no home of their own.
- Status badges carry one of the five status tones; a label that is not a status is a chip.
- Every button label sits on one line at 375px, 768px and 1280px.
- A block with a long list (more than about ten rows) scrolls inside a capped region; the page does not grow with the list.
- What succeeded and what failed sit in separate panels, not one card.
- A learner deadline is an icon and text: no chip, badge, border or tinted box around it on a card, row, outline header, outline row or content header.
- A course card or row shows its deadline as its last line, below the progress bar, with Details on the right.
- A course card's hero holds only the course icon; the organisation avatar straddles its bottom edge with the name beside it.
- A closed course item page shows a large centred icon with text under it, not a callout.
- The content header's deadline line has visible space above and below it.

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
