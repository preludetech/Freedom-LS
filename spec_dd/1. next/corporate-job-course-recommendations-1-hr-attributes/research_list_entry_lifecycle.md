# Research: lifecycle of a job title / department / location list entry

Question: what happens to an entry that learners or rules still reference.

## Recommendation (findings first)

1. **Deactivate, and also PROTECT.** Each list entry model gets `is_active` (default True). Retiring
   an entry means unticking `is_active`, never deleting. The `Learner` foreign keys and (spec 2) the
   rule-condition references use `on_delete=models.PROTECT`, so a hard delete of an in-use entry is
   refused. An unused entry may still be deleted (typo cleanup).
2. **Inactive entries leave every picker but stay valid where already chosen.** A learner keeps an
   inactive entry; it displays normally; rules that name it keep matching it (see below). New
   assignments cannot choose it.
3. **Rename in place** (edit `name`). Every reference follows. That is desirable: a rename is the
   same job/department/place under a new label. **Merge is out of scope** for spec 1 (it is a
   repoint-then-deactivate admin action, which can be added later without a schema change).
4. **Uniqueness:** one entry per case-insensitive trimmed name per organisation, enforced by the
   database. Names are stripped on `clean()`/`save()`.

## 1. How other products retire lookup values

- Workday: inactivating an organisation is a business process with preconditions (move workers and
  positions out, finish in-process events); it is not a delete, and history is kept. Integrations
  can be left with stale records. Source:
  https://doc.workday.com/admin-guide/en-us/manage-workday/organizations/manage-organization-concepts/dan1395087690031.html
  and https://www.servicenow.com/docs/r/SogDT~k7ktsbe1ZYegnaLg/q7M9iWd0TNnPPKalql~2Fg . Search found
  nothing on job profile or location inactivation specifically (not verified).
- Cornerstone OU: each OU has an Active setting; admin lists hide inactive OUs unless "Include
  Inactive" is ticked; edits carry a Reason for Change audit trail. Behaviour for users already in a
  deactivated OU was not found (not verified).
  https://help.csod.com/help/csod_0/Content/System_Configuration/Organizational_Units/Create_Organizational_Unit.htm
- Docebo: a branch with users attached (active or not) cannot be deleted; users must be moved first
  (community answers, not official docs). Deactivating users does not unenrol them and inactive
  users stay in groups, which silently affects enrolment rules.
  https://community.docebo.com/product-q-a-7/do-you-remove-deactivated-users-from-branches-groups-lp-s-13259
  https://community.docebo.com/product-q-a-7/how-do-you-handle-employees-who-are-on-leave-in-docebo-904
- Absorb: inactivate = reversible, hides from learners, keeps data for reporting; delete is
  separate. Enrolment rules do not fire while a course is inactive and process immediately on
  reactivation (courses, not field values).
  https://support.absorblms.com/hc/en-us/articles/53268024177555-Deletion-vs-Inactivation-for-Courses-Curricula-Users
  https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules
- TalentLMS: deactivate keeps profile and progress; deleting is destructive. Nothing found on group
  deletion with rules. https://help.talentlms.com/hc/en-us/articles/9652291013788-How-to-deactivate-users-in-TalentLMS
- BambooHR list-field option archiving: not found; treat as unknown.
- Pattern across products: deactivate/hide, keep data, block delete while in use. Rules that name an
  inactive value are not clearly documented anywhere, so spec 2 must decide it (below).
- Existing research in this effort: `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md`
  (lines ~57, 103) says system-controlled lists beat free text because free text causes mismatches.

## 2. Django practice

- `PROTECT` raises `ProtectedError` on delete; `RESTRICT` allows the delete when the same operation
  also cascades-deletes the referrer (e.g. deleting the organisation). Use `PROTECT` for the
  `Learner` to entry FK; entries themselves hang off `Organisation` (already PROTECT elsewhere, see
  `Cohort.organisation`). https://docs.djangoproject.com/en/stable/ref/models/fields/#django.db.models.PROTECT
- The admin delete confirmation page lists protected objects and refuses, so PROTECT alone gives a
  usable admin message.
- Hiding inactive entries yet keeping existing selections valid: do not use `limit_choices_to` on
  the FK (it also validates existing values, so a learner on an inactive entry could not be saved).
  Instead, in `LearnerAdmin.formfield_for_foreignkey` (or the form `__init__`) filter the queryset
  to `Q(is_active=True) | Q(pk=current_value_pk)`. Filter by organisation of the learner in the same
  place. Autocomplete fields need `get_search_results` on the list admin with the same filter.
  https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.formfield_for_foreignkey
