---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # optional: add "freedom_ls.hr_attributes" to opt in
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: corporate-job-course-recommendations-1-hr-attributes

This change adds `freedom_ls.hr_attributes`, a new optional app. It records each learner's job
title, department and location (per-organisation lists managed in the Django admin) plus four
start dates. It also adds a per-organisation `registration_rules_enabled` switch that nothing
reads yet. A project that leaves the app out of `INSTALLED_APPS` sees no change. No existing
app gained fields or migrations. The only code outside the app that imports it is the dev-only
`qa_create_hr_attributes_scenario` command in `freedom_ls.qa_helpers`, which works only when
`hr_attributes` is installed.

## Breaking changes

None. FLS's own `config/settings_base.py` installs the app, but downstream projects keep their
own `INSTALLED_APPS`, so nothing changes until you add it.

## Manual steps

Only needed if you opt in:

1. **Add the app** to `INSTALLED_APPS`. FLS puts it straight after
   `"freedom_ls.learner_management"`:

   ```python
   "freedom_ls.hr_attributes",
   ```

2. **Run migrations.** One new migration,
   `freedom_ls/hr_attributes/migrations/0001_initial.py`, which depends on
   `freedom_ls_learner_management` `0004_alter_cohort_options_alter_learner_options` and
   `freedom_ls_organisations` `0001_initial`.

   ```
   uv run manage.py migrate
   ```

3. **Check your admin customisations.** The app adds `LearnerHRAttributesInline` to
   `LearnerAdmin.inlines` and `OrganisationHRSettingsInline` to `OrganisationAdmin.inlines`
   by appending to the class attribute when `freedom_ls/hr_attributes/admin.py` is imported.
   A subclass that inherits `inlines` picks them up. A subclass that sets its own `inlines`
   list does not, so add the two inlines yourself if you want them there.

4. **Check your tests that post the Learner or Organisation change page.** Once the app is
   installed, each of those pages has one more inline formset. A test that hard-codes the
   formset management fields in its POST data will fail with missing ManagementForm data
   until it includes the new prefixes. FLS's own
   `freedom_ls/learner_management/tests/test_learner_admin.py` now reads the prefixes from
   the page's `inline_admin_formsets` context instead of naming them.

5. **Reverse accessor names.** The app adds `Learner.hr_attributes`,
   `Organisation.hr_settings`, `Organisation.job_titles`, `Organisation.departments` and
   `Organisation.locations`. If one of your own models already uses one of those as a
   `related_name` on `Learner` or `Organisation`, `manage.py check` reports the clash at boot.
