# Research: showing a learner's answers in Django admin

Note: written from established knowledge of Django admin and the named tools; no live web fetches were performed, so the URLs below are canonical docs and starting points, not quotes of freshly checked pages. Repo facts checked: `FormQuestion.order`, `FormPage.order`, `QuestionOption.order`, `QuestionAnswer(form_progress, question PROTECT FK, selected_options M2M, text_answer)`, `QuestionAnswerFile`. The question FK is PROTECT, so questions cannot be deleted while answered; they can only be edited.

## 1. Django admin techniques

| Technique | Pros | Cons |
|---|---|---|
| Read-only Tabular/StackedInline (`has_add/change/delete_permission=False`, `max_num=0`, `extra=0`, `can_delete=False`) | Zero template work; native admin look | Shows only existing rows, so unanswered questions are missing. No page grouping. M2M `selected_options` renders as a multi-select widget or a raw list when read-only. Ordering needs `get_queryset().order_by("question__form_page__order", "question__order")`. Needs `select_related("question__form_page")` plus `prefetch_related("selected_options", "files")` to avoid N+1. |
| Read-only computed field (`readonly_fields = ["answers_display"]`, method returns `render_to_string(...)` or `format_html`/`format_html_join`) | Full control. Can iterate the Form's questions (not the answers), so unanswered questions are shown and marked. Groups by page. One query set, prefetched once. Reuses a partial template on both admins. | Hand-rolled markup. Escaping must be done correctly. |
| `change_form_template` with an extra block (extend `admin/change_form.html`, e.g. `{% block after_field_sets %}`) | Placement control | More moving parts than a readonly field. It is the same data-building problem and needs `render_change_form`/`change_view` `extra_context`. Only worth it for layout the fieldset cannot give. |
| Custom admin view via `get_urls()` | Own page, printable, can paginate | Must be wrapped in `self.admin_site.admin_view(...)`, needs a permission check and a link from the change page, and breaks out of the change-form context. Overkill. |

Cross-cutting points:
- **Ordering:** build a `{question_id: answer}` dict from prefetched answers. Then walk `form.pages.order_by("order")` with `prefetch_related("questions__options")`, in question order. Ordering is then by the form definition, never by answer insertion.
- **Unanswered:** only the "walk the form" approach shows them. Render a muted "Not answered" marker. Distinguish "no answer row" from "empty text".
- **Performance:** about 4 queries in total (pages with questions, options, answers with `selected_options`, files), independent of the number of questions. Do this once per page render, not per field.
- **XSS:** learner text is untrusted. Use a Django template (auto-escapes) or `format_html`/`format_html_join` with arguments. Never `mark_safe` on learner text or concatenated strings. In a template, use `linebreaksbr` (it escapes first) for multi-line text. Never use `|safe`. Any markdown question text from authors should be shown as plain text or deliberately rendered, not trusted.
- **Long answers:** show in full in a `white-space: pre-wrap; max-width` block. Never truncate for reviewers. Optionally wrap in a `<details>` only past a large length.
- **Files:** link to the existing superuser-only admin download route with `reverse(...)`. Show the filename and size. Show the link only to users who may use that route and plain filename text otherwise, so non-superusers do not hit a 403.
- **Selected options:** render option text ordered by `QuestionOption.order`. For choice questions, optionally list all options with the chosen ones marked. This is more informative than a bare list.
- **Context to show:** form title, learner, started/completed timestamps, score and marking status if present, plus the application status.

**Recommendation:** use a read-only computed field rendered with a shared partial template (`render_to_string`), backed by one helper function that builds the page, question and answer structure from a `FormProgress`. Use it in a "Responses" fieldset on `FormProgressAdmin`, and on `CourseApplicationAdmin` through its `form_progress`. Do not use an inline for the display. Use no `change_form_template` and no custom view unless a print or export need appears later.

## 2. How other tools present one response

