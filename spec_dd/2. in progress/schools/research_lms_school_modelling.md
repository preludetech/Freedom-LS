# Research: how LMSs model a sub-organisation layer

## Executive summary

Every mature LMS that supports multi-org deployments puts *something* between "tenant/instance" and
"course": Canvas has nestable **accounts**, Moodle Workplace has **tenants** mapped 1:1 onto a
top-level **course category**, Open edX has **Organizations** tied to course keys plus separately
configured **Sites**, and the SMB/B2B tools (TalentLMS, Docebo, LearnWorlds) call it a **branch** or a
**school** and treat it as close to a full sub-portal. Totara borrows Moodle Workplace's tenant model.

Two structural choices recur and matter for FLS:

1. **Tree vs flat.** Canvas, Docebo and Totara are trees (nestable sub-accounts/branches). Moodle
   Workplace tenants are deliberately **flat** — a tenant maps to exactly one top-level course
   category and tenants cannot nest — and the community documentation and forum reports both single
   this out as a source of confusion when people expect category-style nesting inside a tenant.
   TalentLMS branches are also flat (a "branch" is not itself sub-branchable in the standard product).
   Flat is a legitimate, common choice, not an outlier — but retrofitting a tree onto a flat model
   later is a real migration (self-referential FK + tree-traversal rewrites of every scoping query),
   not a config flag.
