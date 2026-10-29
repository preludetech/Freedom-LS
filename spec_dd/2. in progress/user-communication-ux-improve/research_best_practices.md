# Research: best practices for in-app messaging UX (user-communication-ux-improve)

Scope: web-sourced practices relevant to a Django/HTMX/Alpine app. Source quality is noted; several are vendor/blog sources. Where searches found nothing, that is stated as a gap rather than filled from memory.

## 1. Header messages icon and dropdown (accessibility)

- Use the WAI-ARIA APG **Disclosure** pattern, not `role="menu"`, for a dropdown that holds a list of links (recent conversations). The APG disclosure-navigation example deliberately avoids the menu role because menu roles imply complex keyboard behaviour assistive tech expects. The toggle is a `<button>` with `aria-expanded="true|false"` and optional `aria-controls`; Enter and Space toggle it. (APG example is marked not production code, so treat it as reference.)
  - https://www.w3.org/WAI/ARIA/apg/patterns/disclosure
  - https://www.w3.org/WAI/ARIA/apg/example-index/disclosure/disclosure-navigation.html
- Practitioner caveats (Adrian Roselli): `aria-controls` is optional with sparse AT support; place the disclosed content immediately after the button in the DOM; keep the accessible name short, leaning on visible text.
  - https://adrianroselli.com/2020/05/disclosure-widgets.html
  - https://adrianroselli.com/2019/06/link-disclosure-widget-navigation.html
- Implication for the spec: an icon-only messages button (idea removes the word "Messages") MUST get an accessible name (`aria-label="Messages"`, plus unread count in the name, e.g. "Messages, 3 unread") and a decorative-hidden SVG. Escape should close and return focus to the button (standard disclosure practice; verify in APG page).
- HTMX fit: load the dropdown content lazily (`hx-get` on first open) into the element right after the button; keep `aria-expanded` in Alpine state.

## 2. Unread badge vs notification de-duplication

- Badge should count only unread items and be capped (e.g. "99+"). Opening the panel should clear the "new since last look" signal so badge and panel never disagree.
  - https://www.saasui.design/blog/saas-notification-center-ux-patterns
  - https://patternfly.org/components/notification-badge/design-guidelines
  - https://braze.com/docs/help/best_practices/utilizing_badge_count/
- PatternFly: unread-state-only badges suit items that can be marked read; otherwise prefer a count. Group/bundle to reduce noise; not every item should light the bell (saasui link above).
- In-app, a new message should update the existing count or be inserted into the current view, not trigger a separate alert (uxcel): https://uxcel.com/lessons/notifications-best-practices-164
- Gap: no source directly addressed "two channels showing the same event". The idea's decision (messages icon owns message unread state; bell excludes message events) is consistent with the single-owner-of-signal principle. Spec should define one source of truth for unread count (per-thread read marker) and say the bell feed filters out the message notification type, while email/push preferences (Moodle-style per-channel message preferences) stay separate.
  - Moodle reference for a messaging menu plus per-user message notification preferences: https://docs.moodle.org/35/en/Using_Messaging

## 3. Recipient picker / typeahead

- Use the APG **Combobox** pattern with a listbox popup: `role="combobox"` on the input, `aria-expanded`, `aria-controls` to the listbox, `aria-activedescendant` for the highlighted option, and `aria-autocomplete="list"` (manual selection). Prefer manual selection over inline autocompletion for recipients, since a wrongly auto-filled recipient is easy to miss.
  - https://www.w3.org/WAI/ARIA/apg/patterns/combobox
  - https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/
- Orange's a11y guidelines tested APG listbox examples against the GOV.UK autocomplete and found screen reader variance (ARIA 1.1 era); test with real screen readers: https://a11y-guidelines.orange.com/en/articles/autocomplete-component/
- Concrete HTMX approach: input with `hx-get` + `hx-trigger="input changed delay:200ms, focus"` + `hx-target` listbox; server filters by name AND shows only people the viewer is permitted to message (permission scoping lives server-side, never filter only client-side). Show name plus role/context (e.g. "Educator", cohort) so identically named people are distinguishable; do not require email recall (matches the idea).
- Gap: no source on recipient-picker permission scoping specifically; this is an implementation inference.

## 4. Chat/thread UI accessibility

- Message list as `role="log"` with an accessible name (`aria-label`/`aria-labelledby`); it is implicitly `aria-live="polite"`. Optionally add explicit `aria-live="polite"` and `aria-relevant="additions"` for broader support. Avoid `assertive` (can double-announce on iOS VoiceOver). Limit number of live regions per page; test with NVDA, JAWS, VoiceOver.
  - https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Techniques/Using_the_log_role
  - https://www.uxpin.com/studio/blog/aria-live-regions-for-dynamic-content/
  - https://www.a11y-collective.com/blog/aria-live/
  - https://www.telerik.com/aspnet-core-ui/documentation/html-helpers/conversational-ui/chat/accessibility/overview
