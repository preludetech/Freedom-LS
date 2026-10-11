# Research: choosing a recipient at scale

Topic: when the messaging policy permits many recipients (an educator with a large organisation, a
learner with peer messaging on), does the composer search, group, or both? Visual reference only:
`design_source/dm/dm-ui.jsx` (`DMPicker`) and `design_screenshots/educator-messages__02-new-message.png`.

## Recommendation (short)

**Both, with search as the core and grouping as a presentation of the search result, not as the
primary navigation.** Use a single search-as-you-type picker (HTMX, server-filtered, capped result
set) and group the returned rows with a heading per group. Do not render the full recipient list up
front once it could be large. Thresholds are in section 4.

## 1. How big can `recipients_for` get, and can it be grouped?

What `recipients_for(sender, site)` is (`freedom_ls/messaging_policy/policy.py`, `LayeredMessagingPolicy`):

- It returns one lazy `QuerySet[User]`: `User.objects.filter(site, is_active).exclude(sender)` filtered
  by `_role_condition | _candidate_condition(open_only=True)`. Everything is `pk__in` / `Exists`
  subqueries, "so it needs no distinct() and stays filterable" (docstring). So the picker can add
  `.filter(...)` for search, `.order_by(...)` and a slice, and it is still one SQL statement. Before
  that, `_resolve` costs two small queries (the sender's `Learner` rows, the `SiteMessagingConfig`
  row), plus whatever `roles_granting` and `_site_grants(...).exists()` read. The spec 3 requirement is a
  fixed query count that does not grow with learners, cohorts or registrations.
- An inactive sender gets `User.objects.none()`.

How large it gets:

| Sender | Who is in the set | Upper bound |
|---|---|---|
| Educator with a site-level grant of `view_learner` | `visible_learners_expression` returns `Q(site=site)`, so **every active learner on the site**, plus colleagues (`colleagues_of`) | The whole site: thousands on a big deployment |
| Educator with an organisation-level grant | Every active learner of the organisation, plus colleagues | The organisation: hundreds to thousands |
| Educator with cohort-scoped grants only | Members of the granted cohorts (plus colleagues) | Sum of the cohort sizes: tens to a few hundred |
| Learner, peers on | `peers_through`: other active learners in the sender's organisation who share an open cohort, or hold an active registration for a course the sender holds (individually or through a cohort); plus offered educators (`educators_of`, narrowed by `offered_roles_for`) | Cohort and course mates: tens to hundreds, **thousands** when one course is registered organisation-wide |
| Learner, peers off (the default) | Only offered educators | Small, single digits to tens |

The superuser branch is not in `recipients_for` (it goes through `can_start`'s ordinary path), so a
superuser sees the same set as any user with those grants.

Does it give enough to group?

- **No grouping key comes with the queryset.** A `User` row carries no cohort, course or role. The
  policy deliberately collapses "why can I message this person" into one `pk__in` condition.
- **A person can belong to several groups.** One peer can share two courses and a cohort with the
  sender; one learner can be in several of an educator's cohorts. Grouping by course or cohort is
  therefore a choice of which group to show (first by name, or the person repeated under each group
  as the educator design does for "Kawame Asante" style rows), not a fact on the user.
- **Grouping can be done without a per-group query.** Take the page of user ids the picker is about to
  show (a capped slice, see below) and run one query per grouping dimension keyed on `user_id__in`:
  - cohort: `CohortMembership.objects.filter(learner__user_id__in=ids, cohort__is_active=True)` with
    `select_related("cohort")`, restricted for an educator to `cohorts_visible_to` /
    `all_cohorts_visible_to(user)` so a cohort the educator cannot see is never named;
  - course: `registrations_of`-style reads for those ids (`LearnerCourseRegistration` and
    `access_granting_cohort_registrations()` with `select_related("course")`), and for a learner
    restricted to courses the sender also holds (the thing that made them peers);
  - role: educators first, then peers, from one `educators_of`-shaped `Exists` annotation or by
    intersecting the page's ids with the educator set (`educators_of(row, roles=offered_roles_for(...))`
    per sender row, normally one row). Display name of the role is available via
    `get_role_config(site.name)` as `cohort_educators` shows.
  This is a **fixed** number of extra queries (about two to four), not one per group, and it runs only
  on the capped page. It must be written new: no existing helper returns "this user, grouped by the
  reason they are reachable".
