# Research: reference implementations of cross-organisation course grants

Verification key: [V] fetched this run; [K] from recall of the source, not re-fetched (URL given, verify before quoting).

## 1. Open edX [V]

**Grant data model.** `CourseAccessRole(user FK, org CharField, course_id CourseKeyField blank, role CharField)`, `unique_together (user, org, course_id, role)`. Blank `course_id` means an org-wide role. Blank `org` means a global role. The grant is user to role to scope (org or course). It is not org to org. Source: https://github.com/openedx/edx-platform/blob/master/common/djangoapps/student/models/user.py

**Where the check lives.** `student/roles.py`: `RoleBase.has_user` delegates to a per-user `RoleCache`. `has_role` looks only in the bucket for that course and requires `access_role.org == org`. Org-level rows sit in an "ungrouped" bucket, so a course-scoped check never sees org-level rows and the reverse. Roles inherit through `BASE_ROLE` (limited staff passes a staff check). https://github.com/openedx/edx-platform/blob/master/common/djangoapps/student/roles.py

**Visibility and enrolment are separate named actions.** `courseware/access.py` `has_access(user, action, obj)` dispatches to `_has_access_course`:
- `see_in_catalog` is granted if `catalog_visibility == CATALOG_AND_ABOUT`, or the user has staff access.
- `see_about_page` is granted for `CATALOG_AND_ABOUT` or `ABOUT`, or staff.
- `see_exists` is `load or enroll`.
- `enroll` checks, in order: a `CourseEnrollmentAllowed` row for the user's email, then staff, then `invitation_only` denies, then open enrolment dates.
- `load` never checks enrolment.

The pattern matches our three flags: independent named actions, with staff and an explicit allow-list row as overrides. `CourseEnrollmentAllowed` is the nearest edX analogue of "grant waives the gate": an explicit allow row bypasses `invitation_only`. https://github.com/openedx/edx-platform/blob/master/lms/djangoapps/courseware/access.py

**List filtering.** The catalogue and dashboard do not call `has_access` per row at scale. They filter `CourseOverview` rows in Python or queryset (`catalog_visibility`, dates), and call `has_access` only for fine checks. Visibility is a field on the course, not a grant to another org. edX has no org-to-org share. Cross-org access is done by giving a user a role in the other org.

**Takeaway.** Strong on action naming and staff override. It is not a model for org-to-org grants.

## 2. Moodle IOMAD (Moodle Workplace is closed source) [K]

