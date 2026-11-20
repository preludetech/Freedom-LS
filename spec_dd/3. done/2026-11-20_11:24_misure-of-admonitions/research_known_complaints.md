# Research: known complaints about inline alert components

Topic `known_complaints` for spec `misure-of-admonitions`. Sources are web search results; some were read only as search summaries. Treat the claims as leads to verify, not settled fact.

## 1. Screen readers announce, or miss, alerts

- A `role="alert"` element that is inserted into the DOM already filled with its message often isn't announced. MDN says not to add an element that already has `role="alert"` and the message, because that isn't a content change. Behaviour differs between browser and screen reader pairs. MDN also says alert content is announced whether the region is in the initial markup or injected, so sources disagree.
- Common advice is to render an empty live region at page load and change its text later. Use `role="status"` (polite) for non-urgent messages.
- A reported case: a `role="status"` region injected with JavaScript stayed silent, while `role="alert"` worked.
- Overuse is a complaint in itself. `role="alert"` on routine status drowns users in interruptions. Alerts fired in quick succession queue, sometimes for tens of seconds.
- Implication for a static in-page alert: if it is in the server-rendered page, it needs no live-region role. Static content is read in normal reading order. A role is needed only for alerts that appear after the page loads, such as HTMX swaps.

Sources:
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/alert_role
- https://tetralogical.com/blog/2024/05/01/why-are-my-live-regions-not-working/
- https://htmhell.dev/adventcalendar/2023/22/
- https://www.disabilityworld.org/toolkit/standards/aria/alert/
- https://github.com/FreedomScientific/standards-support/issues/696
- https://scottohara.me/blog/2022/02/05/are-we-live.html

## 2. HTMX swaps and alerts

- HTMX does not announce swaps. Partial swaps don't trigger live regions on their own, so a persistent `aria-live="polite"` container (with `aria-atomic="true"`) must exist before the swap, and the server targets it with an out-of-band fragment.
- Focus isn't moved by a swap. Handle it explicitly if the alert needs attention.
- Layout shift: I found no source that covers layout shift from alerts inserted by HTMX swaps. The only related guidance is to keep the container in the DOM and swap content into it. That is an inference, not documented advice. This is a gap to settle in the spec's own decisions.
- In htmx 2, out-of-band elements are swapped before the main content.

Sources:
- https://four.htmx.org/docs/core-concepts/multi-target-updates
- https://yarlson-dev.pages.dev/blog/htmx-toast/
- https://camoa.github.io/dev-guides/drupal/ajax-htmx-migration/accessibility-migration
- https://www.freelock.com/advent/2025/6-did-you-get-message-making-status-updates-accessible

## 3. Colour-only meaning

- WCAG 1.4.1 (Level A) says colour must not be the only way to convey information. The common failure is a red or green box with no icon or text label. The fix is an icon plus text plus colour, with the icon also meeting non-text contrast (1.4.11).
- The grayscale test is a quick check: if the meaning is lost in grayscale, it fails.
- Implication: each variant needs a distinct icon and a visible or visually hidden label, such as "Warning".

Sources:
- https://w3c.github.io/wcag/understanding/use-of-color
- https://webaim.org/articles/contrast/
- https://www.boia.org/blog/use-of-color-for-accessibility-explained
- https://developer.mozilla.org/docs/Web/Accessibility/Understanding_WCAG/Perceivable/Use_of_color

## 4. Banner blindness, overuse, hierarchy

- Habituation: repeated warnings are dismissed automatically. Alarm fatigue in healthcare is the strongest evidence. The lesson is that alerts shouldn't fire for everything, so the critical ones stand out.
- One alert can be well designed, but many on one screen overwhelm users. Design a hierarchy of attention.
- I found no concrete numeric limits for inline alerts. The guidance is general: reserve alerts for high-signal events, rank by severity, test in context.
- Implication: keep the variant set small, and make the "info" style quiet. Don't use an alert for plain explanatory text.

Sources:
- https://uxdesign.cc/how-to-design-to-alert-users-without-overwhelming-them-4bb41feda9f0
- https://nhimg.org/faq/why-do-repeated-security-warnings-stop-changing-user-behaviour/
- https://www.plushcap.com/content/logrocket/blog/logrocket-why-users-ignore-notifications-and-how-to-fix-it

## 5. Look-alike components and drift (content callout vs UI alert)

- Design systems often mix up callout and alert. Cimpress separates them by trigger: alerts respond to user actions and hold no interactive elements. Twilio Paste treats alerts as system-level messages not tied to a user action. Different systems draw the line in different places, so the spec has to draw its own and write it down.
- Splitting: one team started with a single "Alert" ticket and ended with Toast, Callout and Notification, keeping "Alert" only as a group name.
- Visual convergence causes confusion. In the NSW design system, a callout update removed its icon and background, and it came to look like in-page navigation.
- Duplicate components accumulate into "a graveyard of half-maintained, overlapping, and occasionally identical components". Suggested fixes are inclusion criteria, an audit, and a rule not to build custom alert UI. Octopus Deploy's rules tell contributors not to build custom alert or notice UI.
- Sentry's docs have an `Alert` and a `Note` both used as callout boxes, which is the drift this spec is fixing.
- Misuse happens because the nearest-looking component gets picked. The usual causes are no decision guide, no enforcement, and a generic name. The name `callout` in the base app reads as general UI, though it carries content styling.
- Implication for FLS: the planned invariant test, a decision guide in the skills, and deleting `c-callout` match the common remedies (guardrail, documented rule, removal of the duplicate). A name that says what it is for ("alert") helps more than a generic one.

Sources:
- https://ui.cimpress.io/components/callout
- https://paste.twilio.design/components/alert (indexed under paste-docs.vercel.app/components/alert)
- https://www.designsystemscollective.com/redesigning-an-alert-component-03de817af7f6
- https://community.designsystem.nsw.gov.au/t/callout-component/1107
- https://www.designsystemscollective.com/component-overload-why-your-design-system-has-too-much-stuff-e6efd5a22c1e
- https://unpkg.com/@octopusdeploy/design-system-components@2026.3.8512/skills/octopus-design-system/rules/feedback.md
- https://github.com/getsentry/sentry-docs/issues/12053
- https://clipcontent.substack.com/p/a-taxonomy-for-alerts-and-notifications

## 6. Not covered by the research

Searches did not return reliable sources on alerts that look like content, or on oversized callouts in dense UIs. The standard design-system advice is compact padding, a clear border or tint, and an icon that separates alerts from body text. Treat that as unsourced.

status: ok
