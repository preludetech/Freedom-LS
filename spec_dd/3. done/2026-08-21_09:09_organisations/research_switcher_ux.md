# Research: organisation switcher UX

## Executive summary

Mature products converge on a small set of rules for org/workspace switchers: put the switcher at
the **top of the primary navigation** (sidebar or global nav), show the **current scope name** plus
some visual mark (logo/avatar/colour) so it is never ambiguous which scope you're in, and treat the
switch as a **navigation event**, not a silent state mutation — most complaints trace back to
products that violate one of these three rules. The two hardest, most-complained-about problems are
(a) what happens to the page you're currently looking at when you switch (stay vs. redirect vs.
broken "not found"), and (b) silent staleness — a switcher whose selection can drift out of sync
with what's actually being shown (URL vs. stored preference vs. multiple tabs), which produces the
single worst failure mode: **a user believes they are in scope A, is actually in scope B, and takes
a destructive or consequential action there.** Accessibility guidance for this exact widget shape
(a single-select list of named options with a persistent current-selection indicator) is well
documented via the W3C ARIA Authoring Practices Guide (APG) listbox/combobox patterns and is
directly implementable.

FLS's existing panel framework already has a well-defined slot for this — `sidebar_content` at the
top of the docked left panel, above `sidebar_nav.html` — and an existing reusable dropdown-menu
cotton component that is architecturally the right building block.

## 1. Canonical patterns

Verified findings, by product, with URLs:

