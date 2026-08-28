# Idea: `QuestionAnswer.selected_options` is unusable in the Django admin

## The bug

In `freedom_ls/learner_progress/admin.py`, `selected_options` is rendered with the default
`SelectMultiple` widget in both `QuestionAnswerInline` (line 13) and `QuestionAnswerAdmin`
(line 72). Two things make it unreadable:

- **No scoping.** `selected_options = models.ManyToManyField(QuestionOption, blank=True)`
  (`learner_progress/models.py:529`) has no `limit_choices_to`, so the widget lists *every*
  `QuestionOption` in the database — every option of every question of every form. Only the
  options belonging to `answer.question` are ever valid.
- **No distinguishing label.** `QuestionOption.__str__` returns bare `self.text`
  (`content_engine/models.py:561`), so the list is hundreds of entries reading `Yes`, `Yes`,
  `Agree`, `1`, `1`… with nothing to tell them apart.

The whole option table is also serialised into the DOM on every `FormProgress` change page.

## Expected fix

- Use `autocomplete_fields = ("question", "selected_options")` on both `QuestionAnswerInline` and
  `QuestionAnswerAdmin`. `QuestionOptionAdmin` already declares
  `search_fields = ("text", "question__question")` (`content_engine/admin.py:32`), so this works
  with no other changes, and it matches the FLS admin skill's rule to use `autocomplete_fields`
  for FK/M2M rather than loading all options.
- Scope the queryset on the standalone `QuestionAnswerAdmin` via `formfield_for_manytomany`, so
  only `answer.question.options` are offered. (Not possible in the inline for unsaved rows, where
  the question isn't chosen yet — autocomplete is the answer there.)
- Make `QuestionOption.__str__` include its question, e.g. `f"{self.question}: {self.text}"`, so
  options are distinguishable in the picker, in `answer_preview`, and anywhere else they render.

## Open question

`QuestionAnswer` holds student-submitted data, and editing it by hand silently invalidates
`FormProgress.scores`, which is computed from these rows. Consider whether the inline should be
`readonly_fields` with a rendered answer summary instead of an editable picker — which removes the
widget problem entirely.

## Sources

- `submodules/Freedom-LS/freedom_ls/learner_progress/admin.py` — lines 13, 72
- `submodules/Freedom-LS/freedom_ls/learner_progress/models.py` — line 529
- `submodules/Freedom-LS/freedom_ls/content_engine/models.py` — line 561
- `submodules/Freedom-LS/freedom_ls/content_engine/admin.py` — line 32
