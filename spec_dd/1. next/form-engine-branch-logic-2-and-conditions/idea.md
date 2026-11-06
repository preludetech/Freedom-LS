Follow-up to `form-engine-branch-logic`: let a form author gate a page, question or content block on several conditions that must all hold.

Example: show a page only if `question_slug_1` equals `foo` AND `question_slug_2` includes `bar`.

Today `when:` takes a single condition (one question slug plus exactly one of `equals` or `includes`). It is stored as a single `condition_option` foreign key on `FormPage`, `FormQuestion` and `FormContent`, and evaluated by `_condition_holds` in `freedom_ls/form_engine/conditions.py`. The `form-engine-branch-logic` spec left boolean combinators out of scope.

Only "and" is wanted. "Or", negation, and numeric or text comparisons stay out of scope.

Keep the existing single-condition `when:` syntax working so current content doesn't need to change.
