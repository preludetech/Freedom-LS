# FreedomLS visual system

The brand as it reaches markup. FLS is themed: every colour, face and radius reaches a template through a role token or a component, and the `default` theme maps the brand onto those tokens. Style through the token and the component, so a theme that repoints one applies everywhere. `Skill(fls-dev:frontend-styling)` owns the token mechanics (the `on-*` pairings, which roles have `*-hover`); this file owns what the brand means by them.

Every rule here holds on every FLS page. A feature's own layout, its component's props and the spacing on one screen live in that feature's spec, its component's doc comment and `docs/product/`.

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
3. **Whitespace is the structure**: build hierarchy from generous, consistent spacing on Tailwind's scale. Space separates things. Surfaces stay flat; a shadow, border or rule appears only where it does a job (the edge of a card or dialog, a sticky dialog header or footer, a table's header row) and where a component already carries it. Siblings that space can separate get space: no box around each item in a group, no box inside a box, and no rule between list items except in a component built as a ruled list of records. A background fill draws a box as surely as a border does, so a group of figures or stats inside a card stands as plain figures in columns, with no border and no fill on each.
4. **Things line up**: content shares edges. Blocks start and stop on their container's padding, a button lines up with the text above it, and items of one kind sit in one column so they read down the page.
5. **Progressive disclosure**: essentials by default, detail on demand.
6. **One kind of thing, one look**: a new section is drawn with the components its neighbours already use. A list of course content (parts and topics) uses the course outline rows (`learner_interface/partials/course_minimal_toc.html#course-children`) wherever it appears: the player sidebar, a full page, the public course page. A heading matches the size and style of its sibling headings, and content that belongs inside a section is a sub-section of it under an eyebrow heading, not a new peer heading. A feature brings no list, link or heading style of its own.
7. **Respect the content author**: content is authored in Markdown, and default rendering must look excellent with zero custom CSS. Honour the author's structure.

Icons are single-colour outline icons, placed through `<c-icon>`: see `Skill(fls-dev:icon-usage)`.

## Components

FLS already builds each of these, and the brand decisions above are encoded in them. Reach for the component or class. `ls freedom_ls/*/templates/cotton/` lists every component; this table holds the ones a brand or layout decision rides on.

| You need | Use |
|---|---|
| A button | `<c-button variant="primary\|secondary\|ghost\|link\|accent\|success\|error" size="small">`, or the `.btn .btn-<variant>` classes directly |
| A back link | `<c-back-link href="…">Back to messages</c-back-link>`, the one style for a back link. It is the first thing on the page, at the top left above the heading. A page a person opens from another page has one. Going back is a link, never a `<c-button>`, and the page's action row holds actions only. `learner_interface/course_detail.html` is the model, with `historyBackLink` returning the person to the page they came from |
| A text action ("Change", "Edit", "Clear all", "Export CSV") | `<c-button variant="link">`, or `variant="secondary" size="small"` with an icon when it sits among buttons |
| A panel-framework page or component (a table, an action, a filter, the quick view, a dialog or sheet, the selection bar) | `Skill(fls-dev:panel-framework)`: it names the component for each job and how it looks |
| A destructive action | `variant="error"`, reserved for irreversible actions. The button that opens the confirm dialog is `variant="error"` too, the same red as the dialog's confirm button |
| A card or panel | `.surface`, or `<c-media-card>` for one with an image |
| A status badge | `<c-panel-status-badge tone="success\|warning\|error\|info\|muted" label="…">`, on any screen: panel-framework pages, dashboards, learner-facing views. Choose it by what the badge says, not where it sits. If it names the state of a record (Active, Stalled, Draft), it's a status badge. It wraps `c-chip`, limits the tones to the five status meanings and keeps the badge legible in forced-colours mode. |
| A label that isn't a status | `<c-chip variant="primary\|secondary\|success\|warning\|error\|info\|muted" size="xs">` for tags, levels and categories. `primary` and `secondary` live here because they carry no status meaning. The `.chip-success`, `.chip-warning`, `.chip-error` and `.chip-info` tints are the `-light` pairs. |
| A callout on a page outside the panel framework | `<c-callout tone="info\|warning\|error\|success" title="…">`. On a panel-framework page (a panel, dialog, sheet or quick view) it is `<c-panel-callout>`, as `Skill(fls-dev:panel-framework)` says |
| A page a person cannot use (closed or blocked) | A large centred `<c-icon>` (`size-12`) with the explanation as plain text under it, never a callout box |
| A callout in course content (`c-admonition` is for course content only; everywhere else use `c-callout`) | `<c-admonition type="note\|tip\|important\|warning\|danger\|key_takeaways\|checklist">`. The admonition look belongs to course content too: an app template never hand-builds a box with a thick coloured start border (`border-s-4`, `border-l-4`) and a tint. Content that is not a notice, such as a learner's answer, sits in a plain box with a 1px border |
| A page wrapper | `<c-page width="wide\|narrow">` |
| A date or a date-time | `<c-date :value="…" />` / `<c-datetime :value="…" />`; a deadline in the learner's own zone is `{% local_time %}`. `voice.md` says how dates read |
| A learner deadline, time limit, close date or access date ("Deadline", "Missed deadline", "Closes", "Closed", "Access ends", "Access ended") | `<c-deadline-label tier="…" layout="inline\|stacked\|minimal">`, the one style for any deadline a learner sees: coloured icon, bold tier word, date in `text-muted font-mono`. Each date is its own label, a separate element under the one before it, never text inside another label's slot. Lines in the same block share one layout; none is plain text |
| A progress bar | `<c-course-progress-bar>`, tinted to the course's own accent |
| A modal | `#app-modal` (the shared native `<dialog>`) opened by `<c-modal-trigger>`; it gets its scrim from `.modal-backdrop-host` |

