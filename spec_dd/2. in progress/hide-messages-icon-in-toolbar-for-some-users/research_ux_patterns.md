# Research: UX patterns for conditionally showing a messages entry point

Context: `freedom_ls/base/templates/partials/header_bar.html` renders `{% messages_button %}`, `{% notification_bell %}` and the user menu for every authenticated user. Free-course learners do not need messages; organisation learners do.

Caveat: web search surfaced mostly secondary sources; primary NNG/GOV.UK/Material/HIG pages were not each fetched. Claims below are labelled where they rest on secondary sources or general design-system practice.

## 1. Hide vs disable vs show-with-empty-state

- Three patterns exist for unavailable commands: show normally and error on click, show visibly disabled, or hide. Nielsen's testing found muted/disabled controls with an explanation performed best when the user should know the feature exists. (https://www.uxtigers.com/post/inactive-buttons)
- Rule of thumb (Smashing / Smart Interface Design Patterns): disable when users should know the feature exists and may gain access (e.g. after a step or an upgrade); hide when the feature is irrelevant to that user and can never apply. Disabled controls are also poor for accessibility (not focusable, no explanation to screen readers). (https://smart-interface-design-patterns.com/articles/hidden-vs-disabled/, https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)
- Disabled-button critiques: they look clickable but give no feedback. (https://www.designsystemscollective.com/when-disabled-buttons-become-a-ux-problem-bb4a4cf360ac, https://design.basis.com/patterns/disabled-buttons)
- Implication: a free-course learner will never have messaging, and there is nothing to upsell in the learner's own context, so HIDE is the fitting pattern. A disabled icon adds noise and an unexplained dead control. Show-with-empty-state ("no messages") wrongly implies they could receive messages.
- Exception: if a user could plausibly be messaged later (joins an organisation cohort), the icon appears at that moment. This is fine since it is a state change, not a permanent disability.

## 2. What users expect when a feature is not available

- Users expect header navigation to show only what applies to them (progressive disclosure, role-appropriate chrome). They do not expect to see controls that never work. Persistent, always-present items are expected for core features, so hide only things that are genuinely out of scope. (secondary: Smashing article above)
- If hiding, avoid leaving unexplained gaps: the remaining icons (notification bell, user menu) should reflow naturally; the header uses `flex gap-2`, so removing one item causes no layout hole.

## 3. User with existing threads who loses eligibility

Patterns from general practice (no single authoritative source found; this is synthesis):
- Never silently make existing data unreachable if the user may need it (data access / records expectations). Options, in order of safety:
  1. Eligibility for showing the icon = "feature enabled for the user OR user has any existing thread". This keeps history reachable (read-only if sending is disabled).
  2. Hide the icon, but keep the URL reachable and show a friendly "messaging is no longer available for your account" page with read-only history.
  3. Hide entirely (data orphaned); acceptable only if the product owner decides history is not the learner's to see.
- Prefer a single rule so icon visibility and URL access never disagree (see section 6).
- Decide explicitly whether replies from the other party can still arrive; if sending is blocked for them, the other party's UI should reflect it rather than messages vanishing.

## 4. Unread badges when the icon is hidden

- A badge is part of the icon; if the icon is hidden, unread count must not be shown anywhere else (no unseen counters, no page-title "(3)", no favicon badge, no email-style digest linking to a hidden page).
- Conversely, if a user can still receive messages (existing threads or an educator can still message them), hiding the icon makes those messages unnoticeable. This is a strong reason to include "has unread/any thread" in the visibility rule, or to keep notification-bell entries pointing to the thread. (synthesis; Apple HIG and Material both treat badges as attached to a visible entry point: https://developer.apple.com/design/human-interface-guidelines/badges, https://m3.material.io/components/badges/overview)
- Avoid computing the unread count when hidden (also avoids a pointless query per page load).

## 5. Header consistency across roles and mobile

- Role-dependent header items are normal (admin links, educator links). Keep position and order stable for items that do appear (messages, then bell, then user menu) so muscle memory holds when a user's eligibility changes. (general design-system practice; Material top app bar guidance: https://m3.material.io/components/top-app-bar/overview)
- Apple HIG and Material both recommend a limited number of trailing actions in a top bar and moving extras into an overflow/menu on small screens. The FLS header is already compact (icons only). On mobile, the same visibility rule should apply to any messages entry in a collapsed menu: no "Messages" menu row when hidden. (https://developer.apple.com/design/human-interface-guidelines/toolbars, https://m3.material.io/components/top-app-bar/guidelines)
- Test both states (with and without the icon) at narrow widths; the title uses `truncate` and the nav is `flex-shrink-0`, so one fewer icon only gives more room.

## 6. Direct navigation to the hidden feature URL

- Hiding the icon is not access control. The view must enforce the same rule as the icon (one shared predicate used by template tag and views).
- 404 vs 403 vs friendly page:
  - 403: honest ("you can't use this"), but reveals the feature exists; fine here since messaging is not secret.
  - 404: hides existence; suited to resources owned by others (another user's thread id), where leaking existence is a concern.
  - Friendly page / redirect with explanation: best for users arriving via bookmark, old email link, or notification after eligibility changed. GOV.UK guidance favours plain-language error pages that say what happened and what to do next. (https://design-system.service.gov.uk/patterns/page-not-found-pages/ , https://www.gov.uk/service-manual/design/error-pages -- not fetched; confirm before citing)
  - Recommended combination: feature unavailable for the user -> 403-style friendly page (or redirect to home with a message); thread belonging to someone else -> 404.
- HTMX partial endpoints (unread count, thread list) should return a clean 403/204, not break the header.

## Recommendations summary

1. Hide (not disable) the messages icon when the user has no messaging eligibility.
2. Define eligibility once (e.g. organisation/site setting or cohort membership) and reuse it in the template tag, views and notification links.
3. Decide the existing-threads policy explicitly; safest default is show the icon while the user has any existing thread.
4. No unread badge, title count or notification entries for a hidden entry point.
5. Keep icon order stable; apply the same rule in any mobile menu.
6. Direct URL access when ineligible: friendly explanatory 403 page; 404 for other users' threads.

## References
- https://www.uxtigers.com/post/inactive-buttons
- https://smart-interface-design-patterns.com/articles/hidden-vs-disabled/
- https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/
- https://www.designsystemscollective.com/when-disabled-buttons-become-a-ux-problem-bb4a4cf360ac
- https://design.basis.com/patterns/disabled-buttons
- https://m3.material.io/components/badges/overview
- https://m3.material.io/components/top-app-bar/overview
- https://developer.apple.com/design/human-interface-guidelines/badges
- https://developer.apple.com/design/human-interface-guidelines/toolbars
- https://design-system.service.gov.uk/ (error page guidance; specific URLs unverified)

status: ok
