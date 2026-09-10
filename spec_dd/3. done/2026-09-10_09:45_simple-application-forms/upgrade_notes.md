---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
  - freedom_ls/form_engine/templates/form_engine/question.html
  - freedom_ls/form_engine/templates/form_engine/inputs/short_text.html
  - freedom_ls/form_engine/templates/form_engine/inputs/long_text.html
  - freedom_ls/form_engine/templates/form_engine/inputs/number.html
  - freedom_ls/form_engine/templates/form_engine/inputs/multiple_choice.html
  - freedom_ls/form_engine/templates/form_engine/inputs/checkboxes.html
  - freedom_ls/form_engine/templates/form_engine/inputs/file_upload.html
  - freedom_ls/course_applications/templates/course_applications/form_page.html
  - freedom_ls/course_applications/templates/course_applications/check_your_answers.html
requires_settings_change: true
changed_settings:
  - DATA_UPLOAD_MAX_MEMORY_SIZE  # optional: raise to 10 MB so a 6 MB upload has request headroom
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: simple-application-forms

## Breaking changes

**The root URLconf needs a new include.** `freedom_ls.form_engine` now ships its own
`urls.py` (`app_name = "form_engine"`) holding the applicant's file upload, file remove and
file download endpoints. Downstream projects keep their own root URLconf, so nothing adds it
for you. Without it, any form page rendering a `file_upload` question, and the application
check-your-answers page, raise `NoReverseMatch` on `form_engine:question_file_upload`,
`form_engine:question_file_remove` and `form_engine:own_question_answer_file`.

**`FormProgressAdmin` and `QuestionAnswerAdmin` are now superuser-only.** Both gained the
`SuperuserOnlyAdmin` mixin in `freedom_ls/form_engine/admin.py`, and the new
`QuestionAnswerFileAdmin` has it too. A staff role that was granted
`freedom_ls_form_engine.view_formprogress` or
`freedom_ls_form_engine.view_questionanswer` no longer sees those
admins — applicant PII now lands in the same tables as quiz answers, so the gate is in the
admin class rather than in a permission grant. Any role relying on that access needs a
superuser account or a locally re-declared admin.

**`manage.py content_save` now fails on a `children:` entry it cannot resolve.** It used to
log a warning and silently drop the child. Two related changes go with it: an author-written
`children:` path is now resolved relative to the directory of the file that declares it (what
`course-files.md` already documented), and every `content_by_path` key is resolved before
comparison. A content tree whose `children:` paths were quietly not matching will now stop
the load with `Collection '<title>' names a child at <path> that was not loaded`. Fix the
paths — the load is atomic, so nothing is half-written.

**`FreeOnlyCourseAccessBackend.validate_course_config` returns more than `access_type`.** It
now returns every key in the new `_ALLOWED_CONFIG_KEYS` class attribute plus the defaulted
`access_type`, instead of always `{"access_type": ...}`. A custom access backend that widened
the accepted keys by overriding `validate_course_config` should widen
`_ALLOWED_CONFIG_KEYS` instead; one that relied on the return value being a single-key dict
must stop.

**The question markup moved out of `learner_interface`.** 142 lines of question rendering left
`learner_interface/templates/learner_interface/course_form_page.html`, which now does
`{% include "form_engine/question.html" %}`. A project shadowing `course_form_page.html`
keeps its own copy and so will not render the new `number` or `file_upload` question types,
and will drift from the exam runner. `learner_interface.views._unanswered_required_message`
is gone; the paging, resume and required-answer helpers now live in
`freedom_ls.form_engine.paging`.

## Manual steps

1. **Run migrations.** Six new ones:
   - `freedom_ls/content_engine/migrations/0002_course_application_form.py`
   - `freedom_ls/course_applications/migrations/0002_courseapplication_form_and_more.py`
   - `freedom_ls/course_applications/migrations/0003_remove_courseapplication_form_and_more.py`
   - `freedom_ls/form_engine/migrations/0002_alter_form_strategy_alter_formquestion_type_and_more.py`
   - `freedom_ls/form_engine/migrations/0003_remove_questionanswerfile_scan_status.py`
   - `freedom_ls/form_engine/migrations/0004_formprogress_furthest_page_reached.py`

   ```
   uv run manage.py migrate
   ```

2. **Add the form_engine URLs to your root URLconf**, alongside the existing includes:

   ```python
   path("forms/", include("freedom_ls.form_engine.urls")),
   ```

   The prefix is yours to choose; only the `form_engine` namespace matters.

3. **Rebuild Tailwind.** The new question-input templates and the two
   `course_applications` pages introduce utility classes your bundle does not have yet.

   ```
   npm run tailwind_build
   ```

4. **Review your template overrides.** If you shadow
   `learner_interface/course_form_page.html`, re-apply your customisations on top of the
   trimmed version and let it include `form_engine/question.html`, or copy the new
   `form_engine/inputs/` templates into your override.

5. **Configure the `user_uploads` storage alias for real.** `QuestionAnswerFile.file` is its
   first consumer, so a deployment that never set `AWS_S3_USER_UPLOADS_BUCKET_NAME` was
   previously harmless and now decides where applicants' ID scans and supporting documents
   land. With no bucket named it falls back to local `FileSystemStorage`. Give it a bucket of
   its own: `manage.py check --deploy` reports `freedom_ls_deployment.E001` when the alias
   resolves where `default` does and `E003` when it inherited `AWS_STORAGE_BUCKET_NAME`, and
   `user_uploads` is in `SIGNED_URL_PURPOSES`, so `E004` fires if it resolves with
   querystring auth off. FLS serves these files through permission-checked views rather than
   handing out bucket URLs, so keep the bucket itself private.

6. **Optionally raise `DATA_UPLOAD_MAX_MEMORY_SIZE`.** FLS's own `config/settings_prod.py`
   went from 5 MB to 10 MB. Nothing enforces this at boot — no system check reads it — but
   the per-file cap an applicant is measured against is
   `freedom_ls.form_engine.uploads.MAX_UPLOAD_BYTES` (6 MB), and the setting is the headroom
   the rest of the multipart request has around it. If your own settings module still says
   5 MB, an upload near the cap can be rejected by Django before FLS sees it.

7. **Nothing to do for existing gated courses.** `Course.application_form` is nullable and
   `CourseApplication.form_progress` is nullable, so a gated course that names no
   `application_form` in its `access_config` keeps today's apply-then-status flow exactly.
   To add a form, an author points `access_config.application_form` at a FORM file's path
   relative to `course.md`; `demo_content/functionality_demo_application_gated/course.md`
   shows the shape.
