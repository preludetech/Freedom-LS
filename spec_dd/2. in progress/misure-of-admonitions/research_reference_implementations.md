# Research: reference implementations of an inline, static app alert

Topic: how established design systems build an inline, non-dismissed alert for app UI, and how they separate it from content callouts. Findings come from page fetches on 2026-11-18. Where a page did not state something, this file says so rather than guessing.

## Summary table

| System | Component | Variants | Title | Body | Icon | Actions | Dismiss | Role / ARIA |
|---|---|---|---|---|---|---|---|---|
| GOV.UK | Notification banner | default (blue), `success` | required `h2` in header ("Important"/"Success") | content div, optional `__heading` p, links | none documented | inline link only | not offered (still in research) | default `role="region"` + `aria-labelledby` title; success `role="alert"` |
| GOV.UK | Warning text | one | none (text is the message) | bold `strong` | "!" in `span`, `aria-hidden` | none | none | visually hidden "Warning" prefix |
| GitHub Primer | Banner | `critical`, `info`, `success`, `upsell`, `warning` | `title` required (accessible name); `hideTitle` | `description` node | per-variant; `leadingVisual` only for info/upsell | `primaryAction`, `secondaryAction` (Button props), `actionsLayout` | only if `onDismiss` passed | landmark region, `aria-label` override |
| Atlassian | Section message | one per message type (info, warning, error, success, discovery) | optional | description, as brief as possible | fixed per type | one or more links, named by destination | not documented | not documented on usage page |
| Shopify Polaris (web components) | Banner | tone `auto`, `info`, `success`, `warning`, `critical` | `heading` string | default slot | per tone | `secondary-actions` slot, max two secondary buttons | `dismissible` (default false) | not documented |
| USWDS | Alert | `info`, `warning`, `success`, `error`, `emergency`, plus modifiers `slim`, `no-icon` | optional `usa-alert__heading`, one line | `usa-alert__text` | CSS-driven per variant | links only (`usa-link`) | none | `role` on root: `alert` (urgent), `status` (advisory), `region` + label (findable info) |
| Carbon | Inline notification | info, success, warning, error; high/low contrast | short, no trailing period | 1-2 short sentences | per kind | at most one (ghost button) on actionable | optional "x" | not documented on usage page |
| Flowbite | Alert | colour classes (info, danger, success, warning, dark) | optional `h3` | div | inline SVG, `aria-hidden` | button in body | `data-dismiss-target` button | `role="alert"` on root |

Material Design 3 has no inline alert component (it has Snackbar for transient messages and Banner in M2 only). I did not fetch it, so treat that as background knowledge. Tailwind UI alerts are paid and could not be fetched. Flowbite stands in as the Tailwind-class reference.

## GOV.UK Design System

Sources: https://design-system.service.gov.uk/components/notification-banner/ and https://design-system.service.gov.uk/components/warning-text/

- Notification banner is for "something they need to know that isn't directly related to the page content". It goes immediately before the page `h1`, one per page at most, used sparingly.
- Inset text and warning text are the opposite case: information directly relevant to the page content. Validation errors never use the banner; they use error message plus error summary.
- Markup: `div.govuk-notification-banner` (+ `--success`), header with `h2.govuk-notification-banner__title`, then `div.govuk-notification-banner__content` holding `p.govuk-notification-banner__heading` and `a.govuk-notification-banner__link`.
- ARIA: the default banner is `role="region"` with `aria-labelledby` pointing at the title. The success banner is `role="alert"`, which moves focus to it on page load.
- Warning text markup: `div.govuk-warning-text` > `span.govuk-warning-text__icon[aria-hidden]` ("!") + `strong.govuk-warning-text__text` containing `span.govuk-visually-hidden` "Warning". It is a single-line emphasis block with no title or actions.
- Lesson: GOV.UK splits "app-level notice" (banner) from "in-content emphasis" (warning text, inset text) into separate components with different guidance.

## GitHub Primer

Source: https://primer.style/components/banner/ (Flash was not covered by the fetched page; Banner is the current replacement as far as the page indicates, but I did not confirm the deprecation.)

- Props: `variant` (critical, info, success, upsell, warning), `title` (required unless `Banner.Title` child), `hideTitle`, `description`, `leadingVisual` (info and upsell only), `primaryAction`, `secondaryAction`, `actionsLayout` (default, inline, stacked), `onDismiss` (the dismiss button appears only when passed), `layout` (`default` or `compact`, compact cuts padding), `flush` (full-width, for dialogs, tables, cards, boxes).
- Renders as a landmark region. The title is the accessible name; `aria-label` overrides it.
- Lesson: size is a two-value prop (default, compact), and a "flush" mode handles use inside containers. Dismiss is opt-in by prop.

## Atlassian Section Message

Source: https://atlassian.design/components/section-message/usage

- Persistent, sits within a section of the screen. Use when an action may be destructive, the person must act to continue, or there are connectivity or authentication problems.
- Parts: optional title, description (as brief as possible), optional actions as links named by destination ("About user permissions", not "Learn more").
- Distinguished from Banner (whole site), Flag (after an event) and Inline message (a specific small part of the UI).
- Accessibility guidance: do not rely on colour alone, the text should say warning or error, and give a way forward.

