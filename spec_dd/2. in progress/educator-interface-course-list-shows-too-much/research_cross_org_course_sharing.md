# Research: cross-organisation course sharing in multi-tenant LMS platforms

Method note: written from working knowledge of each product's public documentation. The URLs below are the doc entry points for each claim. I did not re-fetch them in this run, so treat fine detail (exact setting names, defaults) as "verify before quoting in a spec". Confidence is marked per row.

## Comparison table

| Platform | Unit of tenancy | How a course reaches another tenant | Granular rights | Default for another tenant | Can the other tenant's admin bypass paid or approval enrolment? | Configured where |
|---|---|---|---|---|---|---|
| Moodle core | Course category (plus capability contexts) | No sharing as such. Visibility follows category and system role assignments. | Per-capability (`moodle/course:view`, `enrol/manual:enrol`, `moodle/course:viewhiddencourses`, `moodle/site:viewparticipants`). Each is a separate flag. | Category managers see only their own category. Site-wide courses are visible to all in the catalogue. | Yes. A manual enrol capability holder enrols directly and ignores the self-enrol price/key. Manual enrolment is a separate enrol plugin from payment. | Roles and permissions per context. https://docs.moodle.org/en/Roles_and_capabilities , https://docs.moodle.org/en/Course_categories |
| IOMAD (Moodle multi-tenant) | Company, with departments | Course is assigned to a company by a site admin. A "shared" course is available to all companies. "Open shared" lets a company's own copy be enrolled by others. | Company manager enrols own users on courses assigned to their company. Cannot see other companies' courses. Per-course setting for sharing mode (not shared, open shared, closed shared). | Not visible. Sharing is opt-in by the site admin (the owner side), not the borrowing company. | Company manager enrols only through IOMAD license allocation. Licences cap seats. This is the "gate". | IOMAD company course management. https://www.iomad.org/ , https://docs.iomad.org/ |
| Moodle Workplace | Tenant | Shared courses: site admin makes a course shared across tenants. Shared courses are visible to all tenants. Tenant-owned courses stay private. Tenant admins cannot see other tenants' courses. | Tenant admin manages users and cohorts and enrols them in available courses. Reports are limited to own tenant users. Content edit is only for the owner or site admin. | Private to its tenant unless a site admin marks it shared. | Enrolment is by tenant users through enrolment methods. Tenant admin enrol rights are per-tenant capabilities. | Workplace tenants and shared course settings. https://docs.moodle.org/en/Workplace_tenants (and Moodle Workplace docs) |
| Canvas | Account and sub-account tree | Courses belong to one sub-account. Sharing is via Blueprint (parent pushes to associated child courses in sub-accounts), Commons (opt-in share of a copy), or cross-listing sections. | Account-level permissions are a flag matrix per role (for example "Add/remove students", "View all grades", "Manage courses"), scoped to the account and its descendants. Parent account admins inherit down. Sibling sub-accounts have no rights on each other. | No access to a sibling sub-account's courses. | Admin with enrol permission adds users directly. Paid enrolment is not core to Canvas (there is no price gate), so the bypass question is moot. | Account > Permissions. https://community.instructure.com/ (Admin permissions guides), Blueprint guide https://community.instructure.com/en/kb/articles/661012-what-are-blueprint-courses |
| Open edX | Organisation (the `org` in the course key), with per-course roles | A course's org is fixed by its key. Other orgs do not get the course. Access is by course access role. Course catalogue visibility is per-course "Catalog visibility" (both, about page only, none). CCX gives a coach a custom copy for their own learners. | Roles: course staff, instructor, beta tester, data researcher, library user, plus org-level roles (org-wide staff or instructor via `org` scoped CourseAccessRole). Enrolment by staff is allowed via the instructor dashboard. | Staff of org A have no rights on org B's courses. Each access grant is explicit and per user or per org. | Instructor-dashboard enrolment bypasses the course mode (paid track) and enrolment start/end windows. This is a known gap, and paid is handled by the e-commerce add-on, not by enrolment. | Studio Course Team, Django admin `CourseAccessRole`. https://docs.openedx.org/en/latest/educators/ , https://edx.readthedocs.io/projects/edx-partner-course-staff/ |
| Docebo (Extended Enterprise) | Extended Enterprise tenant ("Enterprise") | Courses are not owned by tenants. Parent catalog items are assigned to a tenant via catalogs and enrolment rules. Tenants can also have their own catalogs and courses. | Per-tenant: which catalogs, courses, learning plans it can see. Power User profiles carry granular permission flags (enrol users, view courses, edit, view reports) scoped to a user set and a catalog or course set. | Nothing visible unless the parent explicitly assigns a catalog. | Power Users enrol "own" users in assigned courses. Paid courses go through the e-commerce flow. Admin enrolment is generally free of purchase, but a power user can enrol only where the permission is granted, and "enrol users" is a separate permission from "view". | Admin menu > Extended Enterprise and Power User Profiles. https://help.docebo.com/hc/en-us/sections/ (Extended Enterprise and Power Users) |
| TalentLMS | Branch | A course is assigned to one or more branches by an admin. Branch admins see only courses assigned to their branch. Branch can have its own courses. | Branch admin can manage users in the branch, and can "see and use" courses in their branch. Course creation can be a branch-level toggle. Reports are limited to the branch. | Course is invisible to a branch until added to it. | Branch admins add own users to branch courses. Price is a course property, and the admin assignment path skips the checkout. | Course > Branches tab. https://help.talentlms.com/hc/en-us/articles/ (Branches) |
| Absorb LMS | Department (and Tenant for Extended Enterprise) | Courses are "shared" to a department or tenant by the owning admin. Catalogue visibility is separate from enrolment rights. | Admin role permission sets (view courses, enrol, report). Department admins constrained to their department tree. Courses can be "shared with child tenants". | Not shared by default. Sharing is opt-in by owner. | Admin enrolment is allowed to shared courses. Eccommerce price applies to learner self-purchase. | Admin > Roles and Tenants. https://support.absorblms.com/ |
| LearnUpon | Portal (parent and child portals) | Parent portal shares courses to child portals (copies or shared). Child portal admins see shared courses in their portal. | Portal admin roles: Admin, Manager, Instructor, Group Leader. Report and enrol rights are per portal. | Child portal sees nothing until parent shares. | Child admin can enrol in shared courses. Ecommerce is a per-portal setting, so bypass is possible if the admin enrols directly. | Portal settings and "Share course" in Courses. https://support.learnupon.com/ |
| Totara | Tenant (multitenancy, built on Moodle's contexts) | Tenant-owned courses live in a tenant category. "Shared" courses sit in the system context and are available to all tenants. | Tenant domain manager, tenant user manager, tenant participant capabilities are separate flags. Default is no cross-tenant access, with a participation (isolation) mode setting. | Isolated. Can be set so tenant users are or are not allowed to see other tenants' users and courses. | Enrolment is by tenant domain manager via enrol plugins. Learner-self enrol rules apply per method. | Tenants guide. https://help.totara.com/docs/multitenancy |
| Thinkific Plus / Teachable | Account (one school per site) | Not multi-tenant in this sense. Thinkific Plus "Sites" can share a course via bundles or by duplicating. Teachable has no cross-school sharing. | Admin rights are account-wide. | Not applicable. | Admin enrolment (manual or by API) ignores price. | https://support.thinkific.com/ , https://support.teachable.com/ |
| Cornerstone | Division / OU (organisational unit) | Content is visible to OUs through catalogue and "Provider" and "Content Owner" rules. | OU-based security and "Learning Administrator" permissions with Target Population limits. | Visibility by explicit OU assignment. | Admin enrolment ("assign training") ignores approval workflows unless configured. | Admin > Security and Catalog Management. https://help.csod.com/ |

Confidence: high for Moodle, Canvas, Open edX, Totara and Workplace on structure. Medium for Docebo, TalentLMS, Absorb and LearnUpon on exact setting names. Low for Cornerstone, Thinkific and Teachable (included for completeness only).

## Common patterns

1. Isolation by default. Every multi-tenant platform here hides a course from another tenant until the owner (or a platform admin) explicitly assigns, shares or publishes it. None default to "other tenants see everything public".
2. Sharing is owner-side and opt-in. The borrowing tenant does not pull. The owner or the platform admin pushes.
3. "See in catalogue", "enrol users" and "view content / edit" are separate permissions. Moodle capabilities, Docebo power user flags, Canvas permission matrix and Totara capabilities are all independent flags, not a ladder. Edit and content-authoring rights stay with the owner.
4. Reporting is scoped to the tenant's own users, never to the course as a whole. This is the one right that platforms treat as safe and natural once enrolment is allowed.
5. Admin enrolment generally bypasses price. Almost every platform lets an enrol-capable admin skip checkout, because price lives on the self-enrol or e-commerce path, not on the enrolment record. The ones that guard it do so by a separate seat or licence mechanism (IOMAD licences, Docebo e-commerce). So "enrol" has to be a deliberate grant, never implied.

## Where platforms disagree

- Whether a shared course is shown to everyone (Workplace and Totara "shared" scope, which is site-wide) or to named tenants (Docebo catalogue assignment, TalentLMS branches, LearnUpon portals). Named tenants is the majority and is what the user wants.
- Whether grants are a ladder or independent flags. Capability systems (Moodle, Canvas, Docebo) use independent flags. Product-style systems (Absorb, LearnUpon) use a small number of sharing modes. Neither pattern gives implicit content preview to a viewer.
- Whether content preview is separately grantable. Most platforms fold it into "enrol" (an enrolled learner sees content) or into edit roles. Few expose "view without enrolling". Moodle (`course:view` for non-enrolled, guest access) and Canvas (public syllabus, "view" on account) do.

## Recommended structure for FreedomLS

Declare in course.md front matter a list of grants, one entry per named organisation (no wildcard), with independent boolean-style capabilities.

Suggested shape (illustrative):

```yaml
organisations: [org_a]            # owners / co-owners
organisation_access:
  - organisation: org_b
    capabilities: [see, enrol, progress]
```

Decisions:

1. Default for a public course of another organisation with no grant: hidden from the educator list and detail, and not registerable by educators. Every platform defaults to isolation. Learners of that organisation still find and self-join it through the normal public path with its price and application gates.
2. Independent flags, not a ladder. This matches Moodle, Canvas, Docebo and Totara, and it lets "enrol without preview" and "see without enrol" both be expressed.
3. `see` (a): lists the course in the educator list and detail with metadata only, no content. Cheap and safe. Gives the org a reason to know the course exists.
4. `enrol` (b): a separate flag, explicitly documented as bypassing the course-access backend price and application gates. Platforms agree this is the risky one, so it must be a deliberate named grant. Consider an `enrol` that implies `see`, since an educator cannot register onto a course they cannot see. Treat that implication as a validation rule, not a ladder.
5. `preview` (c): a separate flag that implies `see`. Content preview is rare as a standalone right across the platforms, so do not grant it through `enrol`. Learners get content through enrolment, educators do not need it.
6. `progress` (d): reporting limited to the granting organisation's own learners, never other orgs' learners. Safe, and it is the natural sequel to `enrol`. In practice, an org that has enrolled learners should always see their progress, so consider making this implicit in `enrol` rather than a flag. Open for a decision.
7. Co-ownership (listed in `organisations:`) is full access: see, enrol, preview and progress, plus management. Owner-side rights in every platform cover the whole set. This resolves the open question: co-ownership is enough, and no extra grant is needed.
8. Site-wide courses (no organisations) keep today's behaviour. Platforms with a "shared to all" mode (Workplace, Totara) treat it as a deliberate declaration, and an empty `organisations` is the same signal.
9. Validation: reject unknown organisation slugs and wildcards at content load time, reject duplicate entries for one organisation, and apply the implication rules above in one place.

Open flags for the spec author: whether `progress` is implied by `enrol`, and whether `audience: public` plus no grant should still let an educator see a course that their own learners are already enrolled in (an existing enrolment is a reasonable reason to show the course in their list; none of the platforms surveyed show this explicitly).

## Sources

- https://docs.moodle.org/en/Roles_and_capabilities
- https://docs.moodle.org/en/Course_categories
- https://docs.iomad.org/
- https://docs.moodle.org/en/Workplace_tenants
- https://community.instructure.com/en/kb/articles/661012-what-are-blueprint-courses
- https://docs.openedx.org/en/latest/educators/
- https://help.docebo.com/hc/en-us/sections/
- https://help.talentlms.com/hc/en-us/articles/
- https://support.absorblms.com/
- https://support.learnupon.com/
- https://help.totara.com/docs/multitenancy

status: ok