**Headings, body text, links, lists, tables and form inputs take no classes.** The base layer already sizes and colours them: write `<h1>Title</h1>`, and the stylesheet stays the one place those styles live.

**No underline on a link outside a sentence.** The base layer underlines every `<a>`, and that underline means "a link inside prose": words in the middle of a sentence in a paragraph. Every other link is a control: a person, a back link, a text action, a clickable row, and a record's name in a table cell, a definition-list value, a card or a list. A control takes the component for its job and never the prose style. A record's name with no component of its own takes `class="font-semibold text-primary no-underline hover:text-primary-hover"`, the back link's look. A bare `<a href>` with no `class` is a forgotten control unless a sentence surrounds it. An invariant test finds them: `template_rules.anchors_without_classes` (`freedom_ls/panel_framework/tests/invariants/template_rules.py`) in an app whose tests may import `panel_framework`, and `freedom_ls/course_applications/tests/invariants/test_template_rules.py` as the model for an app whose tests may not. On a panel-framework page every anchor is a control, and `Skill(fls-dev:panel-framework)` names the component for each and the invariant test that fails on a hand-styled one.

Where you do write utilities, keep to Tailwind's spacing scale and use `rounded-md` (`--fls-radius-md`) unless the component says otherwise. Padding, gaps, dialog footers and phone sizing are set by the panel-framework components; `Skill(fls-dev:panel-framework)` says what they do.

**Buttons of one size are one height.** A variant changes a button's colour and outline, never its box: the secondary button's outline is drawn inside its box, so it sits level with a primary or error button beside it. This holds on every page, learner pages included.

**A button shows its focus ring on keyboard focus only.** `.btn` draws the ring under `focus-visible`, never `focus`, so a button looks the same after a mouse click or tap as before it. A toggle that swaps its label ("Show transcript" / "Hide transcript") keeps one look in both states.

**An icon-only button centres its icon.** The icon sits at the button's optical centre: wrap it in a block-level box (`flex`, not a bare inline `<span>`), so no text baseline pushes it down. A play triangle, whose visual weight sits left of its box, moves right by a pixel or two (`translate-x-px`).

**A callout has room inside it.** `<c-callout>` keeps its icon, title, text and buttons well clear of its border, and puts space between the title, each paragraph and the button row. The `.callout` class sets this spacing for every callout; add no extra padding at the call site.

**A list inside a callout lines its bullets up with the callout's title.** Each bullet or number sits at the left edge of the text column, under the title's first letter, with no extra indent. `<c-callout>` sets this for any `<ul>` or `<ol>` in its slot; write a bare list at the call site, with no list or margin classes.

**A form error that belongs to no single field is an error callout.** A failed login, a rejected submission or any `form.non_field_errors` message shows in an error callout above the form: `<c-callout tone="error">` outside the panel framework, `<c-panel-callout tone="error">` in a panel-framework template. A field's own error stays as text beside that field.

**A marked answer option is tinted with its result.** Once a question is marked, the correct option takes `border-success bg-success/10` and a wrong pick takes `border-error bg-error/10`, each with its icon at the end of the row. An option that is neither stays neutral. The tint carries the result together with the icon and its text, never the icon alone.

**A result and its explanation sit in a callout.** Feedback on something the person just did ("Correct", "Not quite", why an answer is right) goes in `<c-callout>` with the tone of the result: the result as the title, the explanation as the text. It is never a bare heading with a paragraph under it.

**A button label fits on one line, down to a 375px phone.** Keep it to a verb and a noun ("Download errors", "Upload a corrected file"). A count or a sentence goes in the heading or text beside the button, not in the label. A label wraps only when no shorter wording names the action.

