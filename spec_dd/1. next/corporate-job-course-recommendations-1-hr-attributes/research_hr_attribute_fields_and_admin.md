# Research: HR attribute fields, per-organisation lists and the Django admin

For `idea.md` in this directory (spec 1 of the Registration rules effort). Project words are used
for FLS (`Learner`, `Organisation`, `OrganisationMember`, `Cohort`); other systems keep their own
terms, attributed. Settled and not reopened: job title, department, location (each a
per-`Organisation` list model) and start date are fixed fields on `Learner`; managed in the Django
admin; nothing named "role".

## Short answer

- `Learner.organisation` is a required, fixed FK. One `Learner` row has exactly one organisation, so
  "which organisation's list" always has a single answer: `learner.organisation`. A user in several
  organisations has several `Learner` rows, each with its own attributes. Nothing in the code today
  stops a `Learner` pointing at another organisation's list entry, because no such FK exists yet;
  the spec must add that guard (model `clean()` plus a narrowed admin queryset).
- "Start date" should be the date the learner started **at the organisation** (hire date), not the
  start of their current job. Every HR system and both SCIM and Entra have an organisation-level
  hire date; none has a portable "start in current job" field.
- A flat list is enough for exact-match rules. Hierarchy exists in real HR data, but flattening it
  loses nothing the rules in this effort need.
- All four attributes should be nullable/blank. A learner who is not yet described must remain valid.
- Present the three lists as own `ModelAdmin`s with an organisation filter, plus read-write
  tabular inlines on the Organisation page is optional. Own admins are the safer default (reasons
  in section 4).
- No vocabulary conflicts found in the project's vocabulary file; one real code collision to avoid
  (section 5).

## 1. Field semantics in other systems

| Concept | SCIM (RFC 7643) | Microsoft Entra / Graph `user` | Workday | BambooHR |
|---|---|---|---|---|
| Job title | core `title` (4.1.1) | `jobTitle` | job profile / business title | `jobTitle` |
| Department | enterprise ext. `department` (4.3) | `department` (string, max 64 chars) | supervisory org / cost centre | `department` |
| Location | no single attribute; `addresses` (work address) is the nearest, and enterprise has `organization`, `division`, `costCenter` | `officeLocation`, plus `city`, `country`, `companyName` | location (a reference value) | `location` (a list value) |
| Start date | none. 4.3 lists only `employeeNumber`, `costCenter`, `organization`, `division`, `department`, `manager`; `meta.created` is when the SCIM resource was made, not a hire date | `employeeHireDate` (DateTimeOffset): "the date and time when the user was hired or will start work in case of a future hire" | `Hire Date` (latest hire event), `Original Hire Date` (first ever employment), `Continuous Service Date` (overridable, used for benefits and length of service) | `hireDate`, `originalHireDate` |

Findings:

- **Start date is the hire date at the organisation.** Entra defines it that way, including future
  hires. Workday has three variants; the one an LMS wants is `Hire Date` (most recent hire event),
  not `Continuous Service Date`, which HR can override for benefits. "Start in the current job" is
  a position-effective date in Workday job history and has no field in SCIM or Entra, so storing it
  here would have nothing to sync from.
- **SCIM has no hire date**, so a later SCIM sync cannot fill start date from the standard schema.
  It would arrive through a custom schema extension or SSO claims. Do not let that shape the model.
- **Entra's `employeeHireDate` is a date-time**; HR use is a calendar date. A `DateField` on
  `Learner` is right, and the rules in decision 9 ("on or after", "before") compare dates.
- **Departments and locations are free text in SCIM and Entra** (strings, not references), which is
  the exact mismatch the per-organisation lists exist to remove. A sync would map an incoming string
  to a list entry (case-insensitive, trimmed) and decide separately whether to create missing ones.
  Integrations in the wild behave the same way: Greenhouse exports a department, office or job title
  to BambooHR only if it exactly matches an existing BambooHR value.
