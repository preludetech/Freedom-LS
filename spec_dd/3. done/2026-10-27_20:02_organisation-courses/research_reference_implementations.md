# Research: reference implementations of organisation-restricted course catalogues

Topic: reference_implementations. Method: web search summaries only (pages not deep-read; source code not inspected). Confidence is flagged per finding. Terms below belong to each system, not FLS.

## Findings per system

### Open edX (edx-organizations)
- Organization is a separate Django app/model holding publisher metadata: title, logo URL, certificate info. It is the entity that "creates and publishes courses". Course-to-org link is by the course key's `org` string, not a many-to-many restriction. (Confidence: medium)
- It is a publisher/ownership concept, not an access-control one. Visibility restriction is done by mapping orgs to separate LMS sites (site-org link decides which courses appear on a site), i.e. a deployment-level partition rather than a per-course ACL. (EduNext docs; medium-low, vendor doc)
- Studio can restrict who may create courses by organisation (commit "grant course/library creation rights by organization"). That is authoring-side only.
- Cards: an Open edX dashboard card proposal puts the organisation name on its own line above the course name and end date. The Organization Profile proposal says org name/logo/description data exists in edx-organizations but no frontend renders it.
- Sources:
  - https://pypi.org/project/edx-organizations
  - https://public.docs.edunext.co/en/latest/_sources/external/managers/configure_platform/manage_organizations.rst.txt
  - https://git.andalsoftware.com/Andal.LND/edx-platform/src/commit/48ad7effb1df704737351310d7c4dfcfd2521865
  - https://openedx.atlassian.net/wiki/spaces/OEPM/pages/6132891650/Proposal+Organization+Profile+Page+for+Open+edX
  - https://openedx.atlassian.net/wiki/spaces/OEPM/pages/4193484824
  - https://discuss.openedx.org/t/organization-user/4576

### Moodle Workplace (multi-tenancy)
- Each tenant owns a course category; its users see only courses in their tenant's category. A site-designated shared course category makes courses visible across tenants. A shared space can also appear on all tenants' dashboards.
- Learning catalogue lists only the courses the user can access, respecting tenant permissions; this is the enforcement point (filter at catalogue query).
- Adding courses from outside a tenant category needs capability `moodle/category:viewcourselist` at category context.
- Privacy caveat: users of other tenants can be visible in participant lists/forums of shared courses; docs recommend Separate Groups.
- Model: course belongs to exactly one container (tenant category or the shared one), not many-to-many. Many-to-many is approximated via the shared category.
- Sources:
  - https://docs.moodle.org/en/Catalogue_Tenants
  - https://docs.moodle.org/en/Programs_Tenants
  - https://docs.moodle.org/503/en/Staff_Tenants
  - https://docs.moodle.org/310/en/Multitenancy

### Canvas (accounts / sub-accounts)
- Hierarchy: root account with nested sub-accounts; each course lives in exactly one account/sub-account. Permissions flow down, not up; moving courses between sub-accounts requires admin on both parents. Single-owner tree, not many-to-many.
- Canvas Catalog is a registration front end layered over this; no source found on how listings map to sub-accounts.
- Sources:
  - https://community.canvaslms.com/docs/DOC-2963
  - https://community.canvaslms.com/t5/Admin-Guide/How-do-I-view-and-manage-a-sub-account/ta-p/260
  - https://help.ohio.edu/TDClient/30/Portal/KB/ArticleDet?ID=1268

### Docebo (branches and catalogs)
- Closest to many-to-many: a Catalog is a bundle of courses and learning plans plus a list of assigned users, groups, or branches. Course visibility to a branch is achieved by assigning the branch to a catalog (not on the course itself). A course can be in many catalogs; a catalog can be assigned to many branches. Item-level settings also affect what is shown. (Official help plus forum answers; branch-on-course not available, forum-sourced.)
- Learning-plan courses may need catalog visibility for power users (forum-reported, unverified).
- Sources:
  - https://help.docebo.com/hc/en-us/articles/360020125439
  - https://community.docebo.com/product-q-a-7/adding-courses-for-specific-branch-visibility-only-15040
  - https://community.docebo.com/product-q-a-7/does-a-course-in-a-learning-plan-have-to-be-in-a-visible-catalog-for-the-user-to-see-it-3278

### LearnDash (groups)
- Course access restricted via groups; closed groups restrict access, enrolment manual or via ecommerce/membership. Course-group is many-to-many. Group "Display & Content" setting controls whether the course list is visible to everyone or enrollees only. Access Controls (LearnDash App) can hide restricted courses or show them with limited access (hide-vs-show-locked is a real design choice).
- No source found on org/group info on course cards (Course Grid cards are configurable by element only).
- Sources:
  - https://learndash.com/support/docs/group-access-settings/
  - https://learndash.com/support/kb/core/uncategorized/group-display-content-settings/
  - https://learndash.com/support/kb/learndash-app/uncategorized/manage-access-controls/
  - https://learndash.com/support/kb/add-ons/courses/course-grid/

### TalentLMS branches
Not researched (no search run); gap.

## Patterns relevant to FLS
1. Two models exist: single-owner container (Moodle tenant category, Canvas sub-account, Open edX org string) vs many-to-many link (Docebo catalog-branch, LearnDash group-course). FLS idea requires many-to-many, so a direct course-organisation M2M is the Docebo/LearnDash style.
2. No mature system uses an explicit "unrestricted" flag; unrestricted equals shared/global (Moodle shared category, Docebo catalog with no branch limit). An FLS design must define semantics of a course with zero organisations (open to all vs hidden) explicitly.
3. Enforcement is at catalogue/listing query level (Moodle catalogue, Docebo catalogs), plus direct-URL/detail access must be checked separately; Moodle leaks via participant lists in shared courses.
4. Independent same-named per-organisation copies are the norm (separate courses per tenant category in Moodle/Canvas); name uniqueness is not enforced across containers, so FLS should not assume unique course names.
5. Cards: only Open edX proposals show the organisation as its own line above the course title (name/logo from org metadata). Card-level org display for a single-org course is therefore a lightweight, conventional pattern; the "single organisation only" condition from the idea has no reference precedent found.
6. Hide-vs-show-locked (LearnDash) is a choice; idea implies hide for non-members.

## Gaps
Source code not read; Open edX enforcement details, TalentLMS, and Moodle audiences unverified.

status: ok
