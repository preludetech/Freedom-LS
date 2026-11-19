# Answers: learner-profile-use-panels-framework-1-file-upload-actions

Asked by `/sdd:start` before the spec was written.

- Q: When a panel form with a file field comes back with errors (422), what happens to the chosen file? → A: Ask to choose again: the file input comes back empty with a message on the field saying the file must be chosen again; no server-side stash (asked up front)
- Q: How does a panel form show a file the instance already has, and how is it cleared? → A: Name + remove control: show the current file's name as a link, a "Remove" checkbox when the field is optional, and the picker to replace it (Django ClearableFileInput behaviour, framework-styled) (asked up front)
- Q: What does the user see while a file uploads? → A: Disable Save and change its label to "Uploading…" while the request is in flight; no progress bar (asked up front)
- Q: The current file as a link signs a URL on private storage and the stock widget prints the storage key; how should the framework show the current file? → A: Basename as text, no link; a consumer wanting a link or preview adds it in its own panel (asked while research ran)
- Q: Where should inline file-upload support live, given the inline form is the FLS template `inline_record_form.html`? → A: A new framework partial in `panel_framework/partials/`, with `inline_record_form.html` delegating to it and no visible change to existing pages (asked while research ran)
- Q: Should this spec add a handler for 413, 5xx and network failures, which htmx doesn't swap? → A: Yes, for all panel forms, inline and dialog: a short inline error, dialog stays open, no raw error page swapped in, 413 worded as "file may be too large" (asked while research ran)
