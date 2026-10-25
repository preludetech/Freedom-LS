# Research: prior art for learner-facing UX refinements

Question: what has already been tried for the four parts of `idea.md` (mobile/tablet layout of the
paged dashboard category sections; a single Back link on the course detail page; a Home/Dashboard item
in the "mobile hamburger menu"; restyling and paging "My Applications"), here and elsewhere, and what
happened.

Paths are relative to the repo root. "Section" is the dashboard-section sense used by the earlier specs
(see `spec_dd/3. done/2026-09-09_21:01_better-learner-dashboard-course-display/1. spec.md`).

## Headline findings

1. **The "hamburger menu" does not exist in the code.** The only header menu on a phone is the avatar
   user-menu dropdown (`freedom_ls/base/templates/partials/header_bar_user_menu.html`: Profile,
   Educator Interface, Admin Panel, Log out). Earlier QA reports state it outright:
   `spec_dd/3. done/2026-09-17_09:26_learner-dashboard-small-fixes/qa_report.md` (section 9: "the mobile
   header collapses to a compact bar (logo + avatar menu, no hamburger)"),
   `spec_dd/3. done/2026-07-01_19:44_home_page/qa_report.md` (line 217: "no hamburger needed for two
   links") and `spec_dd/3. done/2026-10-24_06:02_anon-application-improvements/qa_report.md` (7.3: "no
   hamburger for anonymous visitors"). The spec must decide whether part 3 means adding an item to the
   avatar dropdown (authenticated only; an anonymous visitor has no menu at all) or building a new
   hamburger. It needs the header files read at plan time (`freedom_ls/base/templates/partials/header_bar.html`).
2. **Three of the four parts touch decisions that were deliberately made and QA-verified.** The list
   below is what not to break.
3. **The dashboard applications panel is not owned by `learner_interface`.** It is rendered by the
   `course_applications` app and handed to the dashboard as pre-rendered HTML. Paging it is the hard part
   of part 4, because the dashboard's paging mechanism pages Python/queryset section data, not pre-rendered
   backend HTML (see "Part 4").

## Part 1: category sections, paging and mobile layout

Built by `spec_dd/3. done/2026-09-09_21:01_better-learner-dashboard-course-display/` (spec, plan, QA
report, `research_dashboard_pagination.md`) and amended by
`spec_dd/3. done/2026-09-17_09:26_learner-dashboard-small-fixes/`.

Decisions to keep (do not relitigate):

- **Page size is three for every paginated section**, a module constant, "one full grid row at the `lg`
  breakpoint" (spec "Decisions"). The idea's tablet complaint (2 columns, 3 cards, so an orphan card) is
  a known consequence: `research_dashboard_pagination.md` section 4 recommended a page size divisible
  by 6 for a full final row at every breakpoint, and that research also warned 3 is annoying for
  In progress (section 7.2). The spec chose 3 anyway. Changing to row-like cards on small screens is the
  idea's fix and does not need a page-size change, but any page-size change reopens that decision, the
  ordering/test numbers ("1 to 3 of 4") and the 38px arrows QA.
- **Controls sit in the section heading row**, beside "Browse all courses": heading and description left,
  position text ("1 to 3 of 12"), previous/next and Browse all right
  (spec section 6, "Templates"). The idea wants the controls above the cards and Browse all below the
  cards, centred, on phones and tablets. That reverses the original placement at small widths only.
- **Mechanism to reuse:** `freedom_ls/learner_interface/templates/cotton/course-section-pagination.html`
  (both arrows always rendered, `aria-disabled` not `disabled`, real `href` plus matching `hx-get`),
  `section_page_href` building links from the request query, `page_<slug>` parameter per section,
  `Paginator.get_page()` clamping (200 not 422), swap boundary below the `<h2>` (id `section-page-<slug>`),
  one page-level `role="status"` region updated out of band, a focus handler in
  `freedom_ls/learner_interface/static/learner_interface/js/alpine-components.js`.
  Moving the controls changes none of that, but the focus fallback ("move focus to the `<h2>` when the
  pressed arrow becomes disabled") was verified with the controls in their current place
  (QA report section 8). A layout where the controls are in a different DOM position per breakpoint must
  keep one set of controls (duplicating them per breakpoint would give duplicate `nav` landmarks and break
  the "unique `aria-label` per section" rule).
- **URL is never pushed for section paging.** The first spec decided it (no `hx-push-url`, no
  `hx-replace-url`; Back should leave the dashboard). QA of the small-fixes spec filed this as bug B1,
  and it was closed "working as intended" (`learner-dashboard-small-fixes/qa_report.md`, B1). Do not
  re-add URL pushing.
- **Section wrapper ids** (`current-courses`, `recommended-courses`, `available-courses`,
  `learning-history`, `coming-soon-courses`, `category-<slug>`) are depended on by tests and the
  first spec forbade moving them.
- **Cards are shared.** Category sections reuse `course-grid` and `course_card.html` verbatim
  (`freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html`). The first spec
  and `test_course_cards.py`/`test_anonymous_home_page.py` assert card markup "must not move". A new
  compact row variant for tablets/phones needs a decision on whether it replaces the card at those widths
  (CSS only) or is a second template. The same card appears in two sections for coming-soon courses
  (small-fixes spec), so any row variant must keep its "Coming soon" eyebrow and Details link.
- **Which sections the idea covers.** Every section pages (In progress, Recommended, Learning history,
  Coming soon, Available, categories), and all use `course-grid`. The idea says "each category"; the spec
  should state whether the compact row applies to all sections or only categories (the idea's complaint
  is generic to every grid).

Bugs and observations already filed against this area (read before writing the spec):

- `learner-dashboard-small-fixes/qa_report.md` general notes (cosmetic, unfiled): at 375px the position
  text wraps to two lines on every section carrying a Browse all link; this is the very asymmetry the idea
  fixes by moving Browse all to the bottom.
- `better-learner-dashboard-course-display/qa_report.md` "Cosmetic: the heading-row control cluster":
  on desktop the controls step left and right between sections because Browse all is conditional; on
  mobile the position text wraps. "Arrow hit-target size": arrows are 38x38 px, above WCAG 2.5.8 AA (24x24),
  below the 44x44 guideline. Worth fixing when the controls are moved.
- Same report, section 8 mobile: at 375px, one card per row, zero horizontal overflow, and at 768px two
  per row, no overflow. Those are the baselines the new layout must not regress (zero horizontal scroll at
  375, 768; 200% zoom check with no overflow).
- Same report, section 5: unrelated query parameters (`utm_source`) survive paging; keep.
- `educator-interface-5-permissions/qa_report.md` line 187: unrelated breadcrumb-not-refreshing bug in the
  educator interface (not the learner course detail page).

Documented behaviour to update: `docs/product/learner-experience.md` "Dashboard" (lines 35 to 45):
"Every section shows up to three cards at a time, with previous/next controls and a '1 to 3 of 12'
position beside the heading". This sentence becomes wrong on small screens.

## Part 2: course detail breadcrumbs to a single Back link

Where the course detail breadcrumbs came from:

- The course detail page uses the shared breadcrumbs component:
  `freedom_ls/learner_interface/templates/learner_interface/course_detail.html` lines 56 to 59
  (`<c-breadcrumbs :crumbs="breadcrumbs" />`, plain full-page anchors with no `hx_target`, because "the
  panel framework's HTMX target `#main-content` does not exist on this standalone page"). The hero is
  deliberately close under the crumbs (`pt-2 lg:pt-2`; "oversized white band" comment, lines 50 to 52), so
  swapping the crumb row for a Back link changes that spacing rationale.
- `spec_dd/3. done/2026-09-19_17:02_course-prices/2. plan.md` line 22 passes the `breadcrumbs` object
  to `<c-breadcrumbs>` in `course_detail.html` (the pattern the view builds).
- Entry points to the details page were widened by
  `spec_dd/3. done/2026-07-17_14:02_course-details-page-accessable-to-registered-learners/` (a "Details"
  link on every dashboard card and catalogue row in every state, and the player's first crumb repointed
  to the details page). Its research (`research_course_details_entry_points.md`) cited NN/g that
  "breadcrumbs reflect the information hierarchy, not session/browsing history (i.e., not 'back to
  whatever page you came from')", and Moodle's convention. That is the exact tension in the idea: a
  hierarchy-based crumb ("All courses") is surprising when the learner arrived from the dashboard.
  The idea reverses nothing in that spec: the player breadcrumb (course title crumb to the details page)
  must stay, and the player breadcrumb test (`test_resume_and_redirect.py::test_breadcrumb_first_crumb_links_to_item_one_not_course_home`
  was rewritten for it) is a different template (`partials/player_breadcrumbs.html`).
- The details page is also the **shareable URL**, and the product docs say so: the player's first crumb
  goes to the detail page and "this is also how a learner shares the course"
  (`docs/product/learner-experience.md` line 229). A visitor can land on the details page from a shared
  link or search (anonymous too; it is publicly accessible and indexed with `/courses/<slug>/detail/`).
  A Back link with no history context needs a defined target for a direct landing (see Open questions).
- Error pages: `spec_dd/3. done/2026-09-06_11:53_error-pages/research_error_page_ux.md` cites GOV.UK
  advising against breadcrumbs and back links on error pages. That is unrelated to the detail page but is
  the repo's existing evidence that a "back" affordance must always resolve to a real route.

No QA bug was ever filed against the detail page breadcrumbs. Tests: the details page's SEO tests mention
breadcrumb (`learner_interface` tests grep hit "only unrelated hits like SEO/breadcrumb tests",
`error-pages/research_error_states_design.md` line 138); the plan should grep
`freedom_ls/learner_interface/tests` for `Breadcrumb` before removing the nav, since SEO/JSON-LD
`BreadcrumbList` output might share the context object.

Open design points raised by prior art: a literal browser-history Back (`history.back()`) is a JS-only
control and breaks for direct landings; a server-computed target (HTTP `Referer` or `?next=`) is
fragile (Referer may be stripped). `docs/product/learner-experience.md` documents the dashboard "Details"
link as "a consistent way back to the overview", i.e. the details page is positioned as the overview,
with the dashboard as its parent in the learner's mental model.

## Part 3: "Home"/"Dashboard" in the mobile hamburger menu

See headline finding 1. History:

- `spec_dd/3. done/2026-03-10_21:13_mobile-responsiveness-audit/` (idea, spec, plan, research, QA):
  scoped to the educator sidebar and general layout, not the learner header. Its research
  (`research_mobile_lms_best_practices.md`, line 16) recommends "hamburger menu for secondary navigation
  items; keep the primary items (3 to 5 max) always visible". The learner header was out of focus.
- `spec_dd/3. done/2026-03-16_15:51_bugfix-expandable -sidebar-button-jumps-around/` is the educator
  sidebar toggle (the one actual hamburger icon), not the learner header.
- `spec_dd/3. done/2026-09-27_07:08_more-prominent-signup-button/qa_report.md`: header controls 40px
  tall at 375px; login/sign-up are inline in the header for anonymous visitors.
- Product doc: `docs/product/learner-experience.md` line 51 describes only Log in / Sign up in the
  header for anonymous users; nothing documents a mobile menu.
- Unrelated hamburger-like control: the course-player TOC (`research ... testing-best-practice-phase-4`
  QA: "TOC sidebar collapses behind a hamburger-style toggle on the topic page"). That belongs to the
  player shell, not the site header.

## Part 4: "My Applications" panel on the dashboard

History (name in code and docs is **Your applications**, not "My Applications"):

- Built by `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/` (spec section on
  `get_dashboard_contributions` around line 533; plan Task B.6 lines 579 to 609). Decision recorded
  there: the panel is the applications backend's own partial
  (`freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html`),
  rendered generically by `learner_interface` via `render_to_string`, which "never reads context keys and
  never imports `course_applications`" (spec "structure-review resolution"; plan line 569 to 571). This
  is the seam to preserve. The better-dashboard spec explicitly left it alone: "`get_dashboard_contributions`
  ... hands back pre-rendered HTML above the whole course list ... so the view cannot order, page or
  deduplicate what is inside it. It stays where it is" (better-learner-dashboard spec, "Scope").
  Its QA there (6-23 `qa_report.md` Test 4, screenshot `desktop_4_dashboard_applications_panel.png`)
  passed.
- Extended by `spec_dd/3. done/2026-10-24_06:02_anon-application-improvements/` (spec lines 171 to 195,
  223 to 273): added `get_dashboard_contributions_for_request(request)`, so an anonymous session sees its
  own drafts in the panel, with **no name or email in the page**; the view guards the panel with a request
  based hook. QA (all pass, `qa_report.md` 2.1, 5.1, 5.3, 7.4): signed-in learner sees Incomplete rows
  with Continue application; anonymous session with two drafts gets both rows newest first; after
  submitting the first course only the second remains; at desktop the heading and rows line up (x=352).
  Pass-through for wrapper backends exists (`freedom_ls/course_access/backends.py` lines 493 to 501), and
  `spec` line 253 warns any backend overriding `get_dashboard_contributions` must also override the
  request-aware method.
- Rows today: submitted = icon + linked course title + "Pending review"; incomplete = linked title +
  warning chip "Incomplete" + "Finish your application to have it reviewed." + "Continue application"
  button with an `sr-only` course name (template read above). Tests that pin the strings:
  `freedom_ls/learner_interface/tests/views/test_course_listing.py` lines ~1813, 1856, 1871 ("Your
  applications" present/absent), `freedom_ls/learner_interface/tests/views/test_course_access.py` section
  5, `freedom_ls/course_applications/tests/test_backends.py` (lines 376 to 440, 531 to 540, 778 to 863),
  `freedom_ls/course_applications/tests/playwright/test_application_form_flow.py` line 69
  (`get_by_role("heading", name="Your applications")`).
- Product doc: `docs/product/learner-experience.md` line 49 (and 31 for anonymous) with screenshot
  `screenshots/learner_dashboard_applications.png`.
- Next work already queued that touches the same seam: `spec_dd/1. next/multi-step-course-applications/idea.md`,
  `spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md` line 229 ("Dashboard
  reachability is unchanged: still the base spec's `get_dashboard_contributions` panel"), and
  `spec_dd/1. next/test-organisation-and-hygene-7-course-access-and-applications/idea.md`. Those treat
  the seam as fixed; changing how the panel is paged or rendered affects them.

Constraint for "allow paging" (idea): the section paging machinery is built around dashboard `Section`
data (`freedom_ls/learner_interface/dashboard_sections.py`, `views.py` ~line 633) and an htmx request
that "builds only the requested section". The contribution is opaque HTML. Options for the spec are to
(a) page inside `course_applications` with its own `page_applications` query parameter and htmx target
following the same conventions (real `href` + `hx-get`, no URL push, `aria-disabled` arrows, unique nav
label, OOB status region), or (b) extend `DashboardContribution` so the backend hands data and the
dashboard pages it. Option (b) crosses the seam the earlier specs protected. Whatever the choice, prior
decisions that carry over: both arrows always rendered; swap boundary below the `<h2>`; `Paginator.get_page()`
clamping; unknown `page_*` parameters ignored; 3 per page unless the spec says otherwise; and anonymous
drafts must still show no name/email.

Design reference: `spec_dd/2. in progress/learner-facing-ux-refinements/design.md` (registered Claude
Design) governs the visuals; the idea says "no highlighted application cards" and "no all applications
page".

## Elsewhere: documented outcomes of similar changes

Evidence is thin and mostly qualitative; no A/B results specific to breadcrumbs-vs-Back-link or to
moving pagination controls were found.

- **Breadcrumbs vs Back (secondary sources).** One roundup cites an unnamed study with breadcrumbs used
  about 6% of the time versus 31% for the browser Back button, and Nielsen's remark that breadcrumbs
  never cause problems in testing but are often overlooked; I could not confirm the study is NN/g's.
  Breadcrumbs jump several levels, a Back arrow steps one screen; breadcrumbs cost horizontal space on
  small screens, and a single "back one level" crumb is recommended as the minimum on mobile. IxDF argues
  history-trail breadcrumbs help little for visitors who land directly on a deep page. Baymard: users
  expect Back to return them to the page they perceive as previous, which sites often do not provide.
  This supports the idea's diagnosis (the surprise is a hierarchy crumb on a page entered from elsewhere)
  but also the direct-landing risk.
- **NN/g on breadcrumbs** is already cited in-repo: breadcrumbs reflect hierarchy, not browsing history
  (`research_course_details_entry_points.md`, 2026-07-17 spec). A Back link is therefore a different
  affordance from a breadcrumb and needs a deterministic target for direct landings.
- **Hamburger menus and Home.** NN/g's quantitative study (179 participants, 6 sites) found hidden
  navigation less discoverable (summaries: about 20% lower discoverability, tasks 39% slower on desktop,
  15% slower on mobile; the mobile penalty is smaller than desktop). Secondary guidance says primary
  destinations should stay visible and hamburgers suit secondary items. No study found on a Home item
  inside a hamburger specifically, so a Home item in a menu is an inference-only improvement; logo-as-home
  already exists in the header (verify at plan time). The repo already cites the same NN/g article in
  `research_kebab_overflow_menu_ux.md` (2026-07-17 spec): hidden/overflow navigation was used by 27%
  versus 48% for visible navigation.
- **Cards vs rows on mobile.** Vendor docs distinguish a vertical list of full-width cards (phones,
  tablets) from a horizontal card grid; learning platforms commonly offer a list view with one course per
  line. A Canvas community thread complains that a two-column card dashboard turned into a single column
  of thin cards requiring more scrolling, which is a caution that compact rows must not become sparse
  tall rows. A HubSpot course-listing theme defaults to 8 per page. No source found that evaluates
  pagination at the top versus the bottom of a mobile list; the idea's top-controls layout is therefore
  untested externally. In-repo precedent: the educator `<c-pagination>` mobile layout is Previous /
  "Page X of Y" / Next (`research_dashboard_pagination.md` section 1).
- **Baymard/NN/g on pagination** are in `research_dashboard_pagination.md` (references there): load-more
  beats pagination for scanning many products, but a dashboard is a launchpad with the catalogue as the
  escape hatch, which is why next/previous plus a stated count plus "Browse all" was accepted.

## Open questions this research leaves for the spec

1. Does "mobile hamburger menu" mean the avatar dropdown? What does an anonymous visitor on mobile get?
2. Back link target for a direct landing (shared link, search, anonymous): history, dashboard, or the
   catalogue? And is it a server-side or JS-driven link (no-JS must work, per the house progressive
   enhancement convention)?
3. Compact rows: all sections or categories only; replace the card at `<lg` by CSS or a second template;
   keep page size 3 (orphan card on a 2-column tablet disappears once rows are single-column).
4. Applications paging: where the paging code lives given the `course_applications`/`learner_interface`
   seam, and the page size.
5. Which of the string-pinning tests above are rewritten rather than deleted.

## References

- LogRocket, Breadcrumbs vs back arrow UX best practices: https://blog.logrocket.com/ux-design/breadcrumbs-vs-back-arrow-ux-best-practices
- Baymard, Mobile design limitations (Back button expectations): https://baymard.com/blog/mobile-design-limitations
- IxDF, Mobile breadcrumbs: https://ixdf.org/literature/article/mobile-breadcrumbs
- NN/g, Hamburger menus and hidden navigation hurt UX metrics: https://www.nngroup.com/articles/hamburger-menus/
- NN/g, Breadcrumbs: 11 design guidelines (cited in repo research): https://www.nngroup.com/articles/breadcrumbs/
- Smart Insights, Are hamburger menus good for UX: https://www.smartinsights.com/digital-marketing-strategy/are-hamburger-menus-hidden-navigation-good-for-ux/
- Canvas community, mobile dashboard card view complaint: https://community.canvaslms.com:443/t5/Canvas-Mobile-Forum/Canvas-mobile-dashboard-card-view/td-p/507695
- Harmonize Learning, Grid vs list view: https://help.harmonizelearning.com/hc/en-us/articles/15800816895117
- Lynton, HubSpot course listing section (8 per page default): https://www.lyntonweb.com/hubspot-cms-themes/rubric/sections/course-listing/

status: ok