**Grant data model** (from `local/iomad` `db/install.xml`; the file URL 404'd on fetch, so verify):
- `company_course (companyid, courseid, departmentid, autoenrol)`: the course is placed in a company's department. In that setup the course belongs to that company.
- `company_shared_courses (companyid, courseid)` (older IOMAD kept this in `iomad_courses.shared`): a course flagged shared (0 not shared, 1 open to all, 2 closed to listed companies) is visible to the named companies. Mode 2 is a named-company allow list, as in our design.
- `companylicense` (allocation, validlength, expirydate, used) plus `companylicense_courses` and `companylicense_users`: seat-based licences per company and course, with per-user allocation rows.

**Where the check lives.** In `local/iomad/lib/company.php` and the `company_course_users_table` and `company_course_selector` classes. These are ad-hoc SQL builders that join `company_course` or `company_shared_courses` for the company the manager belongs to. There is no central manager. Each admin page builds its own query, and the bugs were of the "listed everything" kind. An IOMAD GitHub issue confirms that deleting a company course removes enrolments and licence allocations together: https://github.com/iomad/iomad/issues/1961

**Takeaway.** Confirms the three-state `shared` model (not shared, closed allow-list, open to all), and that licences are a separate seat table (our deferred seat caps). Warns against per-page SQL.

## 3. Totara multitenancy [V via docs]

**Grant data model.** Each tenant has its own context, a top-level course category and an audience (all members auto-added). Members are users under the tenant context. Participants are non-members added to the tenant audience. Course visibility is audience-based. A course in a tenant category is limited to that tenant. Sharing across selected tenants is the support-recommended workaround: put the course in a site-level category and restrict it with a dynamic audience with the rule "is a member of Tenant". There is no first-class per-tenant grant, and `see`, `register` and `preview` are not separate. Isolation mode controls whether tenant users see site-level content at all.
- https://totara.help/docs/multitenancy-in-totara-learn
- https://totara.help/docs/what-is-multitenancy
- https://totara.atlassian.net/wiki/spaces/DEV/pages/121186086/Multitenancy

**Where the check lives.** In Moodle capability and context checks plus a tenant-aware SQL filter on the course list (`totara_tenant` joins on category context path). It is enforced centrally in the core `get_courses` and category listing queries. Visibility is by context path, so no per-page filtering.

**Takeaway.** Tenant ownership is a single root relation, and sharing is the exception expressed as a named audience. Our "owner orgs + named grantee orgs" matches this, but with typed flags.

## 4. django-guardian, django-rules, django-tenants

- **django-guardian** [K]. `UserObjectPermission` and `GroupObjectPermission` rows: `(user|group, permission FK, content_type, object_pk, content_object GenericFK)`. Checks via `user.has_perm("see_course", obj)` through an auth backend. List filtering via `get_objects_for_user(user, perm, qs)`, which builds an `IN (object_pks)` subquery. A grant is a DB row per principal, per object, per permission. The principal is a user or group, not an org, so an Organisation would need to be a Group. Generic FKs and `object_pk` as a char field make joins slow and lose referential integrity. Fits runtime-editable grants, not file-declared ones. https://django-guardian.readthedocs.io/en/stable/userguide/check.html and https://django-guardian.readthedocs.io/en/stable/api/guardian.shortcuts.html
- **django-rules** [K]. No grant table. Predicates are Python functions `@rules.predicate def can_register(user, course)` combined with `&`, `|`, `~`, registered with `rules.add_perm("courses.register", ...)`. Checks via `user.has_perm` or the `@permission_required` view decorator. It is object-level only. It has no queryset integration, so list filtering must be written separately and can drift from the predicate. This is the exact "list and action checked separately" risk the previous research flagged. https://github.com/dfunckt/django-rules
- **django-tenants** [K]. Schema-per-tenant on PostgreSQL. Isolation is by `search_path`, so cross-tenant grants cannot be expressed in the tenant schema. Shared content must live in the public schema (`SHARED_APPS`) and be referenced by tenant rows. Cross-tenant sharing is by design a public-schema model plus a per-tenant link table. Not applicable to FLS, which uses site-aware row filtering. https://django-tenants.readthedocs.io/en/latest/

## 5. Declaring grants in files or config rather than DB rows

No surveyed platform declares org-to-org grants in course content files. Edx, Moodle and Totara all store them in DB rows set through admin UI. The nearest file-declared patterns:
- **Open edX** course policy (`policy.json` / `course.xml` attributes such as `catalog_visibility`, `invitation_only`, `enrollment_start`) is part of the course export and re-imported into a model field. The course file carries the access policy, but only for self-attributes (not named grantees). [K] https://docs.openedx.org/en/latest/educators/references/course_development/policy_json.html
- **Kubernetes-style GitOps and Zanzibar tuples** declare grants as data checked into source and synced to the store. OpenFGA and SpiceDB support loading tuples from files. https://openfga.dev/docs/modeling/getting-started
- **SCORM Cloud dispatch** is API-created, not file-declared (see `research_permission_model_patterns.md`).

FLS front matter is therefore novel but sound. The pattern that supports it is "file is source of truth, importer syncs into a DB projection, checks only read the DB".

## 6. Comparison

| System | Grant is | Check lives in | List filtering |
|---|---|---|---|
| Open edX | user-role-(org or course) row | `has_access` per action, `RoleCache` | field filters on `CourseOverview` plus per-row `has_access` |
| IOMAD | `(company, course)` row, shared mode flag | per-page SQL helpers | per-page joins (drift-prone) |
| Totara | audience or category membership | core course list SQL (context path) | central in the query |
| guardian | `(principal, perm, obj)` row | auth backend `has_perm` | `get_objects_for_user` subquery |
| rules | none (predicate code) | predicate via `has_perm` | none, separate code |
| django-tenants | schema | `search_path` | schema isolation |

## 7. What FreedomLS should borrow

1. **Named actions, one entry point (Open edX `has_access`).** One function `has_course_access(organisation, action, course)` with actions `see`, `register`, `preview`. `register` and `preview` imply `see`. The owner organisation has all. Detail, preview, register and pickers all call it. Return 404 on failure.
2. **Queryset companion in the manager, not the view (Totara core-query lesson, IOMAD anti-lesson, rules gap).** Provide `Course.objects.visible_to(organisation, action="see")` built from the same grant table, and test that its result set equals the per-object function over a fixture. This closes the "list and action drift" bug.
3. **A DB projection of front matter, not a front-matter read at request time.** The importer parses `course.md` and writes `CourseOrganisationGrant(course FK, organisation FK, see, register, preview)` with `unique(course, organisation)`. Implied flags are normalised on import (a `register` row sets `see`). This is guardian's row-per-grant model without generic FKs, and it is joinable and indexable. The file stays the source of truth, so a grant removed from the file is deleted from the table on re-import.
4. **Owner orgs from existing `organisations:`** (IOMAD `company_course`, Totara tenant category). Do not self-grant. No `organisations:` means today's behaviour, as the answers already decided.
5. **Allow-list only (IOMAD mode 2), no "all companies" mode (mode 1).** Matches the no-wildcard answer.
6. **Explicit allow overrides the gate (edX `CourseEnrollmentAllowed` bypasses `invitation_only`).** A `register` grant bypasses price and application gating for educator registration only. Learner self-join is untouched.
7. **Existing registration stays visible (answer 3).** Union of `visible_to(...)` and courses with a registration owned by the current organisation. Do this in the same queryset method.
8. **Defer seats (IOMAD `companylicense`).** Add a `seats` column later on the same grant row.
9. **Do not borrow:** guardian generic FKs, rules predicates without queryset, django-tenants schema isolation, Totara's dynamic-audience workaround.

Sources: edX https://github.com/openedx/edx-platform (files above); Totara docs URLs above; IOMAD https://github.com/iomad/iomad; guardian https://django-guardian.readthedocs.io; rules https://github.com/dfunckt/django-rules; django-tenants https://django-tenants.readthedocs.io.

status: ok
