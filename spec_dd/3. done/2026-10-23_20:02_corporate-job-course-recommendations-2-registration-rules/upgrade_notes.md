---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS                   # optional: add "freedom_ls.registration_rules" after "freedom_ls.hr_attributes"
  - REGISTRATION_RULE_KINDS          # optional: has a default
  - REGISTRATION_RULE_BATCH_SIZE     # optional: has a default
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: corporate-job-course-recommendations-2-registration-rules

A new optional app, `freedom_ls.registration_rules`, lets an organisation admin write a rule that
registers every learner holding a given HR attribute on a course, and keeps those registrations in
step as learners, attributes and the rule itself change. It is entirely admin-driven and runs its
evaluations through the Django task framework. No learner-facing or educator-facing template changed.

## Breaking changes

- **`ListEntryManager.for_picker` takes a list of held primary keys.** In
  `freedom_ls/hr_attributes/models.py`, `for_picker(organisation_id, current_pk: UUID | None)` is now
  `for_picker(organisation_id, held_pks: Iterable[UUID])`. Downstream code that called it with a
  single key or `None` must pass `[pk]` or `[]` instead.
- **Course registration webhooks fire from any code path.** `_ensure_and_announce` in
  `freedom_ls/learner_progress/signals.py` now calls the new
  `fire_webhook_event_for_site(event_type, payload, site_id)` in `freedom_ls/webhooks/events.py` with
  the registration's own site. Before, a `course.registered` event raised outside a request (a
  management command, a task) was silently dropped. Webhook consumers will now receive events for
  registrations made by rules, imports and commands. `fire_webhook_event` keeps its signature and
  still resolves the site from the request.
- **Deleting a course or organisation that a rule names is refused.** `RegistrationRule` holds
  `PROTECT` foreign keys to `Course` and `Organisation`. Downstream code that deletes either must
  delete or detach the rules first. `danger_content_delete` already does this.
- **Deleting an HR list entry a rule names is refused** in the admin. The rules app patches
  `ListEntryAdmin.get_deleted_objects` so the delete confirmation lists the rule as protected.

The first two changes apply whether or not the rules app is installed. The two deletion refusals
only apply when `freedom_ls.registration_rules` is in `INSTALLED_APPS`.

## New optional app

The app is optional. Leave it out of `INSTALLED_APPS` and nothing else in FLS changes beyond the
two unconditional items above. To enable it:

1. Add `"freedom_ls.registration_rules"` to `INSTALLED_APPS`, after `"freedom_ls.hr_attributes"`.
   The app refuses to load with `ImproperlyConfigured` if `freedom_ls.hr_attributes` is not
   installed.
2. Optionally set these settings. Both have defaults and neither is enforced at boot:
   - `REGISTRATION_RULE_KINDS`: a dict of kind key to the dotted path of a rule-kind class. Default
     `{"attribute": "freedom_ls.registration_rules.kinds.AttributeRuleKind"}`. A project that adds
     its own kind subclasses `AttributeRuleKind` and adds an entry here.
   - `REGISTRATION_RULE_BATCH_SIZE`: learners per transaction when a whole rule is evaluated.
     Default `500`.
3. Two system checks guard the configuration. `freedom_ls_registration_rules.E002` fails when a
   `REGISTRATION_RULE_KINDS` path does not import. `freedom_ls_registration_rules.E003` fails when
   the default kind of `RegistrationRule.kind` (`"attribute"`) has no entry in
   `REGISTRATION_RULE_KINDS`. There is no E001.

## Manual steps

1. Run `uv run manage.py migrate` if the app is installed. The new migrations are
   `freedom_ls/registration_rules/migrations/0001_initial.py`, `0002_ruleregistration.py` and
   `0003_attributeruleconditions.py`. They depend on `freedom_ls_hr_attributes.0001_initial`,
   `freedom_ls_learner_management.0005_cohort_is_active` and `freedom_ls_content_engine.0007_article_image`.
2. Make sure the task worker is running in production: `uv run manage.py fls_run_worker`. Rules
   are evaluated as tasks, so without a worker a rule never registers anyone.
3. Run `uv run manage.py check` to confirm `freedom_ls_registration_rules.E002` and `E003` pass.
4. Search your code for `for_picker(` and update any call to pass a list.
5. If you consume the `course.registered` webhook, expect events for registrations made outside a
   request. The payload is unchanged.
