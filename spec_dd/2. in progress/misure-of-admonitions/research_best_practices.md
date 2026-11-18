# Research: best practices for a static inline alert component

Scope: reusable, non-dismissible inline alert for app UI (Django, cotton, Tailwind, HTMX), variants info/success/warning/error, separate from content-engine admonitions. Items marked (inference) are my synthesis, not a quoted source rule.

## 1. Accessibility

### Role choice
- `role="alert"` is for brief, important messages that get attention without interrupting the task. It must not move focus. Alerts must not auto-disappear (WCAG 2.2.3/2.2.4). Screen readers do not announce alerts already present at page load; only alerts injected after load are announced. [APG Alert](https://www.w3.org/WAI/ARIA/apg/patterns/alert/)
- `role="status"` is a polite live region (implicit `aria-live="polite"`, `aria-atomic="true"`) for advisory info. Do not move focus to it. Use `alert` for urgent or blocking messages. Naming it is optional. [MDN status role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role)
- GOV.UK's notification banner uses `role="region"` with `aria-labelledby` pointing at its title. Only the success variant gets `role="alert"`, and the banner is meant to be used sparingly. [GOV.UK Notification banner](https://design-system.service.gov.uk/components/notification-banner/)

### Recommended default (inference)
- A static alert that is part of the initial page render should have no live-region role by default. It is read in document order, and `role="alert"` on load is not announced anyway. A caller who wants the semantics can opt in.
- Offer an opt-in parameter, for example `live="polite"` (renders `role="status"`) or `live="assertive"` (renders `role="alert"`). Make error the only variant that may reasonably default to `alert`. Keep info, success and warning at none or `status`.
- Avoid putting `role="alert"` on many alerts in one page. Over-announcing is the common failure mode.

### HTMX-swapped alerts
- Live regions are reliably announced only if the region element already exists in the DOM before its content changes. Inserting a region together with its content is often not announced. Sources: [Sara Soueidan, live regions part 2](https://sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-2), [Drupal HTMX a11y migration guide](https://camoa.github.io/dev-guides/drupal/ajax-htmx-migration/accessibility-migration), [HTMHell on live regions](https://htmhell.dev/adventcalendar/2023/22/). The Drupal guide is the most HTMX-specific: add `aria-live="polite"` and `aria-atomic="true"` to containers that get swapped.
- So the pattern is: a persistent wrapper (`<div aria-live="polite" aria-atomic="true" id="...">`) in the page or form, with `hx-target` set to it and an innerHTML swap. The swapped alert partial inside it is then plain markup, with no role of its own. A swapped-in `role="alert"` element is less reliable than a persistent wrapper, so verify with a screen reader.
- The component should therefore not own the live region in the HTMX case. Document a wrapper convention, or give the component a wrapper-only mode (inference).
- 422 validation errors: GOV.UK says not to use a banner for validation errors; use field-level errors plus an error summary. An alert is for form-level or page-level problems, not a replacement for field errors.

### Not colour alone
- WCAG 1.4.1 (Level A): pair colour with text, shape or icon. [Understanding Use of Color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) GOV.UK also uses a text label such as "Success" and keeps labels consistent across the service.
- Each variant needs a distinct icon shape (info, check, triangle, octagon or circle-x), and the title or a visually hidden prefix ("Error:", "Warning:") should carry the meaning for screen readers (inference, consistent with the GOV.UK label practice).

### Icons
- A decorative icon next to a text title or visible prefix gets `aria-hidden="true"` and no label. If no text prefix exists, give the icon an accessible name, or add `sr-only` text. Do not do both, or the meaning is announced twice (inference, standard practice).

### Contrast
- Text needs 4.5:1 (WCAG 1.4.3). Icons and borders that carry meaning need 3:1 (1.4.11). I did not fetch these pages. They are well-known WCAG criteria. Check the tinted-background plus coloured-text pairs for all four variants, in light and dark mode if the theme has one. Warning (yellow or amber) is the usual failure, so use dark text on a pale amber background, not amber text.

## 2. Heading semantics for titles
- GOV.UK renders the banner title as `h2`, allows `h3` inside for longer content, and advises against headings for single-line messages. [GOV.UK](https://design-system.service.gov.uk/components/notification-banner/)
- Implication for a component (inference): do not hard-code a heading level, because the right level depends on where the alert sits. Options: (a) a `title` slot rendered as a non-heading element such as `<p class="font-semibold">` (safest, no outline pollution); (b) an optional `heading_level` parameter (default none). Title is optional. Many alerts are a single line and should not produce a heading.
- If the alert is a labelled landmark (`role="region"` plus `aria-labelledby`), do that only for page-significant banners. Inline alerts in forms should not become landmarks.

## 3. Variant naming
- This spec's set is info, success, warning, error. It is the common developer vocabulary and maps to the existing Tailwind and Django message tags.
- Other systems use different names: GOV.UK has default and success; Adobe Spectrum uses semantic names (informative, positive, negative, notice) (from memory; the Spectrum page returned 404 when I fetched it). Atlassian and others use info, success, warning, error (not fetched).
- Recommendation (inference): use `info | success | warning | error`, with `info` as the default. Name by meaning, not colour (not `blue`/`red`). Validate the value and fail loudly on unknown variants. Map Django message tags (`debug`, `info`, `success`, `warning`, `error`) onto them.

## 4. Density and spacing, app UI vs prose
(inference, from general design-system practice; no source fetched for specifics)
- App alerts are compact: small padding (about `p-3` or `p-4`), a 16 to 20px icon, text at the base or small size, and no large vertical margin of their own. Spacing between the alert and its neighbours is the parent's job (`space-y-*`, `gap-*`), not the component's.
- Prose callouts (admonitions) are the opposite: they sit in flowing reading content, with generous margins, a larger type scale and heavier decoration (side-border and big icon), and they may hold multiple paragraphs, lists and code. An app alert should hold short text plus an optional action link.
- Use the app's existing tokens: radius, border weight and semantic colour classes. Do not copy admonition colours.

## 5. Keeping content components out of app UI (governance)
- Established design-system practice is tooling, not documentation alone:
  - Import boundaries via ESLint `no-restricted-imports` with directory-scoped overrides. [ESLint no-restricted-imports](https://eslint.org/docs/latest/rules/no-restricted-imports), [Shopify strict-component-boundaries](https://cdn.jsdelivr.net/npm/@shopify/eslint-plugin@50.0.0/docs/rules/strict-component-boundaries.md).
  - "Use the design system component instead" rules with a configured forbidden list and an alternative named in the message. [eslint-plugin-design-system](https://www.npmjs.com/package/eslint-plugin-design-system), [Atlassian design-system plugin](https://atlassian.design/components/eslint-plugin-design-system/no-deprecated-imports). Atlassian keeps some such rules opt-in.
  - Restricting a CSS class to named files. [eslint-plugin-moxio](https://awesome.ecosyste.ms/projects/github.com%2Fmoxio%2Feslint-plugin-moxio)
- Django translation (inference): the equivalent is a pytest invariant that scans template files for `<c-admonition` (and any other content-engine cotton component) and fails when it appears outside an allow-list (the content engine's own templates, and the template that renders authored content). Good practices:
  - Allow-list is explicit, small and path-based; the failure message names the replacement (`<c-alert>`) and the rule's reason.
  - Scan the template directories of all apps, and also cotton component templates that include other components, since indirect use is the usual leak.
  - Add a positive test: the content-engine admonition still renders in content.
  - Pair the guard with docs (skills and component docs say "content components are for authored content only; use alert for app UI") so the test failure is not the first the author hears of it.
  - Also guard deletion: after `c-callout` is removed, a test that no template references it prevents reintroduction (and a downstream upgrade note covers external users).
- No search result covered architecture tests (ArchUnit style) directly. The template-scan test is the practical equivalent.

## 6. Summary checklist for the spec
1. Static markup, no role by default; opt-in `live` parameter mapping to `status`/`alert`. No dismiss button, no timers.
2. For HTMX, a persistent `aria-live` wrapper; the swapped alert is plain markup. Document it.
3. Variants `info|success|warning|error`; each with its own icon shape and text cue; icons `aria-hidden` when text carries the meaning.
4. Optional title, not a hard-coded heading; optional `heading_level` if needed.
5. Verify 4.5:1 text and 3:1 icon/border contrast for each variant, especially warning.
6. Compact app density; no outer margins.
7. Invariant test with an explicit allow-list, plus a no-`c-callout`-left test; update skills and docs.

## Sources
- https://www.w3.org/WAI/ARIA/apg/patterns/alert/
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role
- https://design-system.service.gov.uk/components/notification-banner/
- https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- https://sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-2
- https://camoa.github.io/dev-guides/drupal/ajax-htmx-migration/accessibility-migration
- https://htmhell.dev/adventcalendar/2023/22/
- https://eslint.org/docs/latest/rules/no-restricted-imports
- https://cdn.jsdelivr.net/npm/@shopify/eslint-plugin@50.0.0/docs/rules/strict-component-boundaries.md
- https://www.npmjs.com/package/eslint-plugin-design-system
- https://atlassian.design/components/eslint-plugin-design-system/no-deprecated-imports

status: ok
