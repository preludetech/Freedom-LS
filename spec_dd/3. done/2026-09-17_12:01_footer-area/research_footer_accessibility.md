# Research: accessibility and HTML semantics of a site footer

Scope: a `{% block footer %}` added to `freedom_ls/base/templates/_base.html` after `</main>`
(currently line 117, before the debug badge), rendering `partials/footer.html`, shipping a
minimal copyright line and legal links, overridable by downstream projects.

## 1. `<footer>` and the `contentinfo` landmark

- The HTML footer element maps to the `contentinfo` ARIA landmark **only when its nearest
  ancestor sectioning context is `<body>`** — i.e. it is not a descendant of `<article>`,
  `<aside>`, `<main>`, `<nav>`, `<section>`, or an element with role `article`,
  `complementary`, `main`, `navigation`, or `region`. Nested in any of those, its implicit
  role is `generic` and it becomes a section-level footer, not a page landmark.
  [MDN: `<footer>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/footer),
  [MDN: contentinfo role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/contentinfo_role),
  [ARIA APG: Landmark Regions](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/).
- **This is exactly why placement outside `<main>` matters for FLS.** The proposed insertion
  point — a sibling of `<main>`, after `</main>`, both direct children of `<body>` — is the
  correct place for the landmark to register. If the footer were placed inside
  `{% block extra_body %}` (which is nested inside `<main>` in `_base.html:106-117`), it would
  render as a `generic` region with no landmark at all, silently defeating the intent.
- A page should carry **exactly one top-level `contentinfo` landmark**. Two `<footer>` elements
  that are both direct-`<body>`-descendants produce two `contentinfo` landmarks, which APG
  flags as needing unique labels to be told apart — effectively a defect for a "the" footer.
  This is a real risk for FLS specifically: `_exam_runner_base.html` overrides
  `{% block header %}` to empty ("runner owns its own bar") but does **not** override
  `{% block footer %}`, and the runner's child template
  (`course_applications/templates/course_applications/form_page.html` and the quiz runner)
  overrides `{% block body %}` wholesale with its own sticky bottom bar
  (`learner_interface/templates/learner_interface/_exam_runner_base.html:12`, "top bar,
  scrollable body, sticky footer"). If that runner-owned sticky bar is itself marked up as a
  `<footer>` (even though it sits inside `<main>`, so it would be `generic`, not `contentinfo` —
  see point above), that's fine; but if a future runner variant ever moves its bar outside
  `<main>` it would create a second `contentinfo`. Worth a spec note: the runner's sticky
  action bar is **not** a page footer and must not be marked up or labelled as one.
  [APG: Landmark Regions](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/).
- **Explicit `role="contentinfo"` in 2026**: current MDN/APG guidance still shows an explicit
  `role="contentinfo"` example, historically justified by pre-Safari-13 VoiceOver not exposing
  the implicit role from `<footer>`. That Safari version is long obsolete (Safari 13 shipped in
  2019), so for a project targeting current browsers the implicit mapping is reliable and the
  explicit role is redundant — some validators (e.g. Rocket Validator's HTML checker) now flag
  it as an unnecessary/redundant ARIA role. Net: don't add `role="contentinfo"` to FLS's
  `<footer>` unless a specific legacy-AT support requirement surfaces.
  [MDN: `<footer>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/footer),
  [Rocket Validator: contentinfo role unnecessary](https://rocketvalidator.com/html-validation/the-contentinfo-role-is-unnecessary-for-element-footer).

## 2. Skip links and bypass blocks (WCAG 2.4.1)

- **FLS today has no skip link and no other bypass mechanism.** Checked
  `freedom_ls/base/templates/_base.html` (body starts straight into
  `{% block header %}` → `partials/header_bar.html`, no skip-link anchor before it) and
  `freedom_ls/base/templates/partials/header_bar.html` (a `<header>` with a logo link, an
  `<h1>`, and one unlabelled `<nav>` for the user menu/login prompt — no `href="#main"` skip
  link, no `id` on `<main>` to target). This is a pre-existing WCAG 2.4.1 (Level A) gap
  independent of the footer.
  [Understanding SC 2.4.1](https://www.w3.org/TR/UNDERSTANDING-WCAG20/navigation-mechanisms-skip.html).
- **Adding a footer makes this gap marginally worse, not better**, because it adds one more
  block of repeated, non-primary content that every keyboard/screen-reader user must traverse
  (or explicitly navigate past via landmark/heading navigation) on every page. It does not, by
  itself, require a *new* bypass mechanism — WCAG 2.4.1 is about letting users skip *past*
  repeated blocks to reach primary content, and a footer sits *after* `<main>`, so it is never
  "in the way" of reaching content. It does raise the value of finally adding the header's own
  skip-to-`<main>` link, since the footer adds one more reason a keyboard user would want to
  jump straight past all chrome.
  [WCAG.com: 2.4.1 Bypass Blocks](https://www.wcag.com/developers/2-4-1-bypass-blocks/).
- **No "skip to footer" pattern is standard or recommended.** Current guidance is that
  skip/quick-access links exist to move *forward* past repeated leading content, are expected
  at the very start of the page (first focusable element), and should not be duplicated
  elsewhere. A footer does not need its own inbound skip link.
  [Orange a11y guidelines: skip links best practices](https://a11y-guidelines.orange.com/en/articles/skip-links-best-practices/).
- **"Back to top"** is a separate, optional pattern (an outbound link, usually at the end of
  `<main>` or inside the footer, that returns focus/scroll to the top of the page) — not a
  requirement of 2.4.1, and not something FLS's spec needs to add for a minimal copyright/legal
  footer; flagging it here only because it's a common footer-adjacent pattern the spec should
  consciously *not* pull in scope for a "minimal" footer.
  [UX Patterns for Developers: Back to Top](https://uxpatterns.dev/patterns/navigation/back-to-top),
  [DigitalA11Y: Scroll to Top, where should focus land?](https://www.digitala11y.com/scroll-to-top-where-should-the-focus-land/).

## 3. WCAG 2.2 success criteria a footer commonly touches

| SC | What it requires | What would make FLS's minimal footer pass/fail |
|---|---|---|
| **2.4.1 Bypass Blocks** (A) | A mechanism to skip repeated blocks of content. | Footer itself doesn't need a bypass mechanism (see §2) since it trails `<main>`; but it's a second data point for finally adding the missing skip-to-main link in `header_bar.html`. [Understanding 2.4.1](https://www.w3.org/TR/UNDERSTANDING-WCAG20/navigation-mechanisms-skip.html) |
| **3.2.3 Consistent Navigation** (AA) | Navigational mechanisms repeated on multiple pages occur in the same relative order each time they appear. | Pass condition: the footer's link order (e.g. Privacy, Terms, Contact) must not be re-ordered per page/app. Because `partials/footer.html` is one include rendered by every page through `_base.html`, this is naturally satisfied unless a downstream override reorders links conditionally per page — worth calling out as a constraint on any per-context customization. [Silktide: 3.2.3](https://silktide.com/accessibility-guide/the-wcag-standard/3-2/predictable/3-2-3-consistent-navigation/) |
| **3.2.4 Consistent Identification** (AA) | Components with the same functionality are identified consistently (same label/icon) across pages. | Pass condition: if a "Privacy Policy" link appears in the footer and *also* elsewhere (e.g. a signup form's consent text), both must use the same accessible name — don't let the footer say "Privacy" while a form says "Privacy Policy" for the same target. |
| **3.2.6 Consistent Help** (A, new in 2.2) | Where a help mechanism (contact details, self-help/FAQ, human/automated contact) exists and repeats across pages, it appears in the same relative order across pages. | A footer is the textbook home for this: if FLS's footer carries a "Contact" or "Support" link, it must appear at the same relative position in the footer on every page it's present, and must not be Emailed-vs-linked inconsistently. If FLS's *minimal* footer is only copyright + legal links (no help/contact mechanism), 3.2.6 is simply not triggered — but the moment a downstream project adds a help link to their footer override, this SC applies to it. [WCAG.com: 3.2.6](https://www.wcag.com/developers/3-2-6-consistent-help-level-a/), [BOIA: Consistent Help](https://www.boia.org/blog/consistent-help-tips-for-meeting-wcag-success-criterion-3-2-6) |
| **1.4.3 Contrast (Minimum)** (AA) | Text contrast ≥ 4.5:1 (≥ 3:1 for large text ~18pt/24px regular or ~14pt/18.66px bold) against its background. | **No footer exception exists in WCAG for "muted" styling.** A common failure mode is exactly what a "minimal legal footer" invites: light-gray copyright/link text (`text-muted`-style tokens) that looks intentionally de-emphasized but drops under 4.5:1 — e.g. `#999` on white is ~2.85:1 and fails outright. FLS's existing `text-muted` token (used elsewhere, e.g. in `_base_interface.html`'s breadcrumb/panel toggle styling) must be checked against its actual background in the footer, not assumed compliant because it "looks like secondary text elsewhere." [tabnav: 1.4.3](https://tabnav.com/academy/wcag/success-criterion-1.4.3) |
| **1.4.11 Non-text Contrast** (AA) | Contrast ≥ 3:1 for UI component boundaries/states and graphical objects required to understand content (not text). | Applies if the footer has any visible interactive-state affordance that isn't text — e.g. a border/divider separating footer from `<main>`, or a focus ring — those graphical elements need ≥3:1 against adjacent colors. A plain text-only footer with only `1.4.3`-governed link text mostly sidesteps this, except for the focus indicator itself (see 2.4.7). |
| **2.4.7 Focus Visible** (AA) | Any UI that supports keyboard operation has a mode where the keyboard focus indicator is visible. | Every footer link must show a visible focus outline. Failure mode specifically relevant to a footer: a focus ring tuned for a light `<main>` background can become invisible against a darker/differently-colored footer background — footers are disproportionately represented in WebAIM's audits of missing/low-contrast focus indicators. Needs its own contrast check against the footer's actual background, not an assumption that the site-wide focus ring "just works" there. [getstark: Focus Visible](https://www.getstark.co/wcag-explained/operable/navigable/focus-visible/) |
| **2.5.8 Target Size (Minimum)** (AA, new in 2.2) | Pointer targets ≥ 24×24 CSS px, unless Spacing (≥24px to the next target), Inline (target sits within a sentence/block of text), Equivalent, User Agent, or Essential exceptions apply. | Footer links are very commonly **inline text links** (e.g. "Privacy · Terms · Contact" in a running line) — the **Inline exception** typically exempts them outright regardless of the rendered link's pixel box, because the target is "in a sentence or block of text." If FLS instead renders footer links as small standalone tap targets (icons, pill buttons) rather than inline text, they lose that exemption and must independently satisfy the 24×24px/Spacing rule — this is a concrete design-time choice the footer spec should decide explicitly rather than leave implicit. [WCAG 2.2 22aa.org: Target Size](https://wcag22aa.org/new-criteria/target-size/) |

## 4. Footer link semantics — `<nav>` wrapping and labelling

- ARIA APG guidance: when there are **multiple `<nav>` regions** on a page, each should have a
  distinguishing accessible name (`aria-label` or `aria-labelledby`) unless the navs contain
  *identical* link sets, in which case the same label is fine. This lets AT users pick the
  right nav from a landmark list instead of hitting two indistinguishable "navigation" regions.
  [ARIA APG: Landmark Regions](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/).
- **FLS already follows this convention everywhere except the primary header nav.** Every
  secondary `<nav>` in the codebase is labelled: `aria-label="Application pages"`
  (`course_applications/templates/course_applications/form_page.html:16`),
  `aria-label="Breadcrumb"` (`base/templates/cotton/breadcrumbs.html:36` and
  `learner_interface/templates/learner_interface/partials/player_breadcrumbs.html:19`),
  `aria-label="Course outline"`
  (`learner_interface/templates/learner_interface/partials/course_minimal_toc.html:67`),
  `aria-label="Sections"` (`panel_framework/templates/panel_framework/partials/sidebar_nav.html:1`),
  and the pagination nav takes a caller-supplied label
  (`learner_interface/templates/cotton/course-section-pagination.html:18`). The **one exception
  is the primary header nav itself** — `<nav class="flex-shrink-0 ml-2 sm:ml-4">` in
  `base/templates/partials/header_bar.html:18` has no `aria-label` at all.
- **Implication for the footer:** whether a footer's link group should be wrapped in `<nav>`
  depends on whether it's genuinely a navigation set (multiple links to other pages) versus a
  single inline legal statement. For FLS's stated "copyright line + links to legal documents"
  footer, that is a small link set — APG-consistent practice (and FLS's own established
  pattern) would wrap it in `<nav aria-label="…">` (e.g. `aria-label="Legal"` or
  `aria-label="Footer"`) so it registers as a distinct landmark from the header's nav. The
  **common failure this avoids** is exactly FLS's current header-nav gap: two `<nav>` elements
  on a page with no `aria-label` on either are indistinguishable in a landmarks list, which is
  the textbook "unlabelled second nav" failure APG warns about. Since the header's own nav is
  currently unlabelled, adding an *unlabelled* footer nav would recreate that exact problem a
  second time, whereas labelling the footer nav (even though the header nav still lacks one)
  at least makes the footer nav individually identifiable and stops the count of anonymous navs
  from growing.
  [ARIA APG: Landmark Regions](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/).

## 5. HTMX implications

- **Course-player boosted navigation never touches the footer, by construction.**
  `learner_interface/templates/cotton/player-nav.html` wraps Previous/Next/mark-complete/form
  controls in `hx-boost="true" hx-target="#interface-main" hx-select="#interface-main"
  hx-swap="outerHTML show:window:top" hx-select-oob="#course-toc-region"`. `#interface-main` is
  the content column inside `_base_interface.html`'s sidebar grid
  (`base/templates/_base_interface.html:207`), itself inside `{% block content %}` inside
  `<main>`. A footer placed as a sibling of `<main>` in `_base.html` is outside both the
  `hx-select` scope and the `hx-target`, so a boosted player navigation **never re-fetches,
  re-parses, or re-inserts the footer** — it is simply never part of any swap.
- **`hx-preserve` is not applicable to the footer.** `hx-preserve` only matters for elements
  *inside* a swap target whose local state (focus, video playback, form input) would otherwise
  be lost on re-render. Since the footer is never inside the swapped subtree, there is nothing
  for `hx-preserve` to protect — it would be a no-op if applied to the footer, and adding it
  would be misleading (implies the footer is at risk of being swapped, which it structurally
  cannot be given `hx-select="#interface-main"`).
  [htmx docs: hx-preserve](https://htmx.org/attributes/hx-preserve/).
- **Focus management is the real gap, but it's pre-existing and site-wide, not footer-specific.**
  `hx-swap="outerHTML show:window:top"` scrolls the *viewport* to the top of `window` after a
  swap, but htmx does not move *keyboard focus* anywhere by default — a known, general htmx
  accessibility gap (screen reader/keyboard position is not managed across a boosted
  navigation). Because a footer is never part of the swap, this doesn't change the footer's own
  risk profile; but it is a reason a footer landmark sitting outside the swap region needs
  **no additional treatment** (no `aria-live`, no focus-reset) — the accessibility work needed
  here is entirely about where focus lands *inside* `#interface-main` after a swap, which is out
  of scope for a footer change and belongs to the player-nav's own accessibility backlog, not
  this spec. [Wagtail: htmx accessibility gaps](https://wagtail.org/blog/htmx-accessibility-gaps-data-and-recommendations/).
- Checked `freedom_ls/base/static/base/js/interface-swap-fallback.js`: it only guards against a
  boosted response missing `id="interface-main"` (falls back to a full navigation via
  `window.location.href`) — it has no bearing on the footer, confirming there is no existing
  swap-adjacent machinery the footer would need to plug into or be exempted from.

## 6. Print and PDF

- FLS's two existing "footer" surfaces that render on paper/PDF are **not web pages and don't
  extend `_base.html`**, so neither is a precedent for `@media print` handling of the *web*
  footer:
  - `freedom_ls/reports/templates/reports/report.html` is WeasyPrint source HTML for a
    generated PDF report, explicitly documented as "never served to a browser — no site base
    template, no cotton components" (line 12). Its `.footer-identity` / `.footer-powered-by`
    divs are WeasyPrint running-element margin boxes (page-footer content repeated per printed
    page by WeasyPrint's own print CSS), unrelated to an HTML `<footer>` landmark and
    irrelevant to a browser's print stylesheet.
  - The email base templates (`freedom_ls/accounts/templates/emails/base_email.html`,
    `emails/includes/footer_links.html`) render a standalone HTML-email document (table-based
    layout, premailer-inlined styles) that is never routed through `_base.html` either.
- **No `@media print` rule exists anywhere in FLS today** (checked `freedom_ls/` for `@media
  print` — no matches), so there is no existing print stylesheet that would already pick up a
  new site footer one way or the other; this would be new surface area, not an extension of
  something already there.
- Because neither existing "footer" is reachable from a browser print of a normal FLS page, the
  question of whether the new web footer should suppress itself on print
  (`@media print { footer { display: none; } }`) is a genuinely open design question the spec
  should decide rather than infer from precedent — there's no existing FLS convention either
  way. General web practice avoids printing site chrome (nav bars, footers with unclickable
  links) on every page of a multi-page print job, since a copyright/legal-links block repeated
  at the bottom of every printed page adds no value once the links can't be clicked; but this
  project has made no commitment on this either way, so it should be called out explicitly
  rather than assumed.

## Checkable accessibility requirements for the footer (with references)

1. The footer must render as a **direct child of `<body>`** (sibling of `<main>`, not nested
   inside it or inside `<article>/<aside>/<nav>/<section>`) so `<footer>` maps to the
   `contentinfo` landmark implicitly. — [MDN footer](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/footer), [ARIA APG Landmarks](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/)
2. There must be **exactly one `contentinfo` landmark per page**; the exam/form runner's own
   sticky bottom bar (`_exam_runner_base.html`) must not be marked up as a second `<footer>`
   that is itself a direct `<body>` child. — [ARIA APG Landmarks](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/)
3. Do **not** add `role="contentinfo"` explicitly — the implicit role from `<footer>` is
   sufficient for current browsers; an explicit role is redundant/flaggable in 2026. —
   [MDN footer](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/footer), [Rocket Validator](https://rocketvalidator.com/html-validation/the-contentinfo-role-is-unnecessary-for-element-footer)
4. If the footer's links are wrapped in `<nav>`, that `<nav>` must carry a distinguishing
   `aria-label` (e.g. `"Legal"` or `"Footer"`) — matching FLS's existing convention on every
   other secondary `<nav>` in the codebase except the still-unlabelled header nav. —
   [ARIA APG Landmarks](https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/); FLS precedent: `base/templates/cotton/breadcrumbs.html:36`, `learner_interface/templates/learner_interface/partials/course_minimal_toc.html:67`
5. Footer link order must stay **consistent across every page it appears on** (WCAG 3.2.3), and
   any link that duplicates a control elsewhere on the site (e.g. "Privacy Policy") must use the
   **same accessible name** everywhere (WCAG 3.2.4). — [Silktide 3.2.3](https://silktide.com/accessibility-guide/the-wcag-standard/3-2/predictable/3-2-3-consistent-navigation/)
6. If any downstream footer override adds a help/contact/support mechanism, it must appear in
   the same relative position in the footer on every page that includes it (WCAG 3.2.6, new in
   2.2). Not triggered by FLS's own minimal copyright+legal-links footer, but a constraint to
   flag for downstream customizers. — [WCAG.com 3.2.6](https://www.wcag.com/developers/3-2-6-consistent-help-level-a/)
7. Footer text and link color must independently meet **4.5:1 contrast** (3:1 if ≥ large-text
   size) against the *footer's actual background* — do not assume an existing `text-muted`
   token passes just because it's used as secondary text elsewhere (WCAG 1.4.3). —
   [tabnav 1.4.3](https://tabnav.com/academy/wcag/success-criterion-1.4.3)
8. The footer's focus indicator (on its links) must independently meet visibility/contrast
   requirements against the footer's own background — a site-wide focus ring tuned for `<main>`
   can become invisible on a differently-colored footer (WCAG 2.4.7). —
   [getstark Focus Visible](https://www.getstark.co/wcag-explained/operable/navigable/focus-visible/)
9. Decide explicitly whether footer links render as **inline text** (qualifies for the Inline
   exception to 2.5.8 Target Size) or as standalone tap targets (must independently hit 24×24px
   or 24px spacing) — don't leave this implicit in the visual design. —
   [WCAG 2.2 Target Size](https://wcag22aa.org/new-criteria/target-size/)
10. The footer needs **no `hx-preserve`, no `aria-live`, and no boosted-swap-specific
    treatment**: it sits outside `hx-select="#interface-main"`/`hx-target="#interface-main"` in
    every course-player boosted navigation and is never part of a swap. — codebase:
    `learner_interface/templates/cotton/player-nav.html`, `base/templates/_base_interface.html:207`; htmx docs: [hx-preserve](https://htmx.org/attributes/hx-preserve/)
11. Adding the footer does not itself require a skip link, but it is one more argument (not a
    hard requirement) for eventually closing FLS's pre-existing gap: no skip-to-`<main>` link
    exists anywhere in `_base.html` or `header_bar.html` today (WCAG 2.4.1, Level A — already
    failing, independent of this feature). — [Understanding SC 2.4.1](https://www.w3.org/TR/UNDERSTANDING-WCAG20/navigation-mechanisms-skip.html)
12. Whether the footer should be hidden via `@media print` is an **open decision with no
    existing FLS precedent** to follow — the PDF report and HTML email templates are separate,
    non-`_base.html` documents and don't establish a pattern for the web shell's print styles;
    no `@media print` rule exists anywhere in FLS today. — codebase: `freedom_ls/reports/templates/reports/report.html:12`, `freedom_ls/accounts/templates/emails/base_email.html`

## Flags: what FLS already gets wrong today that a footer would compound

- **No skip link anywhere in the chrome** (`_base.html`, `header_bar.html`) — pre-existing
  WCAG 2.4.1 gap. A footer doesn't cause this, but it is one more block of repeated chrome a
  keyboard user has to traverse without a bypass mechanism, and raises the practical case for
  fixing it.
- **The primary header `<nav>` has no `aria-label`**
  (`base/templates/partials/header_bar.html:18`), the only unlabelled `<nav>` in the codebase.
  If the footer's link group is also wrapped in an unlabelled `<nav>`, FLS would have two
  indistinguishable navigation landmarks — the exact APG-documented failure mode. Labelling the
  new footer nav avoids adding a *second* instance of this problem, though the header nav
  itself remains unfixed unless separately addressed.

---
status: ok
reason: Completed all six research areas (contentinfo landmark scoping, skip links/bypass blocks, WCAG 2.2 footer-relevant SCs, footer nav labelling, HTMX boosted-swap implications, print/PDF precedent) with FLS codebase inspection (_base.html, header_bar.html, _base_interface.html, _exam_runner_base.html, player-nav.html, interface-swap-fallback.js, reports/report.html, emails/base_email.html) and web-sourced citations (MDN, ARIA APG, WCAG.com/W3C Understanding docs, htmx docs). Produced a 12-item checkable requirements list plus two flags on pre-existing FLS gaps (missing skip link, unlabelled header nav) that a footer would compound.
