# Research: UX patterns for shared / non-previewable courses

Scope: educators of org B seeing org A's course via a grant (`see`, `register`, `preview`) or an existing registration. Confidence note: web search gave solid sources for Moodle Workplace and for hidden-vs-disabled; it gave nothing concrete on Docebo, LearnUpon, Absorb or Canvas Commons badges. Those entries below are from general product knowledge and are marked unverified.

## 1. What other LMSs do

- **Moodle Workplace (verified).** Cross-tenant sharing is done by putting courses in a "shared" category, or in a "Shared space" tenant. Tenant admins otherwise cannot see courses outside their own tenant's category when adding courses to programs. So sharing is opt-in and the default is hidden. Sources: https://docs.moodle.org/en/Catalogue_Tenants, https://docs.moodle.org/en/Programs_Tenants, https://docs.moodle.org/503/en/Multi-tenancy_Tenants
- **Canvas Commons (unverified).** Shared resources sit in a separate library where an item shows its owner or sharer and a license. Importing copies the item. There is no live "shared by" badge in the course list.
- **Docebo, LearnUpon, Absorb (unverified).** Multi-tenant or "extended enterprise" setups scope the catalog per tenant or portal. Shared content appears in the catalog without special lock states. Admins see a plain per-tenant list, with ownership shown as a column or filter.
- **Common thread.** Shared content is either opt-in visible or absent. Where it appears, ownership is a text label or column, not a heavy visual treatment. None of these products renders "visible but locked" shared courses in management lists.

## 2. Hidden vs disabled

Smashing Magazine guidance: disable when users should know the thing exists but can't use it. Hide when it is irrelevant. A disabled control with no reason confuses people, so give helper text. Sources: https://smashingmagazine.com/2024/05/hidden-vs-disabled-ux/, https://github-redirect.dependabot.com/uswds/uswds/wiki/Disabled-States-Research-Findings-2023

Applied here:
- Course with no grant and no registration: **hide completely**. The educator has no business knowing it exists, and the decision is to 404 it.
- Course visible with `see` only: visible, but actions that need a missing right (register, preview) are **disabled with a reason**, or omitted where the action can never apply.

## 3. Recommendations for the FLS educator interface

**Course list (data table)**
- Add a "Shared by <organisation name>" text badge, or a small "Owner" column, on rows whose owner is not the current organisation. Own courses carry no badge, so the common case stays clean.
- Show a rights summary only on the detail page, not in the table. A tooltip on the badge can list it ("You may: view, register learners").
- Offer an "Own / Shared with us" filter only if the list gets long. Don't build it by default.

**Detail page without `preview`**
Options: (a) disabled outline, (b) hidden outline, (c) notice. Recommend **(c) with the outline hidden**. Show the course title, description and owner, then one explanatory notice: "<Org A> shares this course with you. Content preview isn't included." A disabled outline invites clicks that lead nowhere and leaks the structure the owner chose not to share. A silently missing outline looks like a bug. The preview URLs 404, so the page must not link to them.

**Instance actions and quick views**
- Quick views show metadata only (title, owner, rights) for shared courses. No content snippets without `preview`.
- Register actions appear only with `register`. With `see` only, show the action disabled with the reason "Registration isn't included in this share."
- A registration held through an existing cohort or learner registration grants visibility only. Show the same badge and the notice. Do not imply a grant. The notice could read "Visible because you hold registrations on it."

**Pickers (register learner or cohort)**
- **Omit** courses the organisation can't register for. A picker's job is to choose valid targets, and a disabled-with-reason list of other organisations' courses would show courses the educator has no right to know about (hidden ones are never shown). For visible-but-not-registerable (`see` only), omit too, for consistency and shorter lists. The reason is available on the course detail page.
- Label shared options in the picker with the owner's name in parentheses, so duplicates in title are distinguishable.
- A course held only through an existing registration (no `register` grant) is also omitted from pickers. The same rule as the list applies, but the registerable test applies on top.

**Empty states**
- Courses list empty: "No courses yet. Courses owned by or shared with your organisation appear here." Do not mention hidden courses.
- Picker empty: "No courses available to register for." With a link to the Courses list only if it is non-empty.
- Don't differentiate "nothing exists" from "nothing shared", because that would leak the existence of hidden courses.

**Consistency check**
Hidden/forbidden courses behave identically in list, picker and direct URL (absent, absent, 404). Visible-but-restricted courses show a label plus a reason, never a dead control.

## Sources
- https://docs.moodle.org/en/Catalogue_Tenants
- https://docs.moodle.org/en/Programs_Tenants
- https://docs.moodle.org/503/en/Multi-tenancy_Tenants
- https://smashingmagazine.com/2024/05/hidden-vs-disabled-ux/
- https://github-redirect.dependabot.com/uswds/uswds/wiki/Disabled-States-Research-Findings-2023

status: ok · reason: Moodle and hidden-vs-disabled sourced; Canvas Commons, Docebo, LearnUpon and Absorb entries unverified, from general knowledge