## Shopify Polaris Banner

Source: https://shopify.dev/docs/api/app-home/polaris-web-components/feedback-and-status-indicators/banner

- Tones `auto`, `info`, `success`, `warning`, `critical`. `heading` string. Default slot for body. `secondary-actions` slot takes up to two secondary buttons. `dismissible` defaults to false.
- Guidance: one message or required action per banner, short copy, a next step for info, warning and critical. Page-wide banners go outside sections and contextual ones inside the relevant section. Use `badge` for inline status on an item.
- No ARIA documented.

## USWDS Alert

Source: https://designsystem.digital.gov/components/alert/

- Classes: `.usa-alert` root with `--info`, `--warning`, `--success`, `--error`, `--emergency`, `--slim`, `--no-icon`; inner `.usa-alert__body` containing optional `.usa-alert__heading` (examples use `h4`) and `.usa-alert__text`.
- The role goes on the root and encodes urgency: `alert` for errors and emergencies, `status` for advisory (success), `region` plus label for informative or warning. The page's own examples are inconsistent with that table (several have no role).
- Sizing is Sass-token driven (`$theme-alert-icon-size`, `$theme-alert-bar-width`, padding), with `slim` as the compact form, normally without a heading.
- Guidance: start the text with a word naming the alert type, never rely on colour or icon shape alone, do not hide an alert and reveal it later, do not overuse.
- No dismiss and no action buttons, only links. This is the closest match to a static alert.

## Carbon inline notification

Source: https://carbondesignsystem.com/components/notification/usage/

- Kinds: informational, success, warning, error. Inline appears at the top of the primary content area or near the related item, and height should not exceed two lines of text.
- Toast and inline are separate variants of one component family. Actionable allows only one action. Close "x" on inline is optional. Callout (a related style) cannot be dismissed.
- High-contrast versus low-contrast style; "when in doubt, use low contrast". Do not mix styles within a variant.
- Titles are short with no trailing period, body is one or two short sentences.

## Flowbite (Tailwind markup reference)

Sources: https://flowbite.com/docs/components/alerts/ (returned 403) and https://raw.githubusercontent.com/themesberg/flowbite/main/content/components/alerts.md

```html
<div class="p-4 text-sm text-heading rounded-base bg-neutral-secondary-medium border border-default-medium" role="alert">
  <div class="flex items-center">
    <svg class="w-4 h-4 shrink-0 me-2" aria-hidden="true">...</svg>
    <span class="sr-only">Info</span>
    <h3 class="font-medium">Title</h3>
  </div>
  <div class="mt-2 mb-4">Body text</div>
</div>
```

- Pattern: one flex row for icon plus title, a body block, a `sr-only` word for the type, `aria-hidden` icon, `role="alert"` on the root, dismiss as an optional button with `data-dismiss-target`.
- Flowbite puts `role="alert"` on every alert, including static ones. Per the W3C APG alert page (https://www.w3.org/WAI/ARIA/apg/patterns/alert/), screen readers do not announce alerts present before page load completes, so `role="alert"` adds little for static server-rendered alerts. APG also says alerts must not take keyboard focus.

## How they separate app alerts from content callouts

- GOV.UK: banner and warning text are for the service UI; inset text is for page content emphasis. Separate components, separate names, separate guidance.
- Atlassian: scope-based split (Banner, Section message, Inline message, Flag), not content versus UI.
- Carbon and Polaris: the app alert is a status-bearing component (kinds or tones) with no content-author vocabulary like note, tip or caution.
- None of the systems reuse a documentation or content callout for app status. Content callouts (note, tip, warning) are semantic prose blocks authored in markdown. App alerts are status messages with a role, a fixed status vocabulary, and an optional action.

## Patterns relevant to a static, non-dismissible alert

1. Small status vocabulary: 4 or 5 (info, success, warning, error/critical), each tied to an icon and colour.
2. Optional title plus body. Primer and Carbon make the title short. USWDS makes it optional and one line.
3. Icon is decorative (`aria-hidden`) and the type is said in text or `sr-only`. Colour alone never carries meaning.
4. Actions are links or buttons in an optional slot. Carbon limits to one, Polaris to two secondary.
5. Dismiss is opt-in (Primer, Polaris, Flowbite) or absent (USWDS, GOV.UK). A static alert omits it.
6. Sizing: a single compact switch (Primer `layout=compact`, USWDS `slim`) is enough. Primer's `flush` suits use inside cards.
7. Role: the systems disagree. `region` plus label for persistent info (GOV.UK, USWDS, Primer), `status` for advisory (USWDS), `alert` for urgent or server-rendered after-action results (GOV.UK success, USWDS error). A reasonable static mapping is `role="alert"` for error or critical, `role="status"` for success, and no live role (plain labelled content) for info and warning. This is my synthesis, not a quoted rule.

## Gaps

- Atlassian and Carbon pages did not document ARIA roles on the pages fetched.
- Tailwind UI and Material were not fetched.
- GOV.UK notification banner icon not documented on the fetched page.

status: ok