- **Google Forms (Individual tab):** a page per response. Shows each question text with the answer beneath it, in form order. Unanswered questions are shown as blank. Choice answers show the picked option. Files show as links. Has a timestamp, an email and a score per question for quizzes. Complaints: summary view loses the per-person context, and answers lost when a question is deleted (the data moves to the sheet only).
- **Typeform (Responses):** the question and answer are shown as a list, with a "skipped" indication, submit time and metadata. Complaints: edited questions leave old answers under the old title in exports.
- **SurveyJS:** results are displayed by re-rendering the survey JSON in display mode (`mode: "display"`) with the saved data. This means the live form definition is joined to the answers. If the question is removed, its answer is not shown (data exists in the JSON but is not rendered). SurveyJS docs recommend versioning survey JSON.
- **Moodle quiz review / Feedback:** the review page shows question text, the response given, the correct answer, the mark and the feedback. Moodle snapshots the question text and answer into `question_attempts` (`questionsummary`, `responsesummary`, `rightanswer`) precisely so that later edits do not alter the attempt. Feedback (survey) module shows per-user responses with question labels.
- **Canvas:** the SpeedGrader / quiz submission view shows each question text, the chosen answer, correct marking, a timestamp and an attempt number. Canvas quiz questions are snapshotted into a `quiz_data` copy on submission, so later edits do not change what the student saw.
- **Submittable / application review tools:** show the application as a read-only document of labelled sections (question, answer, attached files with preview), plus a sidebar with status, scores and notes. Reviewers want to read it as a document and want attachments inline. Complaints are mostly about answers missing from exports and no preview of files.
- **Wagtail form submissions:** a list with one column per field, an export, and a per-submission view. Field labels are stored with the form data. Wagtail stores the submission as JSON keyed by the field's clean name, and if a field is renamed or removed, the old data shows under the old key or not at all. This is a well known complaint: "lost data when I edit the form".
- **django-forms-builder:** field entries are stored with `field_id` and the text value. The entries admin shows a table with a column per field label and an export. Entry values for deleted fields are lost or shown by ID.
- **django-fobi:** saved form data is stored as JSON with labels and values (a snapshot), shown in a "Saved form data entries" admin. Survives edits because labels are stored with the data.
- **django-formtools:** wizard only; it stores no submissions, so it has no review view to learn from.

Common reviewer complaints (patterns to avoid): raw IDs instead of question text, answers out of form order, no question text next to the answer, truncated long answers, unanswered questions silently absent, files only as an opaque link with no filename, M2M choices shown as IDs or Python list reprs, and answers lost or relabelled when the form changes.

## 3. Form changed after submission

Two strategies:
1. **Snapshot** (Moodle, Canvas, django-fobi, Wagtail labels): copy question text (and option text) into the answer at save time. This is accurate for history but needs a schema change and migration of existing rows, and it is only useful if the display is expected to be an audit record.
2. **Live join** (SurveyJS, Google Forms, the approach recommended above): show the current question text next to the stored answer. Simple, but the displayed wording may differ from what the learner saw.

Reasonable here: use the live join and do not add a snapshot, since the brief is a display feature and "don't build functionality not requested". The PROTECT FK on `QuestionAnswer.question` means answers cannot be orphaned by deleting a question. Handle the remaining edge cases in the display:
- Questions that were added after the learner submitted show as "Not answered" (this is correct behaviour for unanswered questions).
- Questions that were moved to another page or reordered show in their current position.
- Answers whose question is no longer part of the form's current pages (for example, a page was deleted and the question reassigned elsewhere or detached) should be listed in a final "Other answers" group, so no answer is hidden. This is cheap: compute `answers_by_question` minus the questions already rendered.
- Option answers that no longer exist cannot appear in M2M anyway; show what remains.
- Optionally show a small note when a question's `updated_at` is later than the answer's `created_at`/`updated_at` ("question edited after this answer"). The `TimestampedModel` fields make this a cheap comparison, but treat it as optional.

## References
- Django admin reference (InlineModelAdmin, readonly_fields, get_urls, change_form_template): https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- Django `format_html` / `format_html_join` / escaping: https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.html.format_html
- Django template auto-escaping and `linebreaksbr`: https://docs.djangoproject.com/en/stable/ref/templates/builtins/
- Django admin `display` decorator and readonly computed fields: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.display
- Google Forms individual responses: https://support.google.com/docs/answer/139706
- Typeform results: https://www.typeform.com/help/a/view-and-analyze-responses-360029117672/
- SurveyJS display mode / results: https://surveyjs.io/form-library/documentation/design-survey/create-a-simple-survey
- Moodle question behaviours and quiz review: https://docs.moodle.org/en/Quiz_settings
- Canvas quiz submissions: https://community.canvaslms.com/t5/Instructor-Guide/tkb-p/Instructor
- Wagtail form builder submissions: https://docs.wagtail.org/en/stable/reference/contrib/forms/
- django-forms-builder: https://github.com/stephenmcd/django-forms-builder
- django-fobi: https://github.com/barseghyanartur/django-fobi
- django-formtools: https://django-formtools.readthedocs.io/

status: ok