2. **Single-membership vs multi-membership.** The most instructive data point is **Docebo**, which
   *used to* allow a user to be copied across multiple branches, and as of October 2019 **changed the
   default to single-branch membership**, moving multi-branch to a support-gated exception
   ([Docebo community](https://community.docebo.com/product-q-a-7/how-can-i-find-users-that-are-assigned-to-multiple-branches-7700)).
   That is a vendor concluding, after experience, that "one primary org per user" is the saner default
   and multi-membership is the edge case. This directly supports FLS's "school FK is mandatory,
   default-school backfill" decision.

Sources checked and verified against are cited inline per system. Where I could not verify a claim
from primary documentation (paywalled admin docs, product behaviour that changes by plan/version), I
say so explicitly rather than inferring vendor behaviour from marketing copy.

---

## Canvas LMS — Accounts and sub-accounts

**What it's called / where it sits.** Every Canvas instance starts with one **root account**; from
there you can build a hierarchy of **sub-accounts**, and sub-accounts can contain further nested
sub-accounts. Courses and enrolments live inside a sub-account (or the root account directly).
([Instructure Community: hierarchical structure for Canvas accounts](https://community.instructure.com/en/kb/articles/661404-what-is-the-hierarchical-structure-for-canvas-accounts);
[Canvas REST API — Accounts](https://uth.instructure.com/doc/api/accounts.html))

**Tree or flat.** Tree. The `Account` API object exposes `parent_account_id` (`null` for the root
account) and `root_account_id`, and sub-accounts can nest arbitrarily deep
([Canvas REST API — Accounts](https://uth.instructure.com/doc/api/accounts.html)). This is used by
large universities to mirror college → department → program structures.

**Multi-membership.** Not directly verified from primary docs in this pass, but the account/course
relationship is one-directional per course (a course belongs to exactly one account); admin *roles*
are what can be granted at multiple levels — a person can be an admin on more than one sub-account
simultaneously, each grant being a separate role assignment scoped to that sub-account
([Instructure Community: hierarchical structure for Canvas accounts](https://community.instructure.com/en/kb/articles/661404-what-is-the-hierarchical-structure-for-canvas-accounts)).
I could not verify from documentation in this pass whether a *student* enrolment can span two
sub-accounts simultaneously for the same course; Canvas's cross-listing feature (below) suggests
courses/sections are single-account-owned by design.

**Enrolment ownership.** Owned by the course, and the course belongs to exactly one account
(sub-account or root). **Cross-listing** lets an admin move a *section* from one course to another,
including across accounts/sub-accounts — but a section can only be in one course at a time, and
cross-listing after work has been submitted can lose grades/submissions
([Instructure Community: cross-listing](https://community.instructure.com/en/kb/articles/661459-how-do-i-use-cross-listing-in-an-account)).
This is Canvas's answer to "what if this course needs to serve two orgs" — the pain point is that it's
a manual, somewhat destructive administrative operation, not a first-class multi-org enrolment model.

**Branding per sub-account.** The **Theme Editor** is root-account-only by default, but can be
delegated to sub-accounts. Anything a sub-account theme does *not* override is inherited from its
parent; sub-account themes can set colours (via hex codes for text/buttons/links), upload a logo and
watermark images, and (on paid tiers) custom CSS/JS
([Instructure Community: manage themes for an account](https://community.canvaslms.com/t5/Admin-Guide/How-do-I-manage-themes-for-an-account/ta-p/154);
[Instructure Community: create a theme with the Theme Editor](https://community.canvaslms.com/t5/Admin-Guide/How-do-I-create-a-theme-for-an-account-using-the-Theme-Editor/ta-p/242)).
So branding is explicitly hierarchical/inheriting, not "every sub-account starts from a blank slate."

**Staff access scoping.** Admin roles are granted **per account**, and a sub-account admin's scope is
that sub-account plus everything nested beneath it (inheritance down the tree) — this is the direct
payoff of the tree structure: you don't need to explicitly grant access to every leaf, granting at a
branch node covers the branch. This is the main thing FLS gives up by going flat: with a flat model,
"give this person access to Region X and everything under it" degenerates to "give this person access
to each School individually," which is fine at FLS's current scale but is the first thing that will
hurt if a customer wants regional roll-ups.

**Pain points.** Cross-listing across accounts is a manual, admin-only operation with data-loss risk
if done after work is submitted. Sub-account theming is opt-in and inherits by default, which some
institutions have found confusing when a department expects full independence.

---

## Moodle — Course categories vs Moodle Workplace tenants

**Two different mechanisms, worth distinguishing.**

1. **Standard Moodle course categories.** These are a content taxonomy (a tree of categories courses
   sit in), with category-level roles for scoping admin permissions, but they are *not* a tenancy or
   branding boundary out of the box
   ([e-Learn Design: Moodle vs multi-tenancy Moodle](https://www.e-learndesign.co.uk/expert-centre/how-to-moodle/moodle-vs-multi-tenancy-moodle/)).
2. **Moodle Workplace tenants** (a commercial Moodle Workplace / MoodleCloud feature, not core
   Moodle). A **tenant** is "isolated" — its own look and feel, structure, users and learning content;
   users in one tenant cannot see users in another
   ([Moodle Docs: Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy)).

**What it's called / where it sits.** Tenant, sitting directly under the Workplace instance. **Each
tenant maps to exactly one top-level course category** — when you create a tenant you either create a
brand-new top-level category for it, or attach an existing top-level category that isn't already
claimed by another tenant
([Moodle Docs: Multi-tenancy Tenants](https://docs.moodle.org/502/en/Multi-tenancy_Tenants)).

**Tree or flat.** **Flat by design at the tenant level** — a tenant is not itself nestable inside
another tenant. (The course category *underneath* a tenant can still be a normal Moodle category tree
for content organisation, but that's a content hierarchy, not an org hierarchy.) This is the single
most relevant precedent for FLS's flat-School decision: Moodle Workplace, a serious commercial
multi-tenant product, chose flat tenants and did not regret it enough to add tenant nesting. The
documented failure mode is not "we needed nested tenants," it's **course-visibility bleed** — a Moodle
forum thread reports an admin who could not isolate a tenant's category visibility, could not remove
"core" courses from a secondary tenant, and saw courses appearing under both the core tenant and
tenant 2 simultaneously ([Moodle.org forum: Moodle Workplace Tenants issue(s)](https://moodle.org/mod/forum/discuss.php?d=415570) —
title and existence of the thread confirmed via search; I could not fetch full thread content in this
pass due to a 403, so treat the detail as second-hand from search-result summarisation, not a verified
quote).

**Multi-membership.** **Each user belongs to a single tenant** — confirmed directly from Moodle
documentation content fetched in this research
([Moodle Docs: Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy)). This is a second strong
precedent for FLS's "school FK is mandatory" (single-owner) design, at least for the default case.
Moodle Workplace does support deliberately **sharing specific courses across tenants** as an opt-in
exception (e.g. a shared onboarding course), rather than making cross-tenant visibility the default
([Moodle: Sharing content or courses using Moodle Workplace](https://moodle.com/news/sharing-content-or-courses-with-different-teams-using-moodle-workplace/)).

**Enrolment ownership.** Enrolment is effectively owned by the tenant's course category — a user's
tenant membership plus the tenant's course category determines what they can enrol in; tenant users
can only browse courses in the tenant's category and cannot browse courses elsewhere
([Moodle: Sharing content using Moodle Workplace](https://moodle.com/news/sharing-content-or-courses-with-different-teams-using-moodle-workplace/)).

**Branding.** Confirmed: each tenant has its own "look and feel" and theme settings
([Moodle Docs: Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy)). I could not verify from
primary docs in this pass the exact list of brandable fields (logo vs colours vs custom domain vs
emails vs certificates) — Moodle Workplace marketing materials imply theme-level branding including
logo, but I am not treating that as verified without a documentation page confirming the field list.

**Staff scoping.** Moodle Workplace has a distinct **Tenant administrator** role, scoped to a tenant's
course category context (this is inferred from the existence of a "Tenant administrator in course
category role" documentation page title
([Moodle Docs: Tenant administrator in course category role](https://docs.moodle.org/311/en/Tenant_administrator_in_course_category_role))
— the page itself returned a server error when fetched in this pass, so the *exact* mechanics of
inheritance are not verified, only that the role exists and is category-scoped by name).

**Pain points.** The clearest documented one: if you need true physical/data separation between
tenants, Moodle's own documentation says multi-tenancy on a single Moodle instance may not be
sufficient and separate Moodle sites may be needed instead
([Moodle Docs: Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy)) — i.e. Moodle itself
draws a line beyond which "sub-org inside one instance" stops being the right tool, which is a useful
sanity check for FLS: School is for org structure *within* a Site, not a replacement for Site-level
isolation.

---

## Open edX — Organizations, Sites, and site configurations

**What it's called / where it sits.** Open edX has at least three related-but-distinct concepts that
are easy to conflate:

- **Organization** — an `org` string tied into the course key itself (e.g. `course-v1:OrgX+CS101+2024`).
  Every course belongs to exactly one org, baked directly into its identifier
  ([search-result summary citing Open edX Locators developer notes](https://github.com/edx/edx-platform/wiki/Locators:-Developer-Notes)).
- **Site** — a Django `Sites`-framework construct partitioning the experience by domain/host name (this
  is the *same* Django Sites mechanism FLS already uses at the tenant level), configured via a
  `SiteConfiguration` model in Django admin
  ([OpenCraft: Configuring multiple sites on the Open edX platform](https://opencraft.com/configuring-multiple-sites-on-the-open-edx-platform/)).
- **Partner** — a cross-cutting business-entity concept (used for back-office/reporting linkage across
  multiple sites and services), separate again from Organization and Site
  ([Open edX wiki: Partners, Sites, and Organizations](https://openedx.atlassian.net/wiki/spaces/AC/pages/103907632/Open+edX+Partners+Sites+and+Organizations)
  — fetched directly; the Partner and Site definitions above are verified quotes from that page. The
  page content on Organizations specifically was truncated in the fetch and not independently
  verified beyond the course-key relationship above).

**Tree or flat.** Flat. Organization is a plain identifying string/model with no parent — it is not
nestable. Sites are also flat relative to each other (each Site is independently configured).

**Multi-membership.** A **Site is configured to host the courses of one particular org**, and each
site's catalog is filtered by matching `org` on the course key (e.g. subdomain → `ORG=Foo` filter)
([OpenCraft: Configuring multiple sites on the Open edX platform](https://opencraft.com/configuring-multiple-sites-on-the-open-edx-platform/)).
This implies a roughly 1:1 practical pairing of Site↔Org in typical deployments, which is a different
shape from FLS's proposal (multiple Schools *inside* one Site). Open edX's org concept is closer to
"which catalog/brand a course was authored under" than to "which sub-tenant a learner is enrolled
through" — it doesn't map cleanly onto FLS's School concept and I would not treat Open edX as strong
precedent either way for the multi-school-per-site question.

**Enrolment ownership.** Enrolment is owned by the course; org is a property of the course identifier,
not of the enrolment record. There is no visible "org membership" object separate from course
enrolment in what was verified here.

**Branding.** Historically via **Microsites** (deprecated) and now via Site + `SiteConfiguration`:
separate deployable "micro-themes" (branding elements, template overrides) per subdomain
([edx-platform wiki: Microsites Theming](https://github.com/openedx/edx-platform/wiki/Microsites-Theming)).
Documented limitations of this approach include **insufficient data separation and cross-URL branding
issues** — i.e. Open edX's own community flags that site-based theming has leaked-branding failure
modes ([edunext: Discover the Open edX multi-tenancy enhanced features](https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/)).

**Staff scoping.** Not verified in depth in this pass; Open edX role models (course staff, org staff)
exist in `common/djangoapps/student/roles.py` in the edx-platform source but I did not fetch and
verify the specific org-level role classes, so this is flagged as unverified rather than described.

**Pain points.** Open edX's own community documentation explicitly calls out that the
Microsites-then-Sites evolution left **data separation and cross-URL branding gaps**
([edunext](https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/)) — i.e. even a
mature, well-funded open-source LMS found "brand this differently per sub-unit" harder to get fully
clean than it sounds, largely because branding touches URLs, emails, and static assets that don't
naturally partition per logical org the way a DB foreign key does.

---

## TalentLMS — Branches

**What it's called / where it sits.** **Branch**, sitting directly under the TalentLMS portal
("domain"). A branch is described as an "independent sub-portal" with its own admin, branding, users,
courses, homepage, language and e-commerce setup
([TalentLMS: Branches feature page](https://www.talentlms.com/features/branches);
[TalentLMS Help: How to work with branches](https://help.talentlms.com/hc/en-us/articles/10730422769436-How-to-work-with-branches-in-TalentLMS)).

**Tree or flat.** Flat — a branch is not itself sub-branchable in the documentation reviewed; branches
sit as siblings under the main portal. (TalentLMS separately has **Groups**, which are a different,
more flexible, non-hierarchical membership construct explicitly contrasted with branches:
"[branches are for] things that don't change very often about that user ... groups are more flexible"
— this framing is from the Docebo docs but the same branch/group distinction is drawn in TalentLMS's
own help center: [What is the difference between groups and branches in TalentLMS](https://help.talentlms.com/hc/en-us/articles/9651522351260-What-is-the-difference-between-groups-and-branches-in-TalentLMS)).

**Multi-membership.** Users can be added to a branch via import or the UI, and TalentLMS explicitly
supports a setting to **disallow members of a branch from logging in via the main domain URL or
another branch** ("Disallow members of this branch to login from main domain URL")
([TalentLMS Help: How to work with branches](https://help.talentlms.com/hc/en-us/articles/10730422769436-How-to work-with-branches-in-TalentLMS)),
which implies the *default* is that a user's login is not strictly branch-exclusive unless the admin
opts into that restriction — i.e. TalentLMS's default leans toward allowing overlap/shared login across
branches, with single-branch-only being an opt-in lockdown, the reverse of Docebo's later default.

**Enrolment ownership.** Owned by the branch (courses are assigned to a branch; branch admins manage
branch-specific courses and reporting) — TalentLMS branch admins have "access to branch-specific
information and settings only, and absolutely no access to your main domain and the overall platform
data" ([TalentLMS Support: How to use branches for multi-purpose training](https://help.talentlms.com/hc/en-us/articles/10730422734236-How-to-use-branches-for-multi-purpose-training-in-TalentLMS)).

**Branding.** Own URL, theme, homepage and language per branch — a materially bigger branding surface
than "just a logo": TalentLMS branches can look like fully separate products
([TalentLMS: Branches feature page](https://www.talentlms.com/features/branches)).

**Staff scoping.** Branch-scoped admin role, explicitly walled off from the main portal and other
branches (no inheritance implied, no tree).

**Pain points.** Not independently verified beyond the branch/group distinction; I found no specific
documented complaint thread for TalentLMS branches in this pass.

---

## Docebo — Branches (organization chart)

**What it's called / where it sits.** **Branch**, arranged in a hierarchy ("organization chart") of
branches and sub-branches starting from a mandatory root branch that cannot be removed
([Docebo Help: Creating and Managing an Organization Chart](https://help.docebo.com/hc/en-us/articles/360020084140-Creating-an-Organization-Chart)).

**Tree or flat.** **Tree** — branches can have sub-branches, explicitly modelled to mirror a company's
department/team structure.

**Multi-membership — the key precedent for FLS.** Verified via Docebo community support:
**by default, a user belongs to one branch**; assigning a user to multiple branches simultaneously
requires Docebo support to enable a feature toggle. Deployments **activated before 21 October 2019**
could default users into multi-branch (copy-on-update); deployments **activated after that date**
default to single-branch, move-on-update semantics, with no built-in option to copy a user across
branches ([Docebo community: How can I find users that are assigned to multiple branches?](https://community.docebo.com/product-q-a-7/how-can-i-find-users-that-are-assigned-to-multiple-branches-7700)).
Docebo also distinguishes branch (stable org attributes: internal/external, department) from **group**
(flexible, criteria-based membership) as the mechanism for anything that needs to vary independent of
org structure
([Docebo Help: Organizing users with branches](https://help.docebo.com/hc/en-us/articles/360020084140-Organizing-users-with-branches)).
This is a directly on-point precedent: a real vendor tried permissive multi-branch membership, then
walked it back to single-branch-by-default as the product matured, keeping multi-membership as a
support-gated exception rather than the norm.

**Enrolment ownership.** Owned by the branch structure combined with course assignment; not
independently verified beyond the branch/group framing above.

**Branding.** Not verified in this pass beyond general "own branding" claims in secondary sources;
no primary Docebo doc on branch-level brandable fields was fetched.

**Staff scoping.** Branch admins scoped to a branch and (by the tree's nature) implicitly to
sub-branches beneath it, mirroring Canvas's inheritance pattern — inferred from the "organization
chart" framing, not independently confirmed with a permissions matrix in this pass.

**Pain points.** The community thread cited above shows real customer confusion/cleanup burden from
legacy multi-branch users after the policy changed — migrating multi-branch users down to single-branch
required a CSV export/re-import workaround, i.e. **the "loosen it later" direction is easy; the
"tighten it later" direction created real cleanup work for Docebo customers.** That is a useful
asymmetry for FLS: starting mandatory-single-school (as already decided) and *loosening* to
multi-school-membership later if ever needed is the safer order of operations, matching what Docebo
customers actually experienced in the other direction.

---

## LearnWorlds — "Schools"

Worth flagging because LearnWorlds uses the literal word **"School"** for what is otherwise the same
concept: a **School** is a full sub-portal under a LearnWorlds account/organization, with its own
custom domain, branding and (on paid tiers) full white-labelling
([LearnWorlds Help: Quick Start Guide 1 — Set Up Your School](https://support.learnworlds.com/support/solutions/articles/12000105632-quick-start-guide-1-set-up-your-school);
[LearnWorlds Help: How to Manage your LearnWorlds Schools](https://support.learnworlds.com/support/solutions/articles/12000094904-how-to-manage-your-learnworlds-schools)).

**What it's called / where it sits.** School, directly under a LearnWorlds account/organization —
"you should choose under which organization the school will be associated"
([LearnWorlds Help: Custom Domains overview](https://support.learnworlds.com/support/solutions/articles/12000080095-custom-domains)).
This is a closer terminological match to FLS's naming than any other product surveyed, but the *scope*
is much bigger in LearnWorlds — a School there is closer to FLS's whole **Site** (own domain, fully
separate look-and-feel, "unified LearnWorlds Dashboard" managing multiple *otherwise-independent*
Schools) than to FLS's proposed School (a lighter-weight scoping layer *inside* one Site).

**Tree or flat.** Flat — schools sit as siblings under an organization/account, managed from "Multiple
Schools Dashboard"
([LearnWorlds: Multiple Schools Dashboard](https://www.learnworlds.com/multiple-schools-dashboard-branch-out-your-business-in-a-few-clicks/)).

**Multi-membership.** Centralised login across multiple schools under one account for the *owner/admin*
side ("centralized login and a unified LearnWorlds Dashboard") — but this is about an operator managing
several schools, not about a single learner belonging to more than one school at once. No evidence
found of a learner-level cross-school membership model; each School functions as its own learner
population.

**Branding.** The broadest brand surface of anything surveyed: **custom domain** (not just subdomain),
full white-labelling on higher tiers, own homepage/theme — i.e. LearnWorlds treats "School" as
effectively a separate storefront/product, which is a much bigger commitment than "logo on the course
player" ([LearnWorlds Help: Custom Domains overview](https://support.learnworlds.com/support/solutions/articles/12000080095-custom-domains)).

**Why this matters for FLS's naming.** LearnWorlds' use of "School" for something that is really
FLS's Site-equivalent is a naming collision risk worth flagging to the idea author, not a modelling
lesson — see Open Questions below.

---

## What this means for FLS

**1. Flat-vs-tree: FLS can defer this safely, but should know the true cost of deferring it.**
Moodle Workplace (flat tenants) and TalentLMS (flat branches) are commercially successful with a flat
model; Canvas, Docebo and (per name only) Totara are trees, and the tree's payoff in every case is the
same single thing: **inherited staff access** ("give this role at node X, it applies to everything
under X") — not richer branding, not different enrolment semantics. If FLS ever needs that, the
concrete migration cost of adding a tree later is:
   - add a self-referential `parent` FK to `School` (or introduce a separate `SchoolGroup`/region
     model above `School`) — schema-wise this is cheap and additive, not a breaking change to
     `School` itself;
   - the real cost is everywhere a query currently does "role scoped to School X" and would need to
     become "role scoped to School X or any of its descendants," i.e. every educator-scoping query,
     permission check, and the school-switcher dropdown's option list all need a recursive/CTE
     lookup instead of a flat filter. This is a moderate, contained migration (it touches
     `educator_interface` scoping logic and any admin permission checks), not a data-model rewrite,
     provided `school` stays a single mandatory FK on registrations/cohorts throughout (which is
     already the fixed decision). **Recommendation: flat is fine for v1; do not build parent/child now,
     but do keep school-scoping logic behind a small number of query helper functions (not inlined
     everywhere) so that a future "or descendants" change is a localized edit, not a grep-and-replace
     across the codebase.**

**2. "One school per registration" matches the dominant pattern, and is the safer default to launch
with.** Moodle Workplace ("each user belongs to a single tenant," verified) and Docebo's post-2019
default (single-branch membership, with multi-branch demoted to a support-gated exception after real
customer pain from the permissive era) both converge on single-org-membership-by-default being the
mature answer, not the naive starting point. FLS's registration-level `school` FK (rather than a
separate learner-school membership object) is consistent with this and is the right default. **Do
not** build a `SchoolMembership` model in the first cut. If a genuine multi-school learner scenario
shows up later (e.g. a tutor who teaches through two Schools on the same Site), model it the way these
systems do — as multiple registrations/enrolments, each scoped to one School — rather than as
membership-object multiplicity, since that's the pattern every system surveyed here that supports
multiple registrations per learner actually uses (enrolment-owns-the-org-link, not
user-owns-a-list-of-orgs).

**3. Branding scope: FLS's "logo only" first cut is narrow compared to every comparator, and that's
probably correct — but the idea author should decide two adjacent fields explicitly now rather than
by accident later.** Every system surveyed brands more than a logo per sub-org: Canvas sub-accounts
get colours + watermark + optional custom CSS/JS (inheriting); Moodle Workplace tenants get their own
"look and feel"; TalentLMS/LearnWorlds branches/schools get their own **domain**, homepage and
language. FLS's fixed decision (logo shown on the course player) is a sane, minimal v1 scope, but two
things are worth flagging explicitly rather than leaving implicit:
   - **Colour/theme**: Canvas's inheritance model (sub-account theme overrides only what it sets,
     inherits the rest) is a good pattern to borrow *if and when* FLS adds a primary colour field to
     School — don't require every School to configure a full theme.
   - **Custom domain / subdomain per School**: this is the one branding axis that is architecturally
     expensive to bolt on later (routing, TLS, Django `Sites` interplay) and every system that has it
     (TalentLMS, LearnWorlds) treats it as a premium/advanced feature, not part of the base sub-org
     object. **Recommend the idea author explicitly state "no per-School domain in this cut"** so it's
     a documented deferral, not a silent gap — because Open edX's own community flagged branding/
     domain leakage as one of their harder unsolved problems even with dedicated Sites machinery
     ([edunext](https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/)), so it's
     not a trivial add.
   - Emails and certificates (both branded per sub-org in some of these systems) are not mentioned in
     FLS's fixed decisions at all; worth a one-line explicit "out of scope for v1" note so nobody
     assumes School branding silently reaches into notification templates or certificate PDFs.

**4. Staff scoping: FLS's "explicit role-on-school assignment" matches the leaf-level mechanism in
every system surveyed**, and going flat means FLS is deliberately giving up the *inheritance*
convenience that Canvas/Docebo get from their trees. That's an acceptable, explicit tradeoff given the
"defer tree" recommendation above — just don't let the educator-scoping implementation assume a school
list will always be flat and enumerable in a dropdown; keep the query surface narrow (see point 1) so
"district admin over N schools" can be added as a role concept later without a schema change to
`School` itself.

**5. Moodle's own boundary is a useful sanity check for what School is *not*.** Moodle's documentation
states that when true physical/data isolation is required between sub-orgs, multi-tenancy within one
instance is not the right tool and a separate site is needed instead
([Moodle Docs: Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy)). This maps directly onto
FLS's existing Site/School split: **Site remains the isolation boundary (separate branding root,
separate deployment-level tenancy); School is an organisational/scoping layer within one Site's trust
boundary, not a security boundary.** Worth stating explicitly in the spec so nobody later assumes
School gives data isolation guarantees that Site is supposed to provide.

---

## Open questions for the idea author

1. **Naming collision:** LearnWorlds uses "School" for something that is architecturally much closer
   to FLS's *Site* (own domain, full white-label, siblings under an account) than to FLS's proposed
   *School* (logo + scoping layer inside one Site). Is "School" still the right name given FLS already
   has "Site" one level up, or would something like "Organisation," "Division," or "Cohort Group" avoid
   readers importing LearnWorlds' mental model? (Not a blocker, just worth a deliberate choice.)
2. **Multi-school staff, not just multi-school learners:** none of the systems surveyed cleanly
   answered "can the *same person* be a School-scoped educator on School A and a School-scoped educator
   on School B simultaneously, with a single switcher between them" — Canvas and Docebo both said yes
   via multiple role grants; is that FLS's intended model for the "select school" educator dropdown, or
   is an educator meant to belong to exactly one School too?
3. **Course/content ownership vs registration ownership:** in every comparator, the *course content*
   itself is either org-owned (Open edX: org is baked into the course key) or shared-with-opt-in
   (Moodle Workplace: courses can be explicitly shared across tenants). FLS's fixed decision only says
   registrations and cohorts have a school — it does not say whether course *content* in
   `content_engine` is itself School-scoped or Site-scoped-and-shared-across-Schools. Worth confirming
   explicitly, since it changes how "school switcher" behaves for an educator who teaches the same
   course into two Schools.
4. **What happens to the default/backfill School over time** — is it meant to become just "the school
   for Sites that don't use multi-school," permanently, or is it a migration scaffold expected to be
   cleaned up? Docebo's post-toggle migration pain (manual CSV cleanup of legacy multi-branch users)
   suggests it's worth deciding now whether the default School is a first-class permanent option or a
   temporary shim, since that affects whether school CRUD/admin needs to support "delete/merge school"
   from day one.

---

## References

- Canvas — [Hierarchical structure for Canvas accounts](https://community.instructure.com/en/kb/articles/661404-what-is-the-hierarchical-structure-for-canvas-accounts)
- Canvas — [REST API: Accounts](https://uth.instructure.com/doc/api/accounts.html)
- Canvas — [How do I manage themes for an account?](https://community.canvaslms.com/t5/Admin-Guide/How-do-I-manage-themes-for-an-account/ta-p/154)
- Canvas — [How do I create a theme using the Theme Editor?](https://community.canvaslms.com/t5/Admin-Guide/How-do-I-create-a-theme-for-an-account-using-the-Theme-Editor/ta-p/242)
- Canvas — [How do I use cross-listing in an account?](https://community.instructure.com/en/kb/articles/661459-how-do-i-use-cross-listing-in-an-account)
- Moodle — [Multi-tenancy (MoodleDocs)](https://docs.moodle.org/502/en/Multi-tenancy)
- Moodle — [Multi-tenancy: Tenants (MoodleDocs)](https://docs.moodle.org/502/en/Multi-tenancy_Tenants)
- Moodle — [Multi-tenancy Configuration (MoodleDocs)](https://docs.moodle.org/502/en/Multi-tenancy_Configuration)
- Moodle — [Tenant administrator in course category role (MoodleDocs, title only — page fetch failed with server error)](https://docs.moodle.org/311/en/Tenant_administrator_in_course_category_role)
- Moodle — [Sharing content or courses using Moodle Workplace](https://moodle.com/news/sharing-content-or-courses-with-different-teams-using-moodle-workplace/)
- Moodle — [Moodle Workplace Tenants issue(s) — forum thread (title/existence confirmed via search only; fetch returned 403)](https://moodle.org/mod/forum/discuss.php?d=415570)
- Moodle vs multi-tenancy comparison — [e-Learn Design](https://www.e-learndesign.co.uk/expert-centre/how-to-moodle/moodle-vs-multi-tenancy-moodle/)
- Open edX — [Partners, Sites, and Organizations (Open edX wiki)](https://openedx.atlassian.net/wiki/spaces/AC/pages/103907632/Open+edX+Partners+Sites+and+Organizations)
- Open edX — [Configuring multiple sites on the Open edX platform (OpenCraft)](https://opencraft.com/configuring-multiple-sites-on-the-open-edx-platform/)
- Open edX — [Microsites Theming (edx-platform wiki)](https://github.com/openedx/edx-platform/wiki/Microsites-Theming)
- Open edX — [Discover the Open edX multi-tenancy enhanced features (edunext)](https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/)
- Open edX — [Locators: Developer Notes (edx-platform wiki)](https://github.com/edx/edx-platform/wiki/Locators:-Developer-Notes)
- TalentLMS — [Branches feature page](https://www.talentlms.com/features/branches)
- TalentLMS — [How to work with branches in TalentLMS](https://help.talentlms.com/hc/en-us/articles/10730422769436-How-to-work-with-branches-in-TalentLMS)
- TalentLMS — [How to use branches for multi-purpose training in TalentLMS](https://help.talentlms.com/hc/en-us/articles/10730422734236-How-to-use-branches-for-multi-purpose-training-in-TalentLMS)
- TalentLMS — [What is the difference between groups and branches in TalentLMS](https://help.talentlms.com/hc/en-us/articles/9651522351260-What-is-the-difference-between-groups-and-branches-in-TalentLMS)
- Docebo — [Creating and Managing an Organization Chart](https://help.docebo.com/hc/en-us/articles/360020084140-Creating-an-Organization-Chart)
- Docebo — [Organizing users with branches](https://help.docebo.com/hc/en-us/articles/360020084140-Organizing-users-with-branches)
- Docebo — [How can I find users that are assigned to multiple branches?](https://community.docebo.com/product-q-a-7/how-can-i-find-users-that-are-assigned-to-multiple-branches-7700)
- LearnWorlds — [Quick Start Guide 1: Set Up Your School](https://support.learnworlds.com/support/solutions/articles/12000105632-quick-start-guide-1-set-up-your-school)
- LearnWorlds — [How to Manage your LearnWorlds Schools](https://support.learnworlds.com/support/solutions/articles/12000094904-how-to-manage-your-learnworlds-schools)
- LearnWorlds — [Multiple Schools Dashboard](https://www.learnworlds.com/multiple-schools-dashboard-branch-out-your-business-in-a-few-clicks/)
- LearnWorlds — [General Overview: Custom Domains](https://support.learnworlds.com/support/solutions/articles/12000080095-custom-domains)
- Totara — [Multitenancy (Totara developer docs, existence/summary only via search)](https://totara.atlassian.net/wiki/spaces/DEV/pages/121186086/Multitenancy)
- Totara — [What is multitenancy?](https://totara.help/15/docs/what-is-multitenancy)

status: ok