- **Names that map cleanly.** Field names on `Learner`: `job_title`, `department`, `location`,
  `start_date`. Model names: `JobTitle`, `Department`, `Location`. These line up with SCIM `title`,
  enterprise `department`, Entra `jobTitle`, `department`, `officeLocation`. For `start_date`, keep
  the name and put "the date the learner started working at the organisation (hire date)" in
  `help_text`; do not call it `hire_date` only if the product owner prefers the learner-facing
  word. The mapping note is the important part. Using `location` rather than `office` keeps room
  for remote or regional values. The list entry's text field should be `name`, matching `Cohort.name`
  and `Organisation.name`.

Sources: RFC 7643 (https://datatracker.ietf.org/doc/html/rfc7643, sections 4.1.1 and 4.3);
Microsoft Graph user resource, via mirrors and Q&A because the Learn page was too large to read
(https://graphpermissions.merill.net/permission/User.ReadWrite,
https://learn.microsoft.com/en-us/answers/questions/2284391/how-to-provision-employeehiredate-through-graph-ap);
Workday date fields (https://doc.workday.com/admin-guide/en-us/human-capital-management/staffing/basic-staffing-information/dan1370797452783.html,
https://dbm.maryland.gov/sps/Documents/Workday_Date_Field_Guide.pdf); BambooHR field list and the
exact-match behaviour (https://docs.bytechef.io/reference/components/bamboohr,
https://support.greenhouse.io/hc/en-us/articles/201177624). Not verified from a primary source:
Entra `jobTitle` and `officeLocation` descriptions and length limits, BambooHR's own help pages.

## 2. Flat or hierarchical lists

- Real HR data is often hierarchical: Workday supervisory organisations and most Entra/AD
  departments form trees; locations run country > region > city > building. SCIM and Entra
  themselves expose department and office as a single string, so the interchange format is flat.
- The rules for this effort (decisions 2 and assumptions in the roadmap) are exact list-entry
  matching with AND across attributes and OR within one. They never say "anywhere under Finance",
  so a tree adds no capability for them and adds real cost: ancestor queries, rule semantics for
  "includes children", a tree editor in the admin, and ambiguity when an entry moves.
- Recommendation: flat per-organisation lists now. An organisation that wants "Finance > Audit"
  can name entries "Finance - Audit". Keep the door open by not storing anything that blocks a later
  nullable `parent` FK on these models; do not add it now (the project's convention is not to build
  what is not requested). Flag to the product owner that "everyone in Africa" style rules need
  either several ORed list entries or a later hierarchy spec.

## 3. Nullable? Organisation membership? Which organisation's list?

What the code says:

- `Learner` (`freedom_ls/learner_management/models.py`): `user` FK (CASCADE), `organisation` FK to
  `freedom_ls_organisations.Organisation` with `on_delete=PROTECT` and **no null/blank**,
  `is_active`, `created_at`. `UniqueConstraint(site, user, organisation)`
  (`unique_learner_per_organisation`). Its docstring: "A user may hold a Learner row in more than one
  organisation ... an enrolment with no organisation association cannot be represented."
  So a learner always belongs to exactly one organisation per row; a user with none has no `Learner`
  row; a user in several has several rows. `ensure_learner(user, organisation)` in
  `freedom_ls/learner_management/utils.py` is the single get-or-create path.
- `Organisation` (`freedom_ls/organisations/models.py`) has `name`, `slug`, logos, `is_default`; no
  settings and no list models. `Organisation` and `Learner` are both `SiteAwareModel`.
- Existing same-organisation guard precedent: `CohortMembership.clean()` raises "Learner and cohort
  must belong to the same organisation." using the helper `_relations_are_set` (so an unset FK
  yields a field error, not `RelatedObjectDoesNotExist`). Nothing equivalent exists for attributes
  because none exist.

Consequences for the spec:

- **Which list a learner picks from:** `learner.organisation`'s list, always. Each of the three
  list models has a required FK `organisation` (PROTECT, mirroring `Cohort.organisation`).
- **What stops a cross-organisation pointer:** nothing, by default. A plain FK from `Learner` to
  `Department` accepts any department on the site. Needed: (a) `Learner.clean()` raising when
  `job_title/department/location.organisation_id != self.organisation_id`, written like
  `CohortMembership.clean()` with `_relations_are_set`; (b) the admin form narrowing each queryset
  to the learner's organisation (section 4). The model check is the real guard; the narrowing is
  usability. `Learner.save()` through the ORM, factories, `ensure_learner` and later CSV/SCIM paths
  bypass `clean()`, so spec 5 and any sync must call `full_clean()` or repeat the check.
  A database-level guarantee is possible with a composite FK, which Django does not support
  natively; do not attempt it.
- **Changing a learner's `organisation` after attributes are set** would leave stale pointers.
  Learner's organisation is not meant to change; the clean() check also catches this on an edit.
- **Nullability:** all four fields `null=True, blank=True`. Reasons: existing `Learner` rows have no
  values (a migration cannot invent them); HR data arrives piecemeal; a rule that needs a value
  simply does not match a learner with `NULL`. For the list FKs use `on_delete=PROTECT`
  (matches the roadmap's "protected from deletion" option, and `Cohort.organisation`/`Learner.organisation`
  use it); `SET_NULL` would silently drop a learner out of rules, which is the failure the idea
  warns about. This is the open question on entries still in use. Deactivation (an `is_active`
  flag hidden from pickers) is more work than PROTECT and only matters once specs 2, 4 and 5 need
  to retire an entry that has users; the admin already uses "deactivate, never delete"
  (`has_delete_permission` returns False on `LearnerAdmin` and `OrganisationAdmin`). Product owner
  question below.
- `related_name`s: set explicit ones (`learners`) on the three FKs, since `Learner` will have three
  FKs to different models; otherwise default `learner_set` is fine but each model gets only one.

## 4. Django admin

Existing state (read from the code):

- Unfold is in use: `from unfold.admin import TabularInline` in
  `freedom_ls/learner_management/admin.py`; `GuardedSiteAwareModelAdmin(ModelAdmin, GuardedModelAdmin)`
  in `freedom_ls/site_aware_models/admin.py` uses Unfold's `ModelAdmin`. `SiteAwareModelAdmin` sets
  `exclude = ["site"]`.
- The `fls-dev:admin-interface` skill (`claude_plugins/fls-dev/skills/admin-interface/SKILL.md`)
  says: extend `SiteAwareModelAdmin`; inlines use `SiteAwareTabularInline` or
  `SiteAwareStackedInline` (the code uses `unfold.admin.TabularInline` directly, so follow whichever
  `site_aware_models/admin.py` actually exports when writing the spec); never show or edit `site`;
  it defers the generic rules to `ds:admin-interface` (unfold, guardian enabled).
- `LearnerAdmin` has `form = LearnerAdminForm`, explicit `fields`, `autocomplete_fields = ["user",
  "organisation"]`, `list_filter = ["organisation", "is_active"]`, inlines on the change page only
  (`get_inlines` returns `[]` on add), and the `LEARNER_SUMMARIES` seam.
- `OrganisationAdmin` is `GuardedSiteAwareModelAdmin`, explicit `fields = ["name", "slug", "logo",
  "logo_on_dark", SUMMARIES_FIELD]`, `inlines = []` extended by `learner_management/admin.py`
  (appends `OrganisationCohortInline` and `OrganisationLearnerInline`, both with `per_page`,
  `ordering`, `show_count`, `tab = True`). The switch field must be added to `fields` there, or it
  will not render. It is declared in `organisations`, so a field on `Organisation` is easy; a
  settings row elsewhere would need a new seam. `OrganisationAdminForm` is in
  `freedom_ls/organisations/forms.py` (not read in detail).
- Forms: `ConstraintValidationFormMixin` (`freedom_ls/site_aware_models/forms.py`) is mandatory for
  any model with a site-scoped `UniqueConstraint`, because `site` is excluded from admin forms and
  an excluded field disables the constraint check. Each model in `learner_management/forms.py` has
  a form of this shape.
- Scoped learner dropdown precedent: `CohortMembershipInline.formfield_for_foreignkey` narrows the
  queryset from `request.resolver_match.kwargs["object_id"]` on the change page only, and
  `ScopedLearnerAutocompleteSelect` carries the scope on the autocomplete URL because
  "one shared endpoint" builds results from `get_search_results` and never sees the narrowed
  formfield queryset. `LearnerAdmin.get_search_results` honours those params.

Recommendations for the three lists:

1. **Own `ModelAdmin` for each list** (`JobTitleAdmin`, `DepartmentAdmin`, `LocationAdmin`) based on
   `SiteAwareModelAdmin`, with `list_display = ["name", "organisation"]`, `list_filter =
   ["organisation"]`, `search_fields = ["name"]`, `ordering = ["organisation__name", "name"]`,
   `list_select_related = ["organisation"]`, and `autocomplete_fields = ["organisation"]`. Reasons:
   the lists can be long (hundreds of locations), an inline pages poorly and edits four things on
   one page; the autocomplete from `Learner` requires `search_fields` on the target admin anyway;
   bulk typing is faster in a changelist with an add form. Adding an Organisation-page inline per
   list on top is optional; the existing page already carries two tabs and a third to fifth would
   crowd it. If any is added, copy `OrganisationCohortInline` (paginated, `show_change_link`).
2. **Learner admin**: add the four fields to `fields` (grouped in an "Work" fieldset), and make the
   list fields narrow to the learner's organisation. Two options:
   - Plain `<select>` limited to the learner's organisation via `LearnerAdminForm.__init__`
     (queryset `.filter(organisation_id=self.instance.organisation_id)` on change; on add, when
     there is no organisation yet, leave the attributes out of the add form with `get_fields` the way
     `get_inlines` already hides panels on add, or accept any entry and let `clean()` reject). Simple
     and safe for lists of dozens.
   - `autocomplete_fields` for the three: needs `search_fields` on each list admin, and the shared
     endpoint does not see the narrowed queryset (the same trap `ScopedLearnerAutocompleteSelect`
     solves). It would need a scoped widget and a `get_search_results` filter on each list admin.
     Larger; only worth it if lists are expected to run into hundreds. I recommend the plain select
     for this spec; `Learner` model `clean()` remains the guard either way.
   - Note the add page has no organisation until the first save in the browser; the simplest
     rule is "organisation first, attributes on the second edit", or an organisation select that
     always posts first. State which in the spec.
3. **Case-insensitive uniqueness per organisation.** Existing constraints are plain
   `UniqueConstraint(fields=["site", "organisation", "name"])`, which is case-sensitive on
   PostgreSQL. Options: (a) `UniqueConstraint(Lower("name"), "site", "organisation",
   name=...)` (functional constraint; Django 6 supports expressions positionally with field names, but
   `fields=` and expressions cannot be combined by keyword; check on write). (b) a stored
   normalised key. Prefer (a). Caveat: `ConstraintValidationFormMixin._reworded` only rewrites
   messages for constraints with `fields`; an expression constraint falls back to Django's generic
   message and the form-level error key, so also add a model `clean()` / form `clean_name` that does
   `Model.objects.filter(organisation=..., name__iexact=name)` to give a field error on `name` ("A
   department with this name already exists"). `UniqueConstraint.validate` for expressions also
   needs `site`/`organisation` not excluded: `site` is handled by the mixin, `organisation` is
   rendered.
4. **Trimming.** A form `CharField` strips surrounding whitespace by default (`strip=True`), so the
   admin is covered. The ORM, factories and later imports are not. Normalise in the model: strip and
   collapse internal runs of whitespace in `save()` (and in `clean()` so the uniqueness check sees
   the normalised value). Case is kept as typed for display ("IT" must not become "It"); only
   comparison is case-insensitive. Reject an empty name after stripping. Set a `max_length`
   (150, as `Cohort.name`); Entra's department limit is 64, so a sync is not blocked by 150.
5. Make `LearnerAdmin.list_display` / `list_filter` offer `department`, `job_title`, `location`
   filters (filter scoped to organisation is awkward; plain filters will list every organisation's
   entries; a `list_filter` on the FK is acceptable for now but flag it, and `search_fields` could
   add `department__name`). Add `list_select_related` entries for the three to avoid N+1.

## 5. Vocabulary conflicts

`claude_plugins/sdd/resources/domain_vocabulary.md` contains rules only, no term list; the project
points to `.claude/sdd/config.md` "Vocabulary Sources" (not read: the config lives outside the files
I was given, and the code is the fallback vocabulary). Code search for collisions:

- "Role" is taken (`role_based_permissions`, `ObjectRoleAssignment`, `organisation_admin`,
  `cohort_admin`); the idea already avoids it.
- `Organisation`, `OrganisationMember`, `Learner`, `Cohort` are taken; do not call a list entry an
  "organisation unit". `Department` is not a model today (grep of the vocabulary file found none;
  confirm with a code grep when writing the spec).
- "Location" has no model in `learner_management`; check `freedom_ls/` for a `location` field or
  model before the spec (e.g. an event or address field). "Title" is dangerous in this codebase:
  `Course.title`, topic titles and `course__title` appear throughout, so use `job_title` and
  `JobTitle` and never a bare `title`. "Start date" is not a field name elsewhere; there are
  `start_time` (`FormProgress`) and `registered_at`, so `start_date` is distinct, but state in the
  spec that it is not the date a learner started a course.
- "Level" and "grade" are not used, avoid them for seniority.

## 6. Common pitfalls with LMS user-attribute management

(From general LMS practice and the research already in this effort; not separately sourced.)

- Free-text attributes fragment groups ("Finance", "finance ", "Fin."). Exact lists, trimmed and
  case-insensitively unique, are the fix; the idea does this.
- Stale attributes: HR changes are not mirrored in the LMS, so rules act on out-of-date facts. The
  switch plus the attributes being always editable helps; say who owns the data and keep
  `updated_at` visible on the learner page (consider an `attributes` changed timestamp only if a
  later spec needs it).
- Renamed or merged entries ("Marketing" becomes "Brand"): editing the entry's `name` renames it
  for every learner and rule, which is usually what the admin wants. A merge is not supported
  without moving learners one by one; say so as out of scope.
- Deleting an entry in use: PROTECT shows a long "protected objects" page in the admin; a clear
  message and a "learners using this" count in `list_display` help.
- Organisation-wide cross-contamination: multi-tenant lists must never leak into another
  organisation's picker; the narrowing and `clean()` above matter more than the UI.
- Required-ness: making attributes mandatory blocks learner creation from every other path
  (self-registration, SSO, imports). Optional is the right default.
- Learners belonging to several organisations get separate attribute sets per `Learner`, which
  can surprise an admin who expects one person-level profile. State it in the admin help text.

## Recommendations

1. Models in `learner_management`: `JobTitle`, `Department`, `Location` (each `SiteAwareModel`,
   `TimestampedModel`, `organisation` FK PROTECT, `name` CharField(150), case-insensitive unique per
   `(site, organisation, Lower(name))`, whitespace normalised on `save()` and `clean()`).
2. On `Learner`: `job_title`, `department`, `location` (nullable FKs, PROTECT, explicit
   `related_name`s) and `start_date` (nullable `DateField`, help text "the date the learner started at
   the organisation (hire date)"). `Learner.clean()` rejects an entry from another organisation,
   written like `CohortMembership.clean()`.
3. Flat lists, no hierarchy now.
4. Admin: three own `SiteAwareModelAdmin`s with organisation filter; Learner admin shows the four
   fields in a "Work" fieldset with plain selects limited to the learner's organisation; add the
   switch to `OrganisationAdmin.fields` (explicitly listed there).
5. Add form-level and model-level case-insensitive duplicate errors on `name` (the mixin does not
   reword expression constraints).
6. Document in the spec that ORM and import paths bypass `clean()` and must call `full_clean()`.

## Questions only the product owner can answer

1. Should start date mean hire date at the organisation (recommended) or the start of the current
   job? The latter has no field in SCIM or Entra, and Workday needs job-history effective dates.
2. For an entry still referenced: protect from deletion (simplest, recommended) or deactivate and
   hide from pickers (more work, needed if admins must retire entries with users on them)?
3. Is a flat list acceptable, with "Finance - Audit" naming, or do any clients need a department or
   location tree for rules ("everyone in Africa")?
4. Do admins ever need to merge two entries into one? If yes, that is a separate small feature.

status: ok
