# Research: Catalogue-grouping UX — duplicate cards, coming-soon labelling, "browse all", and repeated-link accessibility

Scope: external web research into (a) showing the same catalogue item in two groupings on one
browse surface at once, (b) labelling unreleased/"coming soon" items mixed with available ones,
(c) the "see all"/"browse all" affordance on a card row, and (d) the accessibility consequence of
rendering the same link twice on a page — checked lightly against the FreedomLS (FLS) learner
dashboard, which is adding both a duplicate-card situation (a `Course` in a dashboard-visible
`CourseCategory` now appears in both its category section and "Coming soon") and a "Browse all
courses" link to every section except "In progress" and "Learning history".

The decision to duplicate the card and add the link is already made. This document researches the
pitfalls and mitigations, not whether to do it.

---

## 1. Deliberate duplication of an item across two groupings on one browse surface

**Web finding.** Streaming and storefront catalogues do this routinely, and it is understood as a
byproduct of algorithmic, per-shelf curation rather than a bug: Netflix's Personalized Video Ranker
orders the *entire* catalogue independently for every genre/mood row shown to a member, so the same
title can legitimately surface in more than one row on the same homepage
([ACM: "The Netflix Recommender System: Algorithms, Business Value, and Innovation"](https://dl.acm.org/doi/pdf/10.1145/2843948)).

**Web finding — the reputational risk of *unlabelled* duplication.** Commentary on Netflix's UI
specifically frames unexplained repetition as a trust problem, not a neutral one: "Algorithmic
rows, which often repeat the same titles across multiple categories, create the illusion of
infinite content" — the criticism is that removing the one feature that made the repetition
*visible* (A–Z sorting) let Netflix mask how much overlap there really is
([whats-on-netflix.com: "Netflix Quietly Removes A-Z and Other Sorting Filters from Web UI"](https://www.whats-on-netflix.com/news/netflix-quietly-removes-a-z-and-other-sorting-from-web-ui/)).
The lesson for FLS is the inverse of what Netflix is criticised for: duplication reads as
manipulative padding when it is *hidden or unexplained*, and reads as intentional curation when
the reason for the repeat is visible on the item itself. FLS's case is closer to the latter — the
duplicate exists because the course carries a real, disclosed status ("coming soon"), not because
the system is inflating catalogue size — so the mitigation is to keep that reason visible on both
cards, not to hide the duplication.

**Web finding — per-item status as the standard mitigation.** GOV.UK's Design System gives the
general rule practitioners reach for: "Use the Tag component when it's possible for something to
have more than one status and it's useful for the user to know about that status," and to keep the
status vocabulary as small as consistently applied as possible
([GOV.UK Design System: Tag component](https://design-system.service.gov.uk/components/tag/)).
Applied here: a card's status label is what makes a second appearance of the same course legible as
"this is the coming-soon copy of that card" rather than "why is this course listed twice."

**Repo check.** FLS already does this. `course_status_eyebrow.html` is "the single source of truth
for the four course-status labels," rendered on every card, including inside the category grid
(`freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html`).
A `Course` with `visibility == COMING_SOON` gets the same "Coming soon" eyebrow wherever it is
rendered — in its `CourseCategory` section and in the dedicated "Coming soon" section. The eyebrow
partial's own comment cites **WCAG 1.4.1 (Use of Color)**: "the text label is always present; the
icon (and any colour) is reinforcement only — never the sole indicator of state." That satisfies
the per-card mitigation the web research calls for; **no change needed there.**

What the web research adds that is not yet true in FLS: the *group-level* framing that makes a
repeat feel intentional (Netflix's genre row vs. "New releases" row are self-evidently different
lenses on the catalogue) comes from the section heading and, where set, the section description —
`CourseCategory.description` already renders under the category heading
(`course_list.html`, `course-section` partial). That heading + description pairing is the
group-level signal; it already exists and needs no addition. The one new thing this change
introduces is that "Coming soon" the section and a `CourseCategory` section now legitimately show
the *same* card — which is exactly the Netflix-genre-row-plus-New-row shape, and is covered by the
existing per-card eyebrow, so **the recommended mitigation is already in place; treat this as a
confirmation, not a gap.**

---

## 2. Labelling unreleased ("coming soon") items mixed into an available-items row

**Web finding — where the label needs to sit.** E-commerce "coming soon" plugin guidance (a proxy
for common practice, not a research body) is consistent that the badge belongs *on the listing
card itself*, not only on the detail page: "The badge should be displayed over each coming soon
product in shop pages" — i.e., at the point of the wasted click, before the user commits to it
([ecomposer.io: "How to Add a 'Coming Soon' Product on Shopify"](https://ecomposer.io/blogs/shopify-knowledge/add-a-coming-soon-product-on-shopify)).
Steam's own guidance to developers treats "Coming Soon" as a persistent status a title carries from
the moment its store page goes live, specifically so that browsing users see it as unavailable-but-
real rather than a broken link, before a purchase button ever exists
([Steamworks documentation: "Coming Soon"](https://partner.steamgames.com/doc/store/coming_soon)).
Both sources agree: a badge that only shows up after the click (on the detail page) is too late to
save a wasted click — the label has to be visible at the grid/row level, before the click.

**Web finding — group-level signal is not required if the item-level one is reliable.** GOV.UK's
guidance above is explicit that tags are an *item*-level device, and warns against multiplying
statuses "because the harder it is for users to remember them"
([GOV.UK Design System: Tag component](https://design-system.service.gov.uk/components/tag/)).
Nothing in the sources reviewed argues that a per-card badge additionally needs a group-level badge
(e.g. a "some of these aren't out yet" banner on the row) as long as the per-card label is
consistent and applied to every instance of the same status — which is the situation here, since
"Coming soon" already has its own dedicated section as one more disambiguating cue.

**Repo check.** As above, `course_status_eyebrow.html` renders "Coming soon" with a deadline icon
on every card that needs it, on dashboard cards (`with_icon=False`, text-only) and on the
all-courses page rows (`with_icon=True`). It is rendered before the title link in the card's markup
order (`course_card.html`: eyebrow slot, then the title link), which matches the "signal before the
click" finding above. **No change recommended.**

---

## 3. The "see all" / "browse all" link on a card row

**Web finding — the pattern itself.** No single canonical NN/g or Baymard article on link
*placement* for "see all" surfaced in this research pass (search of both sites' public output did
not turn up a dedicated study — noted here as a gap rather than asserted as settled). The searches
did surface the adjacent, well-established finding that filter/scope state is exactly the kind of
context users expect a listing surface to *carry forward*, not discard: Baymard's product-list
research treats "applied filters" as one of the load-bearing elements of a list page precisely
because users rely on the page continuing to reflect the criteria that got them there
([Baymard Institute: "Product List UX Best Practices"](https://baymard.com/blog/current-state-product-list-and-filtering)).

**Web finding — the specific risk of a link that drops context.** General UX/dark-pattern
literature on filtering treats a control that silently discards the user's scoping choice as a
trust break, even short of a "dark pattern" in the manipulative sense: it undermines user control
and creates friction by forcing the user back through irrelevant content
([Medium/Arounda: "Dark Patterns in UX/UI Design and How to Avoid Them"](https://medium.com/@arounda.agency/dark-patterns-in-ux-ui-design-and-how-to-avoid-them-22-examples-964e5cb0eb86);
general filter-UX summary via [searchanise.io: "12 Ecommerce Filter UX Best Practices"](https://searchanise.io/blog/filter-ui/)).
This research pass did not find a source calling a *generic, unfiltered* "see all" a named dark
pattern outright — the closer, better-supported claim is the milder one: a link that promises "more
of this" but delivers "everything" breaks the expectation the row itself set up, and the size of
that break scales with how strongly the row implied a scope (a named category row implies scope
much more strongly than a general "Recommended" or "Available courses" row does).

**Repo check — this is the one place FLS's current build does not fully match the row's own
framing.** `browse_all_url` is set to `reverse("learner_interface:courses")` — the flat, unfiltered
all-courses page — for both the category sections and "Available courses"
(`freedom_ls/learner_interface/views.py:379` and `:408`). The `all_courses` view
(`freedom_ls/learner_interface/views.py:620`) takes no category/filter query parameter; it always
renders the full catalogue via `get_all_courses()`. So a "Browse all courses" link sitting inside,
say, the "Assessment" `CourseCategory` section currently takes the learner to a page with every
course on the site, not more Assessment courses. Per the finding above, this is the sharpest place
for the row's implied scope (a named category) to be broken by the link's actual behaviour.

Two things temper how serious this is for FLS specifically, and both matter for keeping the
recommendation small:
- The button's own label is "Browse all **courses**", not "See more like this" or "More in
  Assessment" — it does not promise a filtered result, it explicitly says "all". That wording
  already does some of the expectation-management work the web sources call for; a learner who
  reads the label before clicking is not misled the way they would be by a vaguer label.
- "Recommended courses" and "Available courses" (the catch-all) are not meaningfully "filterable"
  scopes to begin with, so a flat link is not a broken promise there — the mismatch is specific to
  the `CourseCategory` sections, where the row itself is a named, filterable grouping.

**Recommendation (small, wording-only — no filtering logic proposed here).** Given the label
already says "all" rather than implying continuation of the row's scope, the cheapest mitigation
that fully closes the gap without touching `all_courses`' filtering behaviour is not required for
this change to be honest with the user — the button text already sets the expectation it delivers
on. If a future pass wants to close the gap further (making a category's "Browse all courses" carry
that category as a filter), that is a `some worker/spec elsewhere` sized change to `all_courses`
and its URL, not something to fold into a small-fixes pass — flagging it here as the identified
pitfall, not proposing it as work to do now.

**Brand-voice check.** `claude_plugins/sdd/../fls-dev` brand-guidelines skill
(`.claude/skills/brand-guidelines/SKILL.md`) gives two directly relevant data points:
- Existing FLS copy already uses "Browse courses" / "browse courses" as the catalogue-CTA verb (the
  commented-out button in `in-progress-empty` partial, and the 404 sample copy: "Head back to
  [your dashboard] or [browse courses]"). "Browse all courses" is consistent with that established
  verb — no wording change is indicated by brand voice.
- Voice principle "Direct over diplomatic" and the error-message rule "Name the specific problem"
  argue against a vaguer label like "See all" in favour of the more literal "Browse all courses"
  FLS already uses — the current wording is the more on-brand of the two options research
  surfaced, not less.

---

## 4. Accessibility: the same title-link text appearing twice on the page

**Web finding — the two relevant, differently-scoped WCAG criteria.**
- **SC 2.4.4 Link Purpose (In Context)** (Level A): "The purpose of each link can be determined
  from the link text alone or from the link text together with its programmatically determined
  link context" — context can come from the enclosing sentence, paragraph, list item, table cell,
  *or a preceding heading*
  ([W3C: Understanding SC 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)).
- **SC 2.4.9 Link Purpose (Link Only)** (Level AAA — not the A/AA baseline most projects target,
  cited here because it directly answers the "is duplication itself a problem" question): its
  Understanding page states plainly that "links with the same destination would have the same
  descriptions," and that consistent text for identical destinations is what lets a user predict
  where a link leads when links are read out of context (e.g. a screen reader's list-of-links view)
  ([W3C: Understanding SC 2.4.9](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-link-only.html)).
  In other words: **two links with identical text that go to the same place is the compliant
  case, not the violation** — the violation pattern WCAG actually warns about is identical text
  pointing to *different* places (e.g. ten "Read more" links to ten different articles), which is
  not what happens here since both cards for a coming-soon course link to the same `course_detail`
  URL.
- Related supporting practice: **ARIA11 (Using ARIA landmarks to identify regions of a page)** —
  the working technique for making repeated regions distinguishable is to give each one a unique
  accessible name, "preferably with `aria-labelledby` referencing a visible header," so that a
  repeated `region`/`navigation` landmark is announced with different names each time
  ([W3C: ARIA11 technique](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA11)). This technique
  is documented against **SC 1.3.1 Info and Relationships** and **SC 2.4.1 Bypass Blocks**, not
  against the link-text criteria above — it is about disambiguating the *section*, not the *link*.

**How this resolves for FLS's specific duplicate.** Because both instances of a coming-soon
course's title link point at the same `course_detail` URL (`course_card.html`'s title-link branch:
`coming_soon` falls into the `course_detail` case, same as `not_registered`), the duplication is
the WCAG-compliant case under SC 2.4.9, not the violation case. The genuine, useful disambiguation
work is upstream of the link: each grid is already preceded by an `<h2>` section heading
(`course_list.html`, `section-heading` partial, one per section, with a stable `heading_id`), which
is exactly the "preceding heading" context SC 2.4.4's Understanding page names as sufficient. A
screen-reader user tabbing through headings hears "Assessment" then "Coming soon" before reaching
each respective grid, which is what tells them *which* occurrence of the title they are in.

**Repo check — one gap worth naming, not fixing here.** The section wrapper
(`course-section` partial's outer `<div>`) carries no `role="region"` / `aria-labelledby` pairing
to its own `heading_id`, so the disambiguation currently relies entirely on heading order during
linear/heading-list navigation, not on a landmarks list. That is consistent with WCAG's letter (SC
2.4.4/2.4.9 are already satisfied via the preceding-heading mechanism and identical destination
respectively) but is the thing ARIA11 exists to strengthen for landmark-based navigation. Given the
"small fixes, no redesign" scope of this change, this is a pre-existing structural characteristic
of the dashboard template, not something introduced by the duplicate-card change — flagging it as
background, not as a required fix for this piece of work.

---

## Summary of findings against the two decided changes

| Decided change | Web-sourced pitfall | FLS status |
|---|---|---|
| Coming-soon course shown in both its `CourseCategory` section and "Coming soon" | Unlabelled duplication reads as padding/manipulation ([whats-on-netflix.com](https://www.whats-on-netflix.com/news/netflix-quietly-removes-a-z-and-other-sorting-from-web-ui/)); mitigation is a reliable per-item status label ([GOV.UK Design System](https://design-system.service.gov.uk/components/tag/)) shown before the click ([ecomposer.io](https://ecomposer.io/blogs/shopify-knowledge/add-a-coming-soon-product-on-shopify); [Steamworks](https://partner.steamgames.com/doc/store/coming_soon)) | Already satisfied — `course_status_eyebrow.html` labels every instance identically and up front |
| Duplicate title-link text on one page | Could look like a WCAG link-purpose violation | Not a violation — SC 2.4.9's Understanding page treats identical text at the same destination as the compliant case; SC 2.4.4 is satisfied via each grid's preceding `<h2>` |
| "Browse all courses" added to every section but `CourseCategory` sections' link is unfiltered | A row-scoped "see all" that discards the row's own scope breaks the expectation the row set up (general filter-UX literature: [Baymard](https://baymard.com/blog/current-state-product-list-and-filtering), [Arounda](https://medium.com/@arounda.agency/dark-patterns-in-ux-ui-design-and-how-to-avoid-them-22-examples-964e5cb0eb86)) | Partially mitigated by wording: the button already says "all", not "more like this" — matches existing FLS brand voice/vocabulary. A true per-category filter is out of scope for a small-fixes pass; flagged, not actioned, here |

## References

- [ACM: "The Netflix Recommender System: Algorithms, Business Value, and Innovation"](https://dl.acm.org/doi/pdf/10.1145/2843948)
- [whats-on-netflix.com: "Netflix Quietly Removes A-Z and Other Sorting Filters from Web UI"](https://www.whats-on-netflix.com/news/netflix-quietly-removes-a-z-and-other-sorting-from-web-ui/)
- [GOV.UK Design System: Tag component](https://design-system.service.gov.uk/components/tag/)
- [ecomposer.io: "How to Add a 'Coming Soon' Product on Shopify"](https://ecomposer.io/blogs/shopify-knowledge/add-a-coming-soon-product-on-shopify)
- [Steamworks documentation: "Coming Soon"](https://partner.steamgames.com/doc/store/coming_soon)
- [Baymard Institute: "Product List UX Best Practices 2025"](https://baymard.com/blog/current-state-product-list-and-filtering)
- [Medium/Arounda: "Dark Patterns in UX/UI Design and How to Avoid Them"](https://medium.com/@arounda.agency/dark-patterns-in-ux-ui-design-and-how-to-avoid-them-22-examples-964e5cb0eb86)
- [searchanise.io: "12 Ecommerce Filter UX Best Practices for Shopify Stores"](https://searchanise.io/blog/filter-ui/)
- [W3C: Understanding SC 2.4.4 Link Purpose (In Context)](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- [W3C: Understanding SC 2.4.9 Link Purpose (Link Only)](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-link-only.html)
- [W3C: ARIA11 — Using ARIA landmarks to identify regions of a page](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA11)

## FLS files consulted (repo check, not web)

- `freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`
- `freedom_ls/learner_interface/views.py` (`_category_section`, `_available_section`,
  `_recommended_section`, `_coming_soon_section`, `all_courses`)
- `.claude/skills/brand-guidelines/SKILL.md`

status: ok