**A long list inside a block scrolls in its own region.** When a block can hold more than about ten rows (an import's error rows, say), cap its height (`max-h-96 overflow-y-auto`) so the page around it stays short. Make the region focusable (`tabindex="0"`, `role="region"`, an `aria-label`) and keep the table header sticky.

**An expand chevron shows whether its control is open.** A menu button, a `<details>` disclosure, a filter chip and an accordion end in `<c-icon name="dropdown">`, which points down while closed and turns up (`rotate-180`) while open: `group-open:rotate-180` under a `<details class="group">`, `group-aria-expanded:rotate-180` under a trigger with `aria-expanded`, and `group-aria-expanded/menu:rotate-180` in a `<c-dropdown-menu>` trigger, which is a `group/menu`.

**The navigation is a left column from 1024px up.** The interface shells (`_base_interface.html`) dock the navigation `<dialog>` beside the content as the grid's first column at `lg` and wider; below `lg` it is a sheet opened from the page heading's toggle. A page where the navigation is drawn above the content, spans the page width or is missing at a desktop width is a broken shell. It is never the page's look, whatever a sibling page or an earlier screenshot shows. With JavaScript off the navigation still shows, by CSS alone: docked as the left column at `lg` and wider, a block above the content below that.

**Separate outcomes get separate panels.** A result page puts what succeeded and what failed in two sibling panels, never one card holding both. The learner import result shows the "Added…" summary in one `<c-panel-card>` and the error block as its own panel beside it in the stack.

## Placement

A control that changes a thing sits where the thing is shown, so the person changes what they are
looking at without going somewhere else. A new panel or action goes next to what it changes. A
Settings tab is the last resort, for actions with no home of their own.

The cohort Settings tab is the Name, Staff and Status panels. The learner Settings tab is the Name
and Account panels. On the Staff table, Add role sits in the Staff member actions column, beside the
person it gives a role to; the per-role actions sit in the Role actions column.

A link on a row or card opens the page of the record that row or card shows. A row for an
application has a "Details" link to the application, and the course it is for is one click further
on. When two records could claim the link, the one named in the list's heading wins.

A row or card in a list ends in one control: the link to its record ("Details"). Every list on a
page ends its rows the same way, so an application row ends like a course row. A second button
beside it, a second arrow, or a button that appears only in some states makes the list ragged. The
record's own actions (continue, withdraw, apply again) sit on the record's page.

A page for one record shows that record's facts in a definition list: its state, each date it
has (started, submitted, decided), and what the person still has to do. The actions come after the
facts. A page whose only content is a heading and a button is unfinished.

## Visual checklist

What QA checks in a screenshot of any FLS page.

- At 1024px and wider the navigation is a left column beside the content, never a band above it, never the page's width, never missing, JavaScript on or off.
- A person is linked with the avatar-and-name person link, never a bare name.
- Only a link in the middle of a sentence is underlined. A link in a table cell, a definition list, a card, a list or on a line of its own has no underline.
- A control that changes a thing sits beside the thing it changes; a Settings tab holds only the
  actions with no home of their own.
- Status badges carry one of the five status tones; a label that is not a status is a chip.
- Every button label sits on one line at 375px, 768px and 1280px.
- A block with a long list (more than about ten rows) scrolls inside a capped region; the page does not grow with the list.
- What succeeded and what failed sit in separate panels, not one card.
- A page a person cannot use shows a large centred icon with text under it, not a callout.
- Outside course content, no box has a thick coloured bar down its start edge: nothing looks like an admonition.
- Every deadline, close-date, time-limit or access-date line a learner sees ("Closes" included) has its own coloured icon and bold tier word, with the date in muted mono; none is plain text, and none sits inside another deadline's block.
- Every expand chevron (menu button, disclosure, filter chip, accordion) points down while closed and up while open.
- Items are separated by space: no box around each option, no box inside a box, no bordered or tinted tile around each figure in a group of stats; a rule appears only at a card or dialog edge, a dialog header or footer, a table header, or between the rows of a ruled list of records.
- A callout has clear space between its border and its content, and between its title, text and buttons; nothing inside it looks packed.
- A list inside a callout has its bullets level with the start of the callout's title text, not indented past it.
- A form error that belongs to no single field sits in an error callout above the form, never as bare red text.
- Buttons of one size are one height, whatever their variant: an outlined button is no taller than a filled one beside it.
- A button clicked with the mouse shows no focus ring; a toggle looks the same in both of its states. Tab to it and the ring shows.
- The icon in an icon-only button sits at its centre, not low and not to one side.
- A new section looks like its neighbours: headings the same size and style as their siblings, and the same row component for the same kind of list (course content always in course outline rows). Nothing on the page looks pasted in from another site.
- Content lines up: blocks start and stop on their container's padding, buttons line up with the text above them, items of one kind share a column.
- A page opened from another page starts with a back link at the top left, above the heading, in the back-link style; no button on the page goes back.
- A button that starts an irreversible action (withdraw, delete, remove) is red, on the page and in its confirm dialog.
- A "Details" link on a row or card opens the record the row shows, not a related record.
- Each row or card in a list ends in one control, in the same place on every row, with one arrow; no row has an extra button.
- A page for one record lists its state, its dates and what is left to do in a definition list above its actions.
- A marked answer option has a green border and tint when it is the correct one and a red border and tint when it is a wrong pick; no result is shown by an icon alone.
- A result and its explanation sit inside a callout in the result's tone, not under a bare heading.

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

            <c-callout tone="info" title="Note">
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