- Two-pane layout: the conversation list should be a navigable list of links with unread state conveyed in text (not colour alone), and the current thread marked `aria-current="true"`. (Inference; standard ARIA.) On narrow screens, collapse to list then thread with a visible back link.
- HTMX fit: when polling or SSE swaps in new messages, use `hx-swap="beforeend"` into the log so existing content is not re-announced; avoid replacing the whole log (would re-announce or lose scroll/focus).

## 5. Shared help-desk queue (assignment, claiming, status, SLA)

- One owner per item is the core rule against double handling; enforce it with an atomic claim (only one owner row may exist per conversation, second claim fails) and soft collision/presence indicators ("X is viewing/replying") with a short TTL (~30s heartbeat). Automated routing rules can pre-assign. Track response times.
  - https://developer.nylas.com/docs/cookbook/email/shared-team-inbox/
  - https://www.getmacha.com/ja/glossary/shared-inbox
  - https://blog.hubspot.com/service/shared-inbox-tools
  - Caveat: claim-lock detail is from one developer tutorial; the rest is vendor content.
- Django implementation hint (inference): claim via conditional update (`filter(pk=..., assignee__isnull=True).update(assignee=user)` and check rows affected) or `select_for_update`, returning 409/422-style feedback via HTMX if already claimed.
- Status model example (Frappe Helpdesk): Open, Replied, Resolved, Closed, with SLA timers (first response, resolution) running per status and due times displayed in the ticket view: https://docs.frappe.io/helpdesk/lesson-2understanding-ticket-view
- Edge cases to specify up front (Zoho community thread): who gets first-response credit after reassignment, and whether SLA resets: https://help.zoho.com/portal/en-gb/community/topic/question-regarding-ticket-slas-and-first-response-time?page=3
- Gap: no source found on linking a chat conversation to a ticket or capturing page context. Recommendation from first principles: store a reference to the content item (and course/position) on the help request at creation time, keep the conversation and ticket as separate records linked by FK, and allow one conversation to link to many tickets over time.

## 6. Contextual help in an LMS ("ask about this lesson")

- Gap: searches returned only Moodle generic private messaging (teacher/participants messaging, per-user message preferences), nothing on in-lesson contextual questions: https://docs.moodle.org/35/en/Using_Messaging
- Recommendation (inference): a "Get help" action in the course player that pre-fills subject/context from the current content item, creates the help request in the shared queue (not a direct thread to an arbitrary educator), and shows the learner a confirmation with expected response behaviour. Make the context a structured link, not just text, so staff can jump to the content.

## 7. Oversight, safeguarding, privacy and transparency

- UK DfE filtering and monitoring standards: governing bodies hold overall responsibility, senior leaders run it day to day; automated monitoring should be supported by staff review; clear protocols for responding to flagged incidents; balance privacy and safety. A school running technical monitoring should do its own DPIA.
  - https://saferinternet.org.uk/blog/department-for-education-releases-updated-filtering-and-monitoring-standards
  - https://swgfl.org.uk/magazine/navigating-the-latest-changes-in-dfe-filtering-and-monitoring-standards-for-schools-and-colleges/
- Gap: results did not cover whether staff may read private messages or exact transparency obligations under UK GDPR; consult DfE's full standards and ICO children's data guidance. FLS is multi-tenant and jurisdiction-neutral, so keep this policy-light.
- Practical recommendations for the spec (inferences, flag for human review): (a) show a persistent notice in educator-learner threads that messages may be visible to organisation admins; (b) make admin access read-only and scoped to the admin's organisation; (c) record admin views of threads (audit trail; the repo already has an educator-interface audit log idea, see recent commits) ; (d) restrict oversight to educator-learner threads as the idea states, not learner-to-learner; (e) make the oversight view a separate, explicitly named surface rather than silently widening the normal inbox.

## Summary of decisions the spec should make explicit

1. Messages icon owns unread state; bell excludes message events; one unread-count source of truth.
2. Disclosure (not menu) pattern for the dropdown; icon-only needs accessible name including count.
3. Combobox with manual selection and server-side permission-scoped recipient list.
4. Thread as `role="log"`, append-only swaps.
5. Help requests: single-owner atomic claim, statuses, first-response definition, FK link to ticket and to content item.
6. Oversight: read-only, org-scoped, audited, with user-visible disclosure.

status: ok
