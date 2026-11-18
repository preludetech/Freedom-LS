---
requires_migrations: true
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

# Upgrade notes: learner-interface-features-1-question-sections

Form questions can now name the sections they test. A form file takes a `sections:` list of
paths to topic markdown files or `part.yaml` files, and a question can override it with its own
`sections:` list. `content_save` stores them on two new through tables in `content_engine`:
`FormQuestionTopic` and `FormQuestionCoursePart`.

## Breaking changes

- **Topics and course parts named by a question can no longer be deleted directly.** Both through
  tables use `on_delete=PROTECT` on the topic or course part, so deleting a `Topic` or `CoursePart`
  that any `FormQuestion` names raises `django.db.models.ProtectedError`. Code in your project that
  deletes topics or course parts has to delete the questions that name them first, or clear their
  sections with `question.topics.clear()` and `question.course_parts.clear()`.
- **New relation names.** `Topic.testing_questions` and `CoursePart.testing_questions` are new
  many-to-many fields, with reverse accessors `FormQuestion.topics` and `FormQuestion.course_parts`.
  A project that already adds a field or relation with one of these names to those models will hit a
  clash at `manage.py check`.
- **The `FormQuestion` admin is re-registered.** `freedom_ls.content_engine.admin` unregisters the
  `FormQuestion` admin and registers `FormQuestionWithSectionsAdmin`, a subclass of
  `FormQuestionAdmin` with a read-only Sections fieldset. If your project registers its own
  `FormQuestion` admin, subclass `FormQuestionWithSectionsAdmin` to keep the Sections fieldset.
  Unregister it before you register your own, after `freedom_ls.content_engine` has loaded.

## Manual steps

- Run `manage.py migrate`. It applies
  `freedom_ls_content_engine.0012_formquestioncoursepart_coursepart_testing_questions_and_more`.
- Content that has no `sections:` key loads as before. Once you add `sections:`, `content_save`
  and `content_validate` reject any path that does not resolve to a topic or course part loaded in
  the same run, so run `manage.py content_validate` on your content before you deploy it.
