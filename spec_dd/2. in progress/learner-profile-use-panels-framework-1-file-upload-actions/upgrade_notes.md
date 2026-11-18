---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/button.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/inline_record_form.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/inline_record_form.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: learner-profile-use-panels-framework-1-file-upload-actions

Panel form actions now accept file uploads: dialog and inline forms post as multipart when the
form has a file field, and a failed request shows a message inside the form.

## Breaking changes

- **Form actions pass `files` to the form.** `FormPanelAction.get_form_kwargs` now returns a
  `files` key alongside `data`. A host form used by a panel form action whose `__init__` takes
  `data` followed by keyword-only arguments (`def __init__(self, data=None, *, ...)`) raises
  `TypeError: ... unexpected keyword argument 'files'` on every request to that action. Add
  `files: MultiValueDict[str, UploadedFile] | None = None` after `data` and pass it on with
  `super().__init__(data, files)`, as the forms in `freedom_ls/educator_interface/forms.py` now
  do. A host that overrides `get_form_kwargs` without calling `super()` is unaffected but will not
  receive uploaded files.
- **Inline record form moved.** Its markup now lives at
  `panel_framework/partials/inline_record_form.html`. The old path,
  `educator_interface/partials/inline_record_form.html`, is now a one-line include of the new one,
  so existing includes keep working. A host that shadows the old path keeps its own markup and
  misses the multipart encoding and the request-error message; move the override to the
  framework path and re-apply your changes there.

## Manual steps

- Review any overrides of the templates listed in `changed_template_paths`:
  - `cotton/button.html`: the loading span now carries `data-loading-label`, which the panel
    framework's JavaScript reads to show "Uploading…" while a file goes up.
  - `panel_framework/modal/form.html`: the form adds `hx-encoding="multipart/form-data"` when
    `form.is_multipart`, and holds a hidden `[data-request-error]` element for the failed-request
    message.
  - The inline record form: see the breaking change above.
- If your project has its own `htmx:responseError` or `htmx:sendError` handler that shows the
  user a message, set `event.detail.requestConfig.panelErrorShown = true` in it. Otherwise a
  panel form adds its own "Your changes could not be saved" message as well as yours.
- If your forms take file uploads, set your reverse proxy's request body limit at or above the
  largest file your forms allow. A 413 from the proxy shows "The file may be too large to upload."
- Rebuild Tailwind: the changed templates use a utility class, `[&_p]:text-error`, that your
  bundle does not include yet.
