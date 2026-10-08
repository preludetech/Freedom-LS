---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: course-applications-admin

## Breaking changes

**Answer data is no longer superuser-only. Standard view permissions decide access now.**
`SuperuserOnlyAdmin` has been removed from `freedom_ls/form_engine/admin.py`.
`FormProgressAdmin`, `QuestionAnswerAdmin` and `QuestionAnswerFileAdmin` use Django's own model
permissions again. The admin file download route
(`admin:freedom_ls_form_engine_questionanswerfile_download`) now checks
`freedom_ls_form_engine.view_questionanswerfile` through
`freedom_ls.form_engine.permissions.can_download_answer_files`, not `is_superuser`. This
reverses the simple-application-forms change.

Before deploying, audit every group, role and user that holds any of these permissions:

- `freedom_ls_form_engine.view_formprogress`
- `freedom_ls_form_engine.view_questionanswer`
- `freedom_ls_form_engine.view_questionanswerfile`
- `freedom_ls_course_applications.view_courseapplication`

The matching `change_`, `add_` and `delete_` permissions on the `freedom_ls_form_engine` models
belong in the same audit. A staff account that was granted these, for example through a role
that holds "every permission", was blocked before this change. After it, that account can read
applicants' answers and download the files they attached. Remove the grants from any role that
should not see applicant data.

**Removed names.** If your code imports either of these from `freedom_ls.form_engine.admin`, it
will fail at import:

- `SuperuserOnlyAdmin`. If you want the old gate back, re-declare it locally.
- `QuestionAnswerInline`. The `FormProgress` change page now shows answers as a read-only
  document in place of the inline.

**The `FormProgress` change page no longer edits answers.** Answers are read-only there, and so
are `user` and `form` on an existing sitting. The add page still takes both.
`furthest_page_reached` now appears read-only. To edit an answer, a user needs the change
permission on the `QuestionAnswer` admin.

## Manual steps

1. **Audit permissions** as described under Breaking changes. This is the only step that
   needs a decision from you.
2. **Nothing else is required.** This change has no migrations, settings, packages or Tailwind
   classes. The new `CourseApplication` admin and its permission (`view_courseapplication`)
   come from the existing model. It is read-only for everyone: nobody can add, change or
   delete an application from the admin.
3. **Optional template shadowing.** The answers document and summary are new templates that
   your project can shadow by path:
   - `freedom_ls/form_engine/templates/admin/form_engine/answers_change_form.html`
   - `freedom_ls/form_engine/templates/admin/form_engine/_answers.html`
   - `freedom_ls/form_engine/templates/admin/form_engine/_summary.html`

   They use Unfold's prebuilt admin classes, so your site's Tailwind bundle does not need
   rebuilding. One rule (`.answer-text`) was added to
   `freedom_ls/site_aware_models/static/site_aware_models/css/admin.css`, which your normal
   `collectstatic` deploy step picks up.
4. **User erasure.** `CourseApplication` and `Learner` were added to
   `freedom_ls.accounts.admin.USER_ERASURE_CASCADE_MODELS`, so erasing a user from the User
   admin removes their applications and Learner rows. Without this, the new
   `CourseApplicationAdmin`, which denies delete, would block erasure. Before this change,
   erasing a user who had `Learner` rows was refused. If you add your own delete-denying
   models to that set, it works the same way as before.