- Case-insensitive uniqueness: `models.UniqueConstraint(Lower("name"), "site", "organisation",
  name=...)` (expression constraints, Django 4.0+); portable and needs no collation. Note
  `UniqueConstraint` with expressions is not checked by `validate_unique` the same way, but
  `validate_constraints` (called by `full_clean`) covers it in Django 4.1+, so model forms report it.
  Nondeterministic `db_collation` is an alternative but PostgreSQL-specific and blocks `LIKE`; prefer `Lower()`.
  https://docs.djangoproject.com/en/stable/ref/models/constraints/#uniqueconstraint
- Trimming: `name = name.strip()` in `clean()`; also collapse internal whitespace if wanted; the
  admin form's CharField already strips by default (`strip=True`), but imports (spec 5) and code
  paths bypass forms, so normalise in `save()` too.

## 3. The codebase

- `is_active` precedent exists: `freedom_ls/learner_management/models.py` `Learner.is_active`
  (removed learner, reactivated on re-registration); `freedom_ls/role_based_permissions/models.py`
  `is_active` on the three role-assignment models, with README text "Soft deactivation ...
  preserves audit history and enables reactivation"
  (`freedom_ls/role_based_permissions/README.md` ~line 191). So soft deactivation under the name
  `is_active` is the project's convention. No `archived` field anywhere.
- PROTECT is the norm for site and organisation FKs: `freedom_ls/site_aware_models/models.py:132`
  (`site`), `Cohort.organisation`, `Learner.organisation`, `learner_progress/models.py` (Topic,
  Learner, Course). `course_applications/models.py:47` uses RESTRICT with a written reason.
- Unique constraint precedent: `Cohort` uses `UniqueConstraint(fields=["site", "organisation",
  "name"], name="unique_cohort_name_per_organisation")` in `learner_management/models.py`. The new
  lists should copy it but wrap `name` in `Lower()`.
- `claude_plugins/fls-dev/resources/admin_interface.md`: site-aware models must use
  `SiteAwareModelAdmin`, never expose `site`. Nothing about deactivation or deletion. The
  `multi_tenant.md` resource has no guidance on delete/unique/case.
- Vocabulary: `claude_plugins/sdd/resources/domain_vocabulary.md` has no entry for "archived",
  "active", "deactivated" (grep empty). "Role" is reserved. Use "deactivated" for entries, matching
  the code's `is_active`, and add a glossary line when the spec lands.

## 4. Consequences for later specs

- **Rename in place.** Safe for learners (FK follows). For rules (spec 2) it changes the rule's
  displayed condition text automatically because conditions reference the entry by FK, not by
  string. This is the point of lists. A rename never changes who matches. Worth an audit
  trail later; not needed in spec 1.
- **Spec 2 (rules, retraction).** Rule conditions must reference entries by FK with PROTECT, so a
  rule cannot lose its entry. Decision for spec 2: a rule that names a deactivated entry **keeps
  working** (matches learners who still hold it); the rule admin warns on the rule and the picker
  hides inactive entries for new conditions, with the existing one kept valid via the same
  `Q(is_active) | Q(pk=current)` queryset. Rationale: deactivation means "stop assigning this", not
  "everyone on it is no longer a Driver". Retraction when a learner stops matching is driven by the
  learner's FK changing, not by the entry's `is_active`, so deactivation alone retracts nothing.
  Avoid the Docebo trap (rules silently diverge from membership) by showing an "uses deactivated
  entry" flag on the rule.
- **Spec 4 (educator pickers).** One shared queryset helper (active in this organisation, plus the
  currently chosen entry) used by admin and educator forms; deactivate/reactivate replaces delete
  in the list screens, delete offered only when unreferenced.
- **Spec 5 (CSV import).** Match cell values to entries by case-insensitive, trimmed name within the
  organisation (same normaliser as the constraint). A value matching a **deactivated** entry should
  be reported as a row problem in the preview ("deactivated: reactivate it or pick another") rather
  than silently assigning or silently creating a duplicate; an unknown value is also a row error
  (no auto-creation unless that spec asks). Unchanged values on a learner already holding an
  inactive entry should not error.
- Reactivation is simply ticking `is_active` again; no data is lost.

## Open caveats

- Whether a rule on a deactivated entry should keep matching is a product call for spec 2; the
  above is the recommended default.
- Workday/Cornerstone/BambooHR specifics for inactive values in use were not found in docs.

status: ok
