---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS                    # hard: freedom_ls_comms.E004 fails at boot without freedom_ls.messaging_policy
  - MESSAGING_OFFERED_EDUCATOR_ROLES  # hard only when a site role config lacks cohort_admin: freedom_ls_messaging_policy.E002
  - MESSAGING_POLICY                  # optional
  - MESSAGING_DEFAULT_FLAGS           # optional
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: user-communication-3-messaging-policy

## Breaking changes

**A new app must be installed.** `MESSAGING_POLICY` (in `freedom_ls.comms`) defaults to
`freedom_ls.messaging_policy.policy.LayeredMessagingPolicy`. If `freedom_ls.messaging_policy` is
missing from `INSTALLED_APPS`, the boot-time check `freedom_ls_comms.E004` fails and the project
will not start. Add it after `freedom_ls.comms`:

```python
INSTALLED_APPS = [
    ...
    "freedom_ls.comms",
    "freedom_ls.messaging_policy",
    ...
]
```

**Custom role configs must define the offered educator roles.** `MESSAGING_OFFERED_EDUCATOR_ROLES`
defaults to `["cohort_admin"]`. The boot-time check `freedom_ls_messaging_policy.E002` fails when a
listed role is missing from the base role config or from any site role config named in
`FREEDOMLS_PERMISSIONS_MODULES`. If one of your site role configs has no `cohort_admin`, set
`MESSAGING_OFFERED_EDUCATOR_ROLES` to roles that every config defines.

Nothing else in your code has to change. Nothing calls the policy yet. Later specs build the
messaging screens on it.

## Manual steps

1. Add `freedom_ls.messaging_policy` to `INSTALLED_APPS` (see above).
2. Run `manage.py migrate`. This applies `freedom_ls_messaging_policy` migrations `0001_initial`
   to `0004_sitemessagingconfig_offered_educator_roles`, which create the messaging config tables.
   No data migration runs.
3. Run `manage.py check --database default`. These checks are new:
   - `freedom_ls_comms.E003`: `MESSAGING_POLICY` doesn't import, or isn't a subclass of
     `freedom_ls.comms.messaging_policy.MessagingPolicy`.
   - `freedom_ls_comms.E004`: `MESSAGING_POLICY` points into an FLS app that isn't installed.
   - `freedom_ls_messaging_policy.E001`: `MESSAGING_DEFAULT_FLAGS` doesn't name exactly
     `learner_to_educator`, `learner_to_cohort_peer` and `learner_to_course_peer`, or has a value
     other than `"open"` or `"closed"`.
   - `freedom_ls_messaging_policy.E002`: see Breaking changes.
   - `freedom_ls_messaging_policy.W001`: a site's stored offered educator roles aren't a list of
     role keys, or name a role that doesn't grant `view_learner` in that site's role config. This check reads the database, so it
     runs only when a database is named, for example `--database default` or during `migrate`.
4. **Optional settings.** You only need these to change the defaults:
   - `MESSAGING_POLICY`: dotted path to your own `MessagingPolicy` subclass.
   - `MESSAGING_DEFAULT_FLAGS`: the settings-level fallback. All three flags default to `"closed"`,
     so out of the box a learner can only reply. Educators can start conversations with the
     learners they can see, and colleagues can message each other.
   - `MESSAGING_OFFERED_EDUCATOR_ROLES`: an install without cohorts should add
     `organisation_admin`.

   Site admins can override the flags per site, organisation, cohort and learner in the Django
   admin, under "Messaging policy". A course registration can override only
   `learner_to_course_peer`.
5. **Existing grant holders need `OrganisationMember` rows.** If you skipped the
   `OrganisationMember` backfill from educator-interface-5-permissions (step 3 in
   `spec_dd/3. done/2026-10-01_22:00_educator-interface-5-permissions/upgrade_notes.md`), those
   `organisation_admin`, `cohort_admin` and `cohort_viewer` holders count as neither educators nor
   colleagues, so the policy refuses them.
6. A small rule was added to
   `freedom_ls/site_aware_models/static/site_aware_models/css/admin.css`, so values that wrap no
   longer get cut off in admin changelist cards on phones. Your normal `collectstatic` deploy step
   picks it up. It needs no Tailwind rebuild.
