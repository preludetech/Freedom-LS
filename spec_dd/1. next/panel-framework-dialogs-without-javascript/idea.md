# Panel-framework dialogs without JavaScript

A single-record dialog trigger does nothing with JavaScript off.
`freedom_ls/panel_framework/templates/cotton/modal-trigger.html` renders an `hx-get` button with
no `href`, so with JavaScript off nothing happens when a person presses it. This affects
"Remove picture" on Personal details and every educator trigger that opens `#app-modal`: course
outline actions, deactivate registration, staff member actions, membership actions, cohort staff,
learner registrations and staff role buttons.

The panel-framework skill says a confirmation shows as a modal over the page it came from,
JavaScript on or off. Today only bulk actions keep that promise: a JavaScript-off bulk POST makes
`freedom_ls/panel_framework/views.py` render the page with the confirmation in
`server_modal_html`, open over it.

Wanted:

- A modal trigger still works with JavaScript off, for example as a link or a GET form to the
  action URL, with `hx-get` layered on top.
- A plain (non-htmx) GET of an action URL renders the page the action belongs to with the dialog
  open over it, reusing the bulk path's `server_modal_html`, with the dialog's Cancel a link back
  to that page.
- A JavaScript-off browser test for a single-record dialog, beside the bulk one in
  `panel_framework/tests/playwright/test_data_table_flow.py`.

Raised by the account-page spec (learner-profile-use-panels-framework-3-account-page), from
code-review finding 3 on PR 263.