- **Group headings make the page long.** Ungrouped but searched results are shorter and ordered by
  relevance; grouped results need the whole matching set to fill the groups. So grouping and a
  result cap interact (a cap per group, or a total cap that can truncate later groups).
- The spec 3 policy forbids a picker from inferring permission from a group: the server must still
  re-check with `can_start` on send. Grouping is display only.

## 2. Existing FLS UI pieces

Findings from the repo:

- **No combobox / autocomplete / listbox exists.** A search for `role="combobox"`, `aria-activedescendant`,
  `role="listbox"` under `freedom_ls/` finds nothing. The Alpine inventory
  (`claude_plugins/fls-dev/skills/alpine-js/SKILL.md`) lists `dropdownMenu`, `appModal`, `quickView`,
  etc., but nothing that implements a combobox. The existing `<c-dropdown-menu>` is a menu button, not a
  field with a listbox, and must not be bent into one (different ARIA pattern).
- **Reusable as building blocks:**
  - `<c-panel-search-field>` (`freedom_ls/panel_framework/templates/cotton/panel-search-field.html`): a
    labelled `<input type="search">` with a decorative icon; `{{ attrs }}` lands on the input so it can
    carry `hx-get`, `hx-trigger`, `hx-target`. This is the search box. It has no `role="combobox"`
    wiring, which the picker would add through `attrs` if it commits to the combobox pattern.
  - `<c-panel-avatar-chip>` (`panel-avatar-chip.html`): initials circle plus name and a `secondary`
    line (email or role). Fits a row of "name + role/course".
  - `<c-panel-status-badge>` for a role tag; `<c-panel-empty-state>` for "no one you can message";
    `panel_framework/partials/announcer.html` (the `announcer_host`) for the polite "n people match"
    announcement; `<c-panel-skeleton>` for loading.
  - `freedom_ls/panel_framework/filters.py` defines `TableFilter`, `ChoiceFilter`, `RelatedChoiceFilter`,
    `BooleanFilter` for data tables. These are table filters, not a picker. They show how the framework
    does URL-param search plus a `RelatedChoiceFilter` for "filter by cohort", which could be reused
    as the "narrow by cohort/course" control if the picker is a panel-framework page, but the composer
    is a learner-interface page, so reuse is limited to the idea.
  - `appModal` / `quickView` Alpine hosts: a picker could open in the existing modal host if it is a
    dialog (the design draws it as a dialog on the learner side and an inline panel on the educator
    side).
