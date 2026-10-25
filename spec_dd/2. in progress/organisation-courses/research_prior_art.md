# Research: prior art for organisation-scoped courses

Question: what has already been tried for this, here or elsewhere, and what happened?

## Part 1: Here (this repo)

No earlier spec, idea or decision tried to scope Courses to Organisations. The closest is an explicit, repeated deferral. Everything below is context the spec must build on or reverse.

### 1.1 Deferral of course scoping (the key finding)

- `spec_dd/3. done/2026-08-21_09:09_organisations/1. spec.md` section 6.4 ("What is not organisation-scoped in this cut"): the Courses list, course interest, course applications and course recommendations stay unscoped. Reason given: course content is shared across the whole Site and has no organisation; interest, applications and recommendations all happen before a registration exists, so there is no organisation to inherit. Called "a known, accepted gap for v1".
- The same spec records a `CourseConfig` educator-interface exemption (permissive override plus a `@claude` TODO), "courses are not organisation-scoped in this cut". Do not delete that TODO. Check whether this work completes it.
- The same spec records a pre-existing bug: `CourseDataTable.get_queryset` in the educator interface is `Course.objects.all()` with no permission check. It was routed to `critical_security_fixes`. Educator course listings are a leak path once courses are org-restricted.
- `docs/product/multi-tenancy-and-isolation.md` (Limitations): "Courses, course interest, applications, and recommendations are not organisation-scoped in this release — they remain shared across the whole site." This doc line will need updating by this feature. The doc also states an organisation is "not a security or isolation boundary" and that site is the isolation boundary. Org-restricted courses are the first place an org gates visibility, so the spec must say how that sits with the canonical statement.
- Organisation design (same spec): Organisation sits between Site and cohorts. `Cohort` and `UserCourseRegistration` carry a mandatory org FK. `CohortCourseRegistration` reaches its org through the cohort. Names are unique per site, every site gets a default organisation, and organisations cannot be deleted. `Course` has no org relation today.
- The same spec rejected "one Site per client" as disproportionate when groups share courses. It also notes the old uniqueness problem (a course name can only exist once per Site). Per-org same-name courses are a Course slug/name uniqueness question: `Course` is `unique_together = ["site", "slug"]` (per `research_visibility_and_access_system.md`), so same-name independent copies need distinct slugs, or a uniqueness change.

### 1.2 Learners and organisations

- `spec_dd/3. done/2026-08-23_17:20_learners-associated-with-organisations`: introduced `Learner` (per user, per organisation) and `OrganisationMember`. It reversed the earlier non-goal "no organisation membership object". The reason was that "who belongs to this organisation" was derived from registrations only, so a person could not be an org's learner before any enrolment. This is the basis for "which organisations is this learner in", which an org-scoped catalogue needs. A user can be a Learner of several organisations.
- Registration uniqueness was widened to include organisation, so a learner can hold two registrations for the same course through two organisations. The spec ordered an audit of every `.get()` / `get_or_create()` on registrations, especially in the course-access backends. Per-org course copies reduce but do not remove that case.
- `docs/product/learner-experience.md` (Organisation Co-Branding): the course player shows a small secondary mark (logo, else initials monogram, else generic icon) for the organisation a learner studies through, reached via cohort or own registration. A learner who self-registers goes through the site's default organisation, so no mark shows unless that org has a logo. The org-resolution logic from the organisations spec section 7 (cohort registration's org, else individual registration's org) is reusable for in-progress cards. It lives in `student_interface/.../course_toc_header.html` (old `student_` naming; the app is now `learner_interface`). Verify the current path.
- Reuse note: the default-organisation case means the card must decide whether to show the default org's info. The co-branding precedent is "no mark unless the org has a logo".

### 1.3 Course visibility and access (the existing gating mechanism)

From `spec_dd/3. done/2026-07-11_16:24_override_course_access_and_details_page/research_visibility_and_access_system.md` (written before the `student_*` to `learner_*` renames, so verify paths):

- Visibility (`published` / `coming_soon` / `hidden`) is a `Course` field set from content YAML and read-only in admin.
- It is enforced at exactly two chokepoints. `VisibilityEnforcingBackend` wraps whatever `COURSE_ACCESS_BACKEND` is configured and cannot be bypassed by an inner backend. It has `get_access()` and `filter_visible()`. `raise_404_if_hidden_unregistered` is the single-course chokepoint for detail, apply and express-interest views.
- Design rule: registered learners bypass hidden/coming-soon, so visibility never disrupts an enrolled learner. Listing views (dashboard "available" section, all-courses, recommendations) all route through `backend.filter_visible` to avoid drift. A comment in the code says the single-course rule must not drift from the queryset rule.
- Implication for this feature: org-restricted visibility belongs at those same two chokepoints, to avoid the drift the earlier design already guarded against. A learner already registered through another path should probably keep access, matching the registered-bypass precedent. This is an inference, not a recorded decision.
- `docs/product/configuration-and-extension.md`: `COURSE_ACCESS_BACKEND` selects the backend. The reference config is application-gated. Applications and their dashboard panel belong to the backend. Applications are in the `course_applications` app and are unchanged by this idea (per the idea file).
- Course cards: `2026-05-30_15:26_course-card-upgrades` (spec, UX research, reference implementations) defined the current card design. Read its spec before adding an org line, so the addition follows its layout and palette rules. `docs/product/learner-experience.md` notes coming-soon courses render as a plain link with a badge instead of a card with actions, a precedent for badges on cards.
- `2026-07-17_14:02_course-details-page-accessable-to-registered-learners` made the details page reachable by registered learners. An org-only course's detail page needs the same access rules.

