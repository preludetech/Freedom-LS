---
name: legend-edge-cases-qa-command
description: qa_create_legend_edge_cases — one-form course stressing the question <legend> (wrapping asterisk, inline markdown, two-paragraph question, optional-no-asterisk)
metadata:
  type: reference
---

`uv run python manage.py qa_create_legend_edge_cases [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_legend_edge_cases.py`. Idempotent.

Why it exists: `learner_interface/course_form_page.html`'s `form-question` partial makes the
`<legend>` do three things at once — float the question number beside line 1, glue the required
asterisk to the last word with a literal `&nbsp;`, and inline **only** the last rendered paragraph
(`[&>p:last-of-type]:inline`) so a multi-paragraph question stays two paragraphs. Every other
demo/QA form has short single-paragraph unformatted questions, so none of that wraps or separates
in a browser.

Seeds on `qa-legend-edge-cases` ("QA Legend Edge Cases", access_config `{"access_type": "free"}`,
visibility published), one viewable item = Form `qa-legend-edge-cases-form` (QUIZ, pass 50),
one page `qa-legend-edge-cases-page`, four questions:

1. required, multiple_choice, 38 words, markdown bold + italic + inline code + link.
2. **optional**, short_text (simplest "leave it blank" type), no options -> renders with NO
   `required-indicator` span at all.
3. required, multiple_choice, markdown with a blank line -> renders as two `<p>`; asterisk lands
   after the *second* `</p>`.
4. required, multiple_choice, one 78-word unformatted paragraph -> wraps at any viewport.

Learner: existing `demodev@email.com` (password == email), registered via `_register`, left with
**zero** `FormProgress` so the form is never-opened.
Start page `/courses/qa-legend-edge-cases/1/`, runner `/courses/qa-legend-edge-cases/1/fill_form/1`.

Reused helpers (same set as `qa_create_form_first_course`): `_get_site`/`_get_learner`/
`LEARNER_EMAIL` from `qa_create_form_question_types`, `_add_options`/`_register`/`_item_index`
from `qa_create_multiselect_quiz_scoring`, `_lay_out_course` from `qa_create_report_course`.

## Technique worth reusing
- **Rendering the legend headlessly without starting an attempt.** Do NOT GET
  `/fill_form/1` to check markup — that creates a `FormProgress` and destroys the
  never-opened state the tester asked for. Instead render the partial directly:
  `render_to_string("learner_interface/course_form_page.html#form-question",
  {"question": q, "existing_answers": {}})` (django-template-partials `#partial` syntax works in
  `render_to_string`), then slice out the `<legend>`. Read-only; re-check `FormProgress.count()`
  afterwards to prove it.
- **Stronger idempotency than the sibling commands.** `qa_create_form_*` bail out early if the Form
  slug exists, so re-running never picks up edited question text. Here `_sync_questions` matches
  existing questions on `(form_page, order)`, rewrites `question`/`type`/`required` in place, adds
  options only when the question has none, and deletes leftovers from a longer previous plan.
  Use this shape when the wording itself is the thing under QA and may be tweaked between runs.
- `FormQuestion.question_number()` walks `form.pages` -> `page.questions` in `order`, so it is
  1-based across the whole form, not per page.
