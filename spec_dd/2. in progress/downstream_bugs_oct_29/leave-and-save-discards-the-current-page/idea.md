# Idea: "Leave and save" in the form exit dialog throws away the answers on the current page

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (LEARN-8).

1. As a registered learner open `/courses/introduction-to-the-drone-industry/4/`, a save-on-exit
   quiz. Press Start Form (or Continue Form).
2. Tick an answer on page 1. Don't press Next.
3. Click the X ("Exit test"). The dialog says "Leave the test? Your progress is saved — you can
   resume later."
4. Click "Leave and save", then "Continue Form".

Expected: the answer ticked before leaving is still ticked.

Actual: page 1 comes back with nothing ticked. Only pages already submitted with Next are kept.

## Cause

In `freedom_ls/learner_interface/templates/learner_interface/course_form_page.html:157-162`, for
save-on-exit forms "Leave and save" is a plain link (`<c-button href="{{ save_and_exit_url }}">`).
`save_and_exit_url` is just the item's start page (`learner_interface/views.py:1593-1596`). The
current page's answers are never posted. "Leave and submit" for submit-on-exit forms (`:149-155`)
does post the runner form, and `form_submit_and_exit` (`views.py:1876`) saves the page before
completing.

## Suggested fix

Make "Leave and save" submit the runner form to an endpoint that saves the posted page with
`require_answers=False`, as `form_submit_and_exit` already does, then redirects to the start page
without finalising. `formnovalidate` applies for the same reason. If FLS would rather not save
partial pages, change the dialog copy so it doesn't promise the progress is saved.

## Downstream workaround

None.