### 1.4 Other in-flight specs that touch the same ground

- `spec_dd/1. next/roadmap.md`: `corporate-job-course-recommendations` and its sub-specs add per-organisation rules, lists and a per-org on/off switch. It records an open question "How organisation-owned rules scope `RecommendedCourse`, which is keyed on `User`, not `Learner`". That question collides with org-restricted courses: a rule must not recommend a course the learner cannot see. This is a likely ordering or interaction dependency.
- Same file: `deadlines`, `educator-interface` (specs 5 to 12) and `user-communication` are all organisation-scoped. The educator interface is organisation-scoped throughout and the Courses tab is the explicit exception. Roadmap line 91: "Everything is organisation-scoped and site-aware ... Nothing lets an educator reach across organisations." Org-restricted courses make the Courses tab scoping question live again.
- `corporate-job-course-recommendations/idea.md` notes `Organisation` has no settings field and no org-level toggle precedent. Org-specific data lives in per-org one-to-one rows in feature apps. That is a precedent for keeping the new relation out of the core `Organisation` model if the apps layering requires it. The through-model location (which app owns the Course-Organisation M2M) is a dependency-direction decision for the spec.

## Part 2: Elsewhere

Source: this repo's earlier `research_lms_school_modelling.md` (organisations spec). The citations below come from that file; it flagged some points as second-hand. Nothing was re-fetched in this run.

- Moodle Workplace (tenants): each tenant maps to exactly one top-level course category, and tenant users browse only that tenant's courses. Specific courses can be deliberately shared across tenants as an opt-in exception (a shared onboarding course). Documented failure mode: course-visibility bleed. A forum thread reports courses appearing under both core and tenant 2, and the admin unable to remove "core" courses from a secondary tenant (second-hand, the thread returned 403). Lesson: course-to-tenant mapping needs to be explicit and enforced everywhere, and "shared" must be a deliberate state. Docs: https://docs.moodle.org/502/en/Multi-tenancy ; https://docs.moodle.org/502/en/Multi-tenancy_Tenants ; https://moodle.com/news/sharing-content-or-courses-with-different-teams-using-moodle-workplace/ ; https://moodle.org/mod/forum/discuss.php?d=415570
- Open edX: an Organization is baked into the course key (`course-v1:Org+Course+Run`), so each course belongs to exactly one org. A Site's catalogue is filtered by org, roughly one site per org. Branding via Sites had documented data-separation and cross-URL gaps. Lesson: single-owner is simple but cannot express a many-to-many catalogue, which FLS wants. Same-name courses stay distinct because the full key differs, which is a parallel to the "same name, independent copies" requirement. https://opencraft.com/configuring-multiple-sites-on-the-open-edx-platform/ ; https://openedx.atlassian.net/wiki/spaces/AC/pages/103907632/Open+edX+Partners+Sites+and+Organizations ; https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/
- Canvas: a course belongs to exactly one account or sub-account. Serving two orgs means cross-listing sections, a manual admin-only step that can lose submitted work. Lesson: forcing single ownership then needing shared courses produces destructive workarounds, which supports a many-to-many restriction (or independent copies) up front. https://community.instructure.com/en/kb/articles/661459-how-do-i-use-cross-listing-in-an-account
- TalentLMS / Docebo: branches are mostly single-membership for users. TalentLMS separates groups (flexible sets used for assigning and selling course bundles) from branches (sub-portals). Course assignment to groups is the many-to-many pattern. https://help.talentlms.com/hc/en-us/articles/9651522351260-What-is-the-difference-between-groups-and-branches-in-TalentLMS

### Lessons carried forward

1. Visibility must be enforced at one chokepoint pair (list queryset and single-course), or courses leak (the Moodle failure mode). FLS already has this structure.
2. Make "available to all organisations" an explicit, default state (no restriction rows), so existing courses, existing installs and single-organisation sites behave unchanged. This is inferred from Moodle's opt-in sharing and from FLS's "single-organisation deployment behaves as before" principle.
3. Same-name independent copies are normal in other systems because identity is not the display name (Open edX course key). FLS identity is `(site, slug)`, so copies need distinct slugs, and the spec must say how that is authored in content YAML.
4. Educator surfaces (course lists) are a second leak path, as the earlier spec flagged.

## Open questions this research surfaces (for the spec)

- Does an org restriction hide courses from non-members entirely, or only block applying and enrolling? Visibility's "registered learner bypass" suggests existing registrations keep access.
- Does "single organisation" for the card rule mean exactly one organisation in the many-to-many set? The idea implies this; the multi-org case is unstated.
- Where does the M2M live (which app), and who authors it: content YAML (as `visibility` is, and read-only in admin) or admin? Precedent leans toward the content pipeline owning course fields.
- Interaction with `corporate-job-course-recommendations` (rules recommending restricted courses).

status: ok