- **HTMX search pattern** (`claude_plugins/django-stack/skills/htmx/SKILL.md`, "Debounced Search
  Input"): `hx-trigger="submit, input delay:300ms from:#search-input"`, `hx-include`, `hx-swap="outerHTML"`,
  state in query params, a `partial_` view that returns just the results fragment, 422 for validation
  errors, `HX-Request` detection. That is exactly the server-filtered result list the picker needs.
- **Separation of concerns** (same skill): HTMX for server data, Alpine for client-only state. So the
  server filters and groups; Alpine would carry only the active option and open/closed state.

What this means: the search box, avatar rows, role tag, empty state and live-region announcement
exist. What does not exist, and the spec must either build or avoid, is the **keyboard-navigable
listbox** (arrow keys, active descendant). The cheapest correct option is to avoid the combobox role
(see section 3, "search box plus results list").

## 3. How other products do it, and accessible patterns

### Other systems

- **Canvas Inbox** (https://community.canvaslms.com/docs/DOC-2670,
  https://community.canvaslms.com/docs/DOC-26251): pick the course first (a course dropdown with its own
  search), then type in the To field and pick from suggestions, or use an **address book** button that
  lets you browse and filter by Teachers / Students / Student Groups. Multiple selection, optional
  "send individually"; above 100 recipients it sends individually. Takeaway: scope-then-search, with a
  browse affordance that is grouped by role.
- **Moodle** (https://docs.moodle.org/405/en/Messaging, https://docs.moodle.org/en/Messaging): a
  contacts panel with a search that returns "contacts" and "non-contacts"; whether you can find
  non-contacts is limited by the site's site-wide messaging setting and each user's privacy choice
  (contacts only, contacts plus course-mates, or anyone on the site). Takeaway: search results are
  grouped by relationship (contacts vs non-contacts), and **who is findable is a policy setting**, as
  in FLS where `recipients_for` is the findable set.
- **Google Classroom** (https://support.google.com/edu/classroom/answer/9093530?hl=en and the
  third-party summaries at https://shakeuplearning.com/blog/google-classroom-comments-all-you-need-to-know/):
  there is no general DM picker. Conversations are private comments attached to an assignment or the
  student's work, so the recipient is implied by context and no recipient list is ever shown.
  Takeaway: when context identifies the person (the learner quick view in the educator interface), skip
  the picker entirely. This matches the design brief's "message box in the learner quick view".
- **Slack and Microsoft Teams** (from general knowledge; not re-verified in this session, so treat as
  unconfirmed): both use a single "To" typeahead over a directory: you type, results are ranked and
  tagged (people, channels; Teams shows the person's job title or department), and there is no
  full-list browsing screen because the directory is large. Slack shows recent conversations first
  when the field is empty. Takeaway: search-first with recents on empty is the norm at scale; grouping
  is by type of thing, not by organisational unit.

Common thread: nobody shows a flat list of everyone once the directory is large; they scope (course),
search, and tag.

### Accessible combobox (WAI-ARIA APG)

Source: https://www.w3.org/WAI/ARIA/apg/patterns/combobox/ and the list-autocomplete example
https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/ (fetched).

Required pattern: input with `role="combobox"`, `aria-autocomplete="list"`, `aria-controls` pointing
at the popup, `aria-expanded`, and `aria-activedescendant` for the visually focused option; popup is
`role="listbox"` with `role="option"` children, `aria-selected` only on the active option. DOM focus
stays in the input. Keys: Down/Up move (and wrap), Enter chooses, Escape closes (or clears when
closed), Alt+Down opens, Home/End/Left/Right stay in the text.

Pitfalls (the APG page and common experience):

1. Browsers do not scroll an `aria-activedescendant` target into view; the script must.
2. APG says its code is illustrative, "not intended for production", and that mobile and touch support
   has gaps; test with assistive technology. "No ARIA is better than Bad ARIA."
3. **Groups inside a listbox.** Options may be wrapped in `role="group"` with a label inside a listbox;
   support in screen readers varies, so the group heading must also be readable as text in the option
   (for example the course name on the option's secondary line), not only as a group label.
4. **Live results.** An async result list needs a polite status ("4 people match") in a live region;
   the design already does this (`role="status"` with a count).
5. **Two things per row.** Rows with an inner link or button ("Open existing conversation") break the
   one-option-one-action model; give each person one action, and say in the row text when a
   conversation already exists.
6. **Touch and 375px.** A popup list anchored to a small input is hard to use on a phone; the design
   renders the picker as a full-screen dialog on mobile. WCAG 2.2 AA applies (target size 24px
   minimum, focus visible, no reliance on colour for role tags).
7. **Debounce versus announcements.** Announce after the swap, not on every keystroke.

**Simpler alternative that avoids the combobox role:** a labelled search input followed by an ordinary
list of buttons (or a radio-like list) in a region that is updated by HTMX, with the count announced.
Tab moves through results; no `aria-activedescendant`. It is less slick than an arrow-key combobox but
is robust, needs no new Alpine component, and is what `DMPicker` in the learner design is (a search
field plus a list of `<button>` rows in a `role="group"`-wrapped list inside a dialog). The educator
design draws the arrow-key hint ("up/down to move, Enter to choose, Esc to close"), which implies a
combobox. The spec should pick one; both are viable.

### Privacy and enumeration

- Revealing a list of users is an information disclosure even inside a site. Typical enumeration
  guidance is about not distinguishing "exists" from "does not exist" and rate limiting lookups
  (https://guides.codepath.org/websecurity/Username-Enumeration,
  https://gitlab.com/gitlab-org/gitlab/-/issues/29040). I found no authoritative minimum search length
  to cite; the figures below are a design judgement.
- In FLS the picker's candidate set is **already the policy's allowed set**, so the biggest control is
  structural: the search endpoint must filter **inside** `recipients_for(...)` and never search
  `User` and then check, otherwise a search for a name outside the set could leak existence through
  different responses or timing. A name that matches nobody the sender may message returns exactly the
  empty message "No one you can message matches ...", the same as a name that does not exist (the
  design's copy already does this).
- Because the set is policy-bounded, an educator already may see these people on learner lists
  (`learners_visible_to`), so the picker adds no new disclosure for educators. For a learner with peer
  messaging on, it is **new disclosure of classmates' names**, which is why that flag defaults closed.
- Further mitigations for the learner side: do not render the whole peer list when the search is empty
  (show educators and recent conversations only); require a minimum of 2 characters before listing
  peers; cap the result count; do not show email to peers (the educator design shows email, which an
  educator can already see; a peer should see name and, if needed, the shared course only); and the
  endpoint is login-required and site-scoped like every FLS view, with ordinary request throttling if
  the project already has one (do not add a new mechanism unasked).
- **What to show per person.** Educator picker: name, a disambiguator (email, because two learners can
  share a name), and the group heading (cohort). Learner picker: name, a role tag for educators (the
  display name from the role config, text not colour only), and the course as the group heading or a
  secondary line; mark "You already have a conversation". Never show data the policy has not
  already made visible to that sender.

## 4. Recommendation: search, grouping, or both, and at what threshold

Proposed rule, to be confirmed in the spec (thresholds are a judgement call for the spec, not
researched facts):

1. **One picker, search-first, server-filtered.** An HTMX search over `recipients_for` with a case
   insensitive match on first name, last name and (for educators) email, debounced at 300ms per the htmx skill, ordered
   by name, capped (for example 20 per search response) with a "keep typing to narrow" line when
   truncated. Always done on the server: this keeps the fixed query count and avoids sending the set
   to the browser.
2. **Grouping is a presentation of the capped result**, fetched with the fixed extra grouping queries
   from section 1: educator picker grouped by cohort; learner picker with educators first (their
   own labelled group, "Your instructors") then peers grouped by course. A person appearing in
   several groups is shown under their first group only (by group name) to keep the list short and
   the option ids unique.
3. **Threshold for the empty-field view.**
   - Up to about 15 recipients in total (typical learner with peers off, or a small educator):
     show them all, grouped, with the search box available but not required. Count is one cheap
     `COUNT(*)` of the same queryset.
   - Above that: with an empty field show only the sender's recent conversations and the
     educator group (for a learner), or the educator's cohorts as group headings with counts and no
     people (for an educator), and require a search term (2 or more characters) to list people.
   This avoids rendering thousands of rows and limits the enumeration surface for peers.
4. **Skip the picker where context names the person**: the learner quick-view message box and "message
   this learner" actions on learner lists start the conversation directly (Google Classroom's model).
5. **Component choice.** Build on `<c-panel-search-field>`, `<c-panel-avatar-chip>`, the status badge,
   the empty state and the announcer. Take the simple search-box-plus-list-of-buttons form unless the
   spec wants arrow-key navigation, in which case a new Alpine combobox component is a real piece of
   work (listbox roles, active-descendant, scroll into view, mobile dialog) and should be its own
   plan task with screen-reader testing. FLS has no existing one.
6. **Server re-check stays.** Whatever the picker shows, the send re-asks `can_start`.

Open for the spec to decide: the exact threshold and cap numbers; whether a person appears once or
under every group; combobox with arrow keys versus search plus button list; whether peers see only
name or name and course.

## Sources

- https://www.w3.org/WAI/ARIA/apg/patterns/combobox/
- https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/
- https://community.canvaslms.com/docs/DOC-2670
- https://community.canvaslms.com/docs/DOC-26251
- https://docs.moodle.org/405/en/Messaging
- https://docs.moodle.org/en/Messaging
- https://support.google.com/edu/classroom/answer/9093530?hl=en
- https://shakeuplearning.com/blog/google-classroom-comments-all-you-need-to-know/
- https://guides.codepath.org/websecurity/Username-Enumeration
- https://gitlab.com/gitlab-org/gitlab/-/issues/29040
- Repo: `freedom_ls/messaging_policy/policy.py`, `freedom_ls/learner_management/queries.py`,
  `freedom_ls/panel_framework/templates/cotton/panel-search-field.html`,
  `freedom_ls/panel_framework/templates/cotton/panel-avatar-chip.html`,
  `freedom_ls/panel_framework/filters.py`, `claude_plugins/django-stack/skills/htmx/SKILL.md`,
  `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`,
  `spec_dd/2. in progress/user-communication-4-direct-messaging/design_source/dm/dm-ui.jsx`.

Not verified: Slack and Teams behaviour (stated from general knowledge); Moodle's search grouping
(inferred from the docs and tracker snippets); no authoritative minimum search length found.

status: ok · reason: complete; Slack/Teams marked unverified