- **Slack** — workspace switcher is a **docked vertical rail on the far left edge of the window**
  (separate from the per-workspace sidebar), showing each workspace as a small icon/logo; the active
  workspace has a distinct border treatment (thick highlight vs. transparent on hover), and every
  workspace is visible simultaneously rather than hidden behind a single dropdown. Slack tried to
  remove/simplify this rail in a 2022 redesign and reinstated it as an optional feature after user
  backlash — evidence that for users with 2+ real workspaces, an always-visible switcher is a
  hard requirement, not a nice-to-have.
  [Slack: Switch between workspaces](https://slack.com/help/articles/1500002200741-Switch-between-workspaces) ·
  [Fast Company: Slack's redesign backlash](https://www.fastcompany.com/90949647/slacks-new-redesign-has-one-big-problem) ·
  [Fast Company: tips after the redesign](https://www.fastcompany.com/90974178/got-the-slack-redesign-try-these-tips)

- **Notion** — the switcher lives as a **single control at the very top of the left sidebar**:
  clicking the current workspace name opens a dropdown listing other workspaces, "join another",
  "create new", and account/settings actions. This is the closest structural analogue to what FLS is
  building (a name-based control at the top of a docked sidebar, not a separate rail).
  [Notion: Intro to workspaces](https://www.notion.com/help/intro-to-workspaces) ·
  [Notion: Navigating with the sidebar](https://www.notion.com/help/guides/navigating-with-the-sidebar)

- **GitHub** — organisation context is expressed through the URL namespace (`/org-name/...`) rather
  than a persistent app-chrome switcher; there is an org picker on `github.com` itself and in the
  top-left "context switcher" on some pages, but a large share of "org switching" is actually just
  navigating between org URLs. This matters for FLS: GitHub's failure mode of stale/broken links
  after an org rename shows the risk of coupling scope to the URL without a redirect strategy.
  [GitHub Docs: renaming an organization](https://docs.github.com/es/enterprise-server@3.0/organizations/managing-organization-settings/renaming-an-organization)

- **GitLab** — actively designing an "Organization switcher" for the left sidebar (as of the linked
  issue) with three integration points: sidebar, breadcrumbs, and the command palette ("Search or go
  to..."). Their documented behaviour rule is the most directly reusable finding of this whole
  research pass: **stay on the current page if it is a cross-organisation page (Explore, Search,
  profile); redirect to the organisation's front page if the current page is organisation-scoped**
  (Projects, Groups, Admin). This is essentially the answer to research question 3.
  [GitLab issue #417778: Add organization navigation](https://gitlab.com/gitlab-org/gitlab/-/issues/417778)

- **Vercel** — team/project switcher supports **favouriting** teams/projects so frequently-used ones
  surface in the dashboard overview; this is the scale pattern (see §6).
  [Vercel changelog: Favorite teams and projects](https://vercel.com/changelog/favorite-teams-and-projects-to-appear-in-your-dashboard)

- **Google Workspace / Google account switcher** — stacked list of avatar+name rows, inactive
  accounts shown with muted/grey background, active one highlighted; scales well because it is a
  simple recognition list, not a search.

- **Canvas LMS** — does *not* have an in-app account switcher in the sense FLS needs. Multi-institution
  Canvas users generally hold **separate accounts per institution** and cannot merge across
  institutions; where merging is offered it is one-way and only within a single institution. This is
  a cautionary data point, not a pattern to copy: Canvas's approach avoids scope-switch bugs by not
  solving the problem at all, which is a worse experience for anyone genuinely part of two
  institutions.
  [Canvas: Users with Multiple Accounts](https://kb.wisconsin.edu/dle/97640)

General pattern summary (design judgement, informed by the above): almost every mature switcher (a)
sits at the top of primary navigation or in global chrome, never buried in settings; (b) shows name
first, logo/avatar/colour second as a scan aid, not as the sole identifier; (c) closes and returns
focus to a stable landmark after selection; (d) is a single control even when the underlying rail
(Slack) also exists — GitLab, Notion, and Vercel all put it as one row/button that expands, matching
the "top of the left-hand panel" placement already fixed for FLS.
[Medium — Ways to Design Account Switchers & App Switchers](https://medium.com/ux-power-tools/ways-to-design-account-switchers-app-switchers-743e05372ede)

## 2. The single-option case

General UX guidance (not switcher-specific, but directly applicable): **disable when a feature
exists but is currently unavailable to the user; hide when it is irrelevant and the user has no
path to make it relevant.** For a switcher with exactly one option there is no meaningful choice to
present, so showing a disabled/greyed dropdown with one item is noise, not a safety net — the
educator idea document's own fixed decision ("shown only when more than one school is available") is
consistent with this guidance, not a shortcut around it.
[Smashing Magazine: Hidden vs. Disabled in UX](https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)

The discoverability cost is real but is about a different failure than "will the user find the
switcher" — it's "will the user *notice* that a new capability appeared." Smashing Magazine's
explicit warning is "never hide buttons or key filters by default as users expect them to persist,"
which argues for **something else** signalling the school in single-school mode (see §4's "ambient
indicator" — even with only one school, name it, don't just omit UI silently) so that when a second
school is granted, the appearance of a new interactive control is a visible *change*, not an
unannounced feature nobody looks for. There is no rigorous quantified research (e.g. an eye-tracking
study) specifically on this discoverability delta for org switchers; the guidance above is
practitioner consensus, not measured data — flagged as such.

No product researched here hides the switcher outright for single-tenant users in a way that leaves
*zero* trace of "school" as a concept; Notion/Slack/GitLab all show the current scope's name even
when it's the only one, they just don't show an interactive affordance to change it (or grey out
"create/join" actions instead). Filament (a PHP admin framework) explicitly added an option to hide
the tenant menu entirely for genuinely single-tenant apps, which is a different case from "this user
happens to have one school right now" — FLS's case, where a user's count can change over time, so
the persistent-name-without-menu treatment is the closer analogue.
[Filament discussion #7872](https://github.com/filamentphp/filament/discussions/7872)

## 3. What happens on switch

This is confirmed as the most contentious area in real product design discussions.

- **GitLab's documented rule** (verified above): stay on the current page if it's meaningful across
  organisations; jump to the org's front page/dashboard if the current page is org-scoped and would
  not resolve. [GitLab #417778](https://gitlab.com/gitlab-org/gitlab/-/issues/417778)

- **Grafana's real, filed bug** is the "feels broken" case in the wild: switching organisations left
  the user on a "dashboard not found" error page, because the URL still referenced a
  dashboard/slug from the *previous* org and the app didn't detect that the object doesn't exist in
  the new org before rendering the error state. The switcher itself also didn't update to reflect
  where the user actually landed.
  [Grafana issue #10776](https://github.com/grafana/grafana/issues/10776)

- **CircleCI's real, filed bug** shows a related but distinct failure: the switcher's *displayed*
  state reverted to the first org in the list whenever the current URL didn't encode an org
  identifier, producing a mismatch between the breadcrumb (correct) and the switcher control
  (wrong) — i.e., the chrome lied about current scope. Root cause: deriving "current scope" from the
  URL on routes that don't carry an org identifier.
  [CircleCI discuss: Organization keeps reverting to the first one in the list](https://discuss.circleci.com/t/organization-keeps-reverting-to-the-first-one-in-the-list/20291)

Design judgement synthesis for FLS's concrete shape of this problem (list views vs. object-detail
views, e.g. a cohort detail page for a cohort that belongs to another school):

- List/index pages (dashboard, cohort list, student list) are inherently "safe" — switching schools
  and re-rendering the same list route with the new school's data is unsurprising and matches
  GitLab's "stay on cross-scope pages" rule, because from the user's point of view the *page*, not
  the *object*, is what they were on.
- Object-detail pages (a specific cohort/registration) are the risky case FLS was flagged for: the
  object may not exist in the destination school. Rendering Django's normal 404 here (as Grafana
  effectively fell into) reads as broken. The two credible patterns from the research are (1)
  redirect to the equivalent list page in the new school with a brief inline notice ("You switched
  to Oakwood School — this cohort belongs to Riverside School"), matching GitLab's stated rule for
  org-scoped pages, or (2) do not allow the switch to complete mid-object-detail without an explicit
  confirmation if data would be lost (rare in a read-mostly educator interface, but worth flagging
  for any in-progress form). Given FLS's HTMX architecture (`hx-target="#main-content"`,
  `hx-push-url="true"` seen in `sidebar_nav.html`), the natural implementation is: switching school
  is itself an HTMX action that swaps `#main-content` to the equivalent index page for whatever
  section the user is currently in, and pushes that URL — i.e., reuse the exact mechanism the
  sidebar nav already uses for normal navigation, rather than inventing a second navigation model.

## 4. Persistence and surprise

No single "best practice" verified doc says persistence must/must not survive a session; the
trade-off is documented but the decision is contextual:

- Client-side persistence (localStorage/cookie) survives reloads and browser restarts but is
  per-device and per-browser-profile, is invisible to the server on first request, and (per general
  web-storage guidance) is unencrypted and script-readable — not a security concern for a school ID,
  but a state-consistency one.
  [Persisting state on the client side](https://app.studyraid.com/en/read/1903/31004/persisting-state-on-the-client-side) ·
  [4 options for saving user preferences](https://www.wking.dev/library/4-options-for-saving-user-preferences)
- Server-side persistence (store "last selected school" against the user record) survives devices
  but adds a write on every switch and needs a policy for "what if that school is no longer in the
  user's access list" (revoked access since last login).
- The single most relevant *documented* failure pattern found is the CircleCI bug above: whichever
  mechanism is chosen, the switcher's **displayed value must always be derived from the same source
  of truth actually driving the rendered content** — never let the visible chrome and the effective
  scope diverge, or you get exactly the "silently in the wrong scope" failure the research prompt
  asked about. No public incident write-up naming a specific destructive-action-in-wrong-tenant
  story was found in this pass (search did not surface one), but the CircleCI/Grafana bugs are the
  documented near-misses that the concern generalises from, and the underlying mechanism (URL/state
  desync) is exactly the mechanism that would produce a silent-wrong-scope destructive action.

**Ambient signal** (design judgement, consistent with every product surveyed): the current
school's name must be visible at all times the panel is open, not only inside the closed dropdown —
i.e. the trigger control itself always renders "School: Oakwood School", never just a generic
"Switch school" label that requires opening it to know current scope. This matches Notion (current
workspace name always shown at the top of the sidebar) and Slack (active workspace always
distinguishable in the rail). A colour or logo per school is a nice-to-have amplifier, not a
substitute for the name — FLS schools may not have logos, and colour-only signals are an
accessibility risk (see §7).

## 5. Multiple tabs

No single product documents a "solved" answer here; the underlying technical constraint is
consistent across the vendor-neutral sources found: cookie/session-based state (the normal case) is
shared across all tabs in one browser, so if "current school" is only stored in a Django session
cookie, two tabs on two schools is not just theoretically possible — it silently overwrites itself:
whichever tab's request completed last on the server "wins" the session-stored scope, and the other
tab, if it later performs an action, sends it to whatever the session now says, not what its own UI
last showed.
[IBM: session shared across tabs](https://www.ibm.com/support/pages/node/878412) ·
[Session state across multiple browser tabs](https://laracasts.com/discuss/channels/livewire/session-state-across-multiple-browser-tabs)

Two documented mitigation directions:
1. **Encode scope in the URL** rather than (or in addition to) the session, so each tab's own
   address bar is the source of truth and two tabs can genuinely be in two different schools at
   once. This is exactly GitHub's and GitLab's model (org namespace in the URL).
2. **Tab-scoped storage** (`sessionStorage`, which is genuinely per-tab, unlike cookies) as a
   client-side complement, at the cost of not surviving a fresh tab/new-tab-from-link.
   [Session Handling for Multi-User Multi-Tenant Web Applications (patent, background section)](https://patents.justia.com/patent/20190132397)

For an educator workflow specifically (design judgement): this is a real but moderate-severity risk
— educators plausibly do have two schools open in two tabs while comparing cohorts, and a
session-only implementation would make the second tab silently follow the first tab's last switch.
Given FLS already threads state through the URL for `hx-push-url` navigation, putting the school
identifier in the URL (or a URL-derived value, not only a cookie) removes this failure class
entirely and should be treated as close to a requirement, not a nice-to-have.

## 6. Scale

Findings, ordered by evidenced scale:

- **2–5 options**: every source treats a plain list (dropdown or docked rail) as sufficient; no
  search/filter is used by any product surveyed at this scale (Notion, Slack, GitLab's proposed
  design all show a flat list first).
- **~10+ options**: Notion explicitly warns of a *performance* (not just usability) cost once a
  user is signed into "10+" workspace accounts, though they still don't gate this behind search —
  it's presented as a flat list with a documented degradation.
  [Notion: Intro to workspaces](https://www.notion.com/help/intro-to-workspaces)
- **Many options (tens+)**: Vercel's answer is **favourites/recents**, not search-first — favourited
  teams/projects surface first in the dashboard, and the underlying combobox pattern used across
  Vercel's own design system (Geist) explicitly supports "recents" as a first-class concept, keyed
  by a stable id "so recents... survive a rename."
  [Vercel: Favorite teams and projects](https://vercel.com/changelog/favorite-teams-and-projects-to-appear-in-your-dashboard) ·
  [Vercel Geist Combobox](https://vercel.com/geist/combobox)
- A searchable combobox (type-to-filter) becomes the norm once the flat list would require
  scrolling past more than roughly a screenful of options — this is design judgement synthesised
  from the sources above rather than a single stated threshold, but is consistent across every
  large-scale example found (none of them use a plain unsearchable `<select>`-style list once
  option counts get large).

No source in this pass gave FLS's specific "20 vs 200" comparison numbers; treat the following as
design judgement only: 2–5 → flat list, no search needed (this covers FLS's realistic near-term
case per the idea doc's framing); ~10–20 → flat list becomes borderline, recents/favourites start
paying off; 20+ → searchable combobox with recents pinned at the top is the point past which a flat
list is a usability problem, not just a cosmetic one.

## 7. Accessibility

Verified against the W3C ARIA Authoring Practices Guide (APG), the canonical accessibility reference
for exactly this widget shape:

- **Roles**: the options container uses `role="listbox"` with `aria-label` (or `aria-labelledby`)
  naming it (e.g. "Select school"); each option uses `role="option"`.
- **Selection state**: use `aria-selected="true"` on the currently-chosen option; do not mix
  `aria-selected` and `aria-checked` on the same widget.
- **Focus model**: the widget-standard pattern keeps real DOM focus on the trigger/combobox control
  and tracks the highlighted option via `aria-activedescendant` pointing at the option's `id` —
  moving real focus into the list is called out explicitly as a common mistake that breaks
  type-ahead and confuses screen readers.
- **Keyboard**: Up/Down Arrow moves the highlighted option; Home/End jump to first/last (recommended
  once there are 5+ options — directly relevant to FLS at any scale beyond the smallest); type-ahead
  jumps to the next option starting with the typed character; Enter/Space commits the selection and
  closes the list; Escape closes without changing selection.
- **Expand/collapse state**: the trigger button uses `aria-expanded` (true/false) and, per general
  combobox guidance, `aria-haspopup="listbox"`.
- **Announcing the scope change**: because the switch is a full content re-render (new
  `#main-content`, as per FLS's existing HTMX pattern), the practical requirement is that the new
  page's `<h1>`/heading receives focus (or an `aria-live="polite"` region announces "Now viewing:
  Oakwood School") after the swap completes — screen reader users must get an explicit signal that
  the entire content context changed, not just that a dropdown closed. This is a synthesis
  requirement (not lifted verbatim from a single source) but follows directly from APG's general
  principle that state changes affecting content elsewhere on the page must be announced, combined
  with FLS's own HTMX out-of-band-swap architecture already seen in `sidebar_nav.html`.
- **Colour is not sufficient**: given §4's note that a colour/logo chip might be used as an ambient
  scope indicator, WCAG's general non-text-contrast/use-of-colour guidance (well established,
  referenced generally rather than re-derived here) means the school name label is mandatory
  alongside any colour or logo cue, never colour alone.

[W3C APG: Listbox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/listbox/) ·
[W3C APG: Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/) ·
[MDN: ARIA listbox role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/listbox_role)

## 8. Common complaints and anti-patterns

Collected from the sources surfaced above plus general search of complaint/support forums:

- **Chrome lies about current scope** (CircleCI): the switcher shows one org, the page content is
  scoped to another, because the "current scope" the widget displays and the scope actually applied
  to data are derived from different sources of truth (URL vs. stored state). This is the
  single most damaging anti-pattern found and maps directly to FLS's own risk-4/5 concerns.
  [CircleCI](https://discuss.circleci.com/t/organization-keeps-reverting-to-the-first-one-in-the-list/20291)
- **Switching leaves you on a broken/"not found" page** (Grafana): switching context without
  validating the current route resolves in the new context.
  [Grafana #10776](https://github.com/grafana/grafana/issues/10776)
- **Removing an always-visible switcher for "calm" UI actively harms multi-scope users** (Slack
  2022 redesign backlash, later partially reverted): simplifying single-scope UX at the expense of
  power users who juggle multiple scopes was loudly rejected in the wild.
  [Fast Company](https://www.fastcompany.com/90949647/slacks-new-redesign-has-one-big-problem)
- **Merging/consolidating scopes after the fact is a support-ticket-generating dead end**
  (Canvas): once two organisationally-distinct accounts are merged, they generally cannot be cleanly
  split again, and third-party integrations may silently misbehave post-merge. This is a caution
  about over-engineering "helpful" scope-consolidation features rather than a switcher-placement
  lesson per se.
  [Canvas: Users with Multiple Accounts](https://kb.wisconsin.edu/dle/97640)
- **Hidden-by-default power features get relearned every redesign cycle**: the general
  hide-vs-disable guidance explicitly warns that hiding things users expect to persist erodes trust
  in the UI; several of the switcher discussions above (GitLab's own feature request, Slack's
  reversal) are downstream of a product having previously hidden or minimised the switcher and users
  pushing back.
  [Smashing Magazine](https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)

## Recommendations for FLS

The following is opinionated design judgement for the idea document, informed by the findings above.
It is deliberately spec-adjacent but not a spec.

- **Placement**: a single control at the very top of the docked left panel, inside the existing
  `{% block sidebar_content %}` slot, rendered *above* `{% include "panel_framework/partials/sidebar_nav.html" %}`
  (see `freedom_ls/educator_interface/templates/educator_interface/interface.html:10-12` and the
  panel body wrapper at `freedom_ls/base/templates/_base_interface.html:59-62`). This matches the
  Notion pattern most closely (top-of-sidebar, above the nav tree) and requires no new layout
  region — it is a new partial slotted into an existing block, consistent with how
  `sidebar_nav.html` is already just an include.
- **Contents when multiple schools exist**: a button styled like `sidebar_nav.html`'s own nav items
  (`freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html:8-16`) that always
  displays the **current school's name** (never a generic "Select school" placeholder — the name
  itself is the ambient indicator, per §4/§8's "chrome must not lie" finding) with a chevron/expand
  icon, opening a `role="listbox"` of the user's other schools. FLS already has a reusable
  `c-dropdown-menu` cotton component (used for the header user menu,
  `freedom_ls/base/templates/partials/header_bar_user_menu.html:2-32`) — reuse or extend that
  component rather than building a bespoke dropdown, for consistency and to inherit its existing
  accessibility wiring.
- **Single-school behaviour**: per the fixed decision, hide the interactive control entirely — but
  still render the school's name as static text in the same position (not literally nothing), so
  the label "you are in school X" never disappears from the UI, and so that a user who is later
  granted a second school sees the *same* label become clickable rather than a wholly new element
  appearing from nowhere. This satisfies both halves of the hide/disable trade-off in §2: hidden
  because there's no real choice, but not silent about current scope.
- **Post-switch navigation**: switching school is an HTMX interaction using the exact mechanism
  `sidebar_nav.html` already uses for ordinary navigation (`hx-target="#main-content"`,
  `hx-push-url="true"`, `hx-swap="outerHTML"` — see
  `freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html:9-12`), not a new
  navigation model. Rule, following GitLab's documented split (§3): if the current page is a
  cross-school view (a top-level dashboard/list), reload it in place for the new school. If the
  current page is an object-detail view (cohort detail, registration detail) and that object does
  not belong to the newly-selected school, redirect to the equivalent list page for the new school
  with a one-line inline notice explaining the redirect (e.g. "Switched to Oakwood School — that
  cohort isn't in this school"). Never render a bare 404/"not found" as the direct consequence of a
  switch (Grafana anti-pattern, §3/§8).
  Do not add a confirmation dialog for the switch itself in the first cut — none of the products
  surveyed require one for a simple context switch, and the educator interface is read-mostly.
- **Persistence**: encode the selected school in the URL (or make the URL the effective source of
  truth for which school a given `#main-content` render is scoped to), not solely in the Django
  session. This closes both the CircleCI-style "chrome lies about scope" failure (§8) and the
  multi-tab failure (§5) in one move, and is consistent with how the rest of the educator interface
  already threads state through `hx-push-url`. A last-selected-school value may additionally be
  stored server-side against the user (or in a cookie) purely as the *default* for the next fresh
  visit with no school in the URL — but once a URL specifies a school, that always wins over any
  stored default, and the switcher's displayed value must always be read from whatever the currently
  rendered content is actually scoped to, never from stored state alone.
- **Ambient indicator**: the switcher trigger itself, always showing the current school's name, is
  the ambient indicator — no separate header chip is needed given the "top of sidebar" placement
  fixed in the idea. Do not rely on colour or logo alone to distinguish schools (§7); if a future
  iteration adds a colour/logo per school, it must be a secondary cue alongside the name, not a
  replacement for it.
- **Accessibility requirements** (concrete, for the spec phase): `role="listbox"` +
  `aria-label="Select school"` on the option list; `role="option"` + `aria-selected` on each school;
  trigger button has `aria-haspopup="listbox"` and `aria-expanded`; keyboard support for
  Up/Down/Home/End/type-ahead/Enter/Escape per the APG listbox pattern; after a successful switch,
  move focus to (or announce via `aria-live="polite"`) the new page's main heading so screen reader
  users get an explicit signal that the entire content scope changed, not just that a menu closed.
- **Scale**: first cut (2–5 schools per the idea's framing) needs only a flat, unsearchable list —
  do not build search/recents/favourites now. Note in the idea doc as an explicit non-goal for this
  cut, with a documented trigger for revisiting it (roughly "once any single educator's school count
  makes the list longer than fits without scrolling," informally ~10+, per §6) so it isn't
  quietly forgotten.
- **Multiple tabs**: explicitly treat "two tabs open on two different schools must not silently
  cross-contaminate" as an acceptance criterion for the later spec, satisfied by the URL-as-source-
  of-truth decision above rather than by any tab-messaging mechanism.

## References

- [Slack: Switch between workspaces](https://slack.com/help/articles/1500002200741-Switch-between-workspaces)
- [Fast Company: Slack's new redesign has one big problem](https://www.fastcompany.com/90949647/slacks-new-redesign-has-one-big-problem)
- [Fast Company: Hate the Slack redesign? Try these tips](https://www.fastcompany.com/90974178/got-the-slack-redesign-try-these-tips)
- [Notion: Intro to workspaces](https://www.notion.com/help/intro-to-workspaces)
- [Notion: Navigating with the sidebar](https://www.notion.com/help/guides/navigating-with-the-sidebar)
- [GitHub Docs: Renaming an organization](https://docs.github.com/es/enterprise-server@3.0/organizations/managing-organization-settings/renaming-an-organization)
- [GitLab issue #417778: Add organization navigation](https://gitlab.com/gitlab-org/gitlab/-/issues/417778)
- [Vercel changelog: Favorite teams and projects to appear in your dashboard](https://vercel.com/changelog/favorite-teams-and-projects-to-appear-in-your-dashboard)
- [Vercel Geist: Combobox](https://vercel.com/geist/combobox)
- [Canvas / KB Wisconsin: Users with Multiple Accounts](https://kb.wisconsin.edu/dle/97640)
- [Medium — Ways to Design Account Switchers & App Switchers](https://medium.com/ux-power-tools/ways-to-design-account-switchers-app-switchers-743e05372ede)
- [Medium — Breaking Down the UX of Switching Accounts in Web Apps](https://medium.com/ux-power-tools/breaking-down-the-ux-of-switching-accounts-in-web-apps-501813a5908b)
- [Smashing Magazine: Hidden vs. Disabled in UX](https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)
- [Filament discussion #7872 — hide tenant menu](https://github.com/filamentphp/filament/discussions/7872)
- [Grafana issue #10776 — org switch dashboard not found](https://github.com/grafana/grafana/issues/10776)
- [CircleCI discuss — organization keeps reverting to the first one in the list](https://discuss.circleci.com/t/organization-keeps-reverting-to-the-first-one-in-the-list/20291)
- [IBM support — session shared across browser tabs](https://www.ibm.com/support/pages/node/878412)
- [Laracasts — Session state across multiple browser tabs](https://laracasts.com/discuss/channels/livewire/session-state-across-multiple-browser-tabs)
- [Patent background — Session Handling for Multi-User Multi-Tenant Web Applications](https://patents.justia.com/patent/20190132397)
- [W3C APG: Listbox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/listbox/)
- [W3C APG: Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
- [MDN: ARIA listbox role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/listbox_role)

### Codebase references (FLS)

- `freedom_ls/educator_interface/templates/educator_interface/interface.html:8-12` — defines
  `sidebar_storage_key` and the `sidebar_content` block that currently only includes
  `sidebar_nav.html`; this is where the switcher partial would be added, above the nav include.
- `freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html:1-50` — the
  existing nav tree, including its HTMX navigation mechanism (`hx-target="#main-content"`,
  `hx-push-url="true"`, `hx-swap="outerHTML"`) that a switcher should reuse rather than duplicate,
  and its OOB-swap comment pattern (lines 30-33) relevant to keeping the switcher's displayed value
  in sync after any navigation.
- `freedom_ls/base/templates/_base_interface.html:29-64` — the docked/modal `<dialog>` sidebar shell
  (`sidePanel` Alpine controller); the switcher must live inside
  `<div class="px-4 pb-6 lg:px-6 ... pt-6">{% block sidebar_content %}{% endblock %}</div>`
  (line 59-62), i.e. inside the same padded body as the nav, not in the dialog chrome (which has
  none by design, per the comment at lines 50-58).
- `freedom_ls/base/templates/partials/header_bar_user_menu.html:1-33` — existing `c-dropdown-menu`
  cotton component usage; the natural base component to extend/reuse for the switcher's dropdown
  behaviour rather than building new dropdown logic from scratch.
- `freedom_ls/panel_framework/templates/panel_framework/partials/breadcrumbs.html:1-13` — shows the
  existing OOB breadcrumb-swap convention; if a future iteration surfaces school context in
  breadcrumbs (as GitLab's design proposes for organisations), this is the template to extend.

status: ok
