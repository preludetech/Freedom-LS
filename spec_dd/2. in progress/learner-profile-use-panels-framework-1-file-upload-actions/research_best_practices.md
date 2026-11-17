# Research: best practices for file upload in an HTMX 2 + Django panel framework

Scope: `FormPanelAction` and subclasses (inline and dialog), 422 re-render, decisions in `answers.md` (empty input on 422 with "choose again" message; ClearableFileInput-style name + Remove; Save disabled with "Uploading…"). Items marked (docs) were checked against the cited pages this session; items marked (background) are well-established knowledge not re-fetched, so the spec author should verify them if they become a hard requirement.

## 1. HTMX 2 file uploads

- (docs) Set `hx-encoding="multipart/form-data"` on the form (or the element issuing the request) so htmx sends a `FormData` body and files are included. Source: https://htmx.org/docs/#files
- (background) htmx also switches to multipart automatically if the form element has a native `enctype="multipart/form-data"` attribute, and `hx-post` on a `<form>` honours the form's `enctype`. Safest requirement: put the native `enctype="multipart/form-data"` on the `<form>` (also gives a working non-JS fallback) AND `hx-encoding`. Either way, the spec should require a test that asserts the rendered form carries the encoding, not rely on one mechanism.
- Without multipart, the file input posts only a filename string, `request.FILES` is empty, and the form reports "This field is required". This is the classic failure; the framework must set encoding itself, not leave it to each consumer.
- (docs) Django `request.FILES` is populated only for POST, with a posted file field, and `enctype="multipart/form-data"`. Source: https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/
- Make the encoding conditional: emit multipart only when the form has a file field (`form.is_multipart()` is the Django API for this). That satisfies "forms without a file field behave exactly as today" (urlencoded stays urlencoded).
- Dialog shape: the modal template (`panel_framework/modal/form.html`) is a separate template from the inline form, so both need the same `is_multipart()`-driven attributes. Best practice is one shared partial/attribute helper so the two cannot drift.
- Progress: (docs) htmx fires `htmx:xhr:progress` during upload (`event.detail.loaded`/`total`), but the decision is no progress bar, so do not build it. Source: https://htmx.org/docs/#files, events at https://htmx.org/events/
- In flight state: (docs) `hx-disabled-elt` sets `disabled` on the named elements for the request duration; (docs) htmx puts class `htmx-request` on the requesting element (and `hx-indicator` targets) while in flight. Sources: https://htmx.org/docs/#indicators, https://htmx.org/attributes/hx-disabled-elt/
  - Use `hx-disabled-elt="find button[type=submit]"` (or `this` on the button) on the form. The label swap to "Uploading…" can be done without JS by having two spans in the button, with the "Uploading…" span hidden by default and shown under `.htmx-request`, and the normal label hidden under `.htmx-request`. Needs Tailwind variants or a small CSS rule; htmx's built-in indicator CSS only handles opacity, so the spec should say how the swap is styled.
  - Should this apply to all panel forms or only multipart ones? Requirement-wise, restrict to forms with a file field to keep other forms unchanged (or accept it as harmless and say so).
  - Disabled controls are excluded from submitted values, but htmx gathers values before applying disabled state (order of operations: values gathered, then `htmx-request` class applied). Safe for the submit button; do not disable the file input itself (disabled inputs are not sent). Source: https://htmx.org/docs/#request-operations
  - Because the swapped-in 422 response replaces the form, the button state resets naturally. After a successful swap the dialog closes or the panel re-renders, also resetting it. Spec should add a test/QA step for network error (`htmx:send-error`/timeout): the button must not stay stuck disabled. htmx removes `htmx-request` and the disabled state on error as well (background), but verify.

## 2. 422 swaps in htmx 2

- (docs) htmx 2 default `responseHandling` includes `{code:"[45]..", swap:false, error:true}`, so 422 is NOT swapped by default. Add `{code:"422", swap:true}` (before the `[45]..` rule) to swap it. Source: https://htmx.org/docs/#response-handling
- The panel framework already returns 422 for validation errors, so it must already configure this globally or per request (`htmx:beforeSwap` handler or `htmx.config.responseHandling`). Spec should state that file forms rely on the same existing mechanism, and a test/QA check should confirm that a multipart 422 swaps (it is the same code path, but this is the most likely place a regression hides).
- Other 4xx for uploads that the framework should expect: 413 (reverse proxy `client_max_body_size`), 400 (Django `RequestDataTooBig` / `TooManyFilesSent` are `SuspiciousOperation`, giving 400). These are not swapped by default; the user sees nothing. See section 7.

## 3. Django forms with files

- Pass `request.FILES` as the second argument: `Form(request.POST, request.FILES, ...)`; for ModelForm also `instance=`. Source: https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/ . The framework's `get_form` on `FormPanelAction`/`EditAction` must pass `files=request.FILES` (only on POST). This is the core code change.
- `ClearableFileInput` (default widget for `FileField`/`ImageField` in ModelForm): renders "Currently: <a href>name</a>", a "Clear" checkbox (only when the field is not required and has an initial), and "Change:" + the file input. Source: https://docs.djangoproject.com/en/5.2/ref/forms/widgets/#clearablefileinput . Clearing uses a `<name>-clear` checkbox; `FileField.clean` returns `False` for clear, and ModelForm save clears the reference (it does not delete the stored file from storage; storage cleanup is a consumer/`file-storage` skill concern).
- Framework styling implies overriding the widget template (`django/forms/widgets/clearable_file_input.html`) or a framework widget subclass rather than hand-rendering fields. Overriding via the widget template keeps `-clear` naming compatible with Django's own `value_from_datadict`.
- Spec should require: the "Currently" link uses `file.url` of the storage the consumer configured; the framework must not render `file.path`.
- On a 422 re-render the bound form's file field has no retained upload (see section 4). For an EditAction the instance's existing file is still shown via `initial`, so the "Currently: name" line and Remove checkbox persist. Spec should say explicitly which wins: the existing instance file is shown on re-render; the error message tells the user to choose the new file again. Test case: edit with existing file + invalid other field + new file selected -> 422, existing file still displayed, new file not retained, message on the file field.
- Message requirement: Django adds no "choose again" message when another field fails. The framework would add it in the 422 path. Spec must define the trigger (a file was uploaded but the form is invalid) and avoid showing it when the user did not select a file, or when the file field itself already has an error (avoid double or contradictory messages).
- Size/type validation lives in the consumer form (`clean_<field>`, `FileExtensionValidator`, `ImageField` using Pillow). The dev reference page should show an example validator with max size and allowed extension. Do not trust browser-supplied `content_type`; Pillow/`ImageField` verifies image content. Source: https://docs.djangoproject.com/en/5.2/ref/forms/fields/#imagefield
- Django limits that apply before the form is reached (https://docs.djangoproject.com/en/5.2/ref/settings/):
  - `FILE_UPLOAD_MAX_MEMORY_SIZE` (default 2.5 MB): above this the upload streams to a temp file; it is NOT a size cap. (docs: file-uploads page)
  - `DATA_UPLOAD_MAX_MEMORY_SIZE` (default 2.5 MB): caps request body size excluding file upload data; non-file fields count. (background)
  - `DATA_UPLOAD_MAX_NUMBER_FIELDS` (1000) and `DATA_UPLOAD_MAX_NUMBER_FILES` (100): exceeding raises `SuspiciousOperation`, giving 400. (background)
  - Therefore Django has no built-in max file size; an actual cap needs the form validator, plus reverse proxy limits for early rejection.
- Write uploads using `chunks()` not `read()` for large files. Source: file-uploads page.

## 4. Why browsers cannot refill file inputs

- An `<input type="file">` value cannot be set from HTML or normal script to a path; only the user can choose a file (script can only assign `input.files` from a `DataTransfer` of File objects it already holds). This prevents a malicious page from silently uploading local files. Sources: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file , https://html.spec.whatwg.org/multipage/input.html#file-upload-state-(type=file)
- Consequence: a server re-render of a 422 form cannot restore the file. Options were (a) ask to re-choose (decided), (b) server stash of the temp file with a token (complex: storage, cleanup, security surface), (c) client-side `hx-preserve` on the file input with a stable `id` so the browser keeps the selection. `hx-preserve` has caveats (needs unique stable id, element is moved not recreated, awkward with inline-vs-dialog re-render and with the field's error styling). Source: https://htmx.org/attributes/hx-preserve/ . Not chosen; the spec should record it as a rejected alternative.
- This is why the message is mandatory: silent loss is the failure mode the idea forbids. Other fields are re-rendered from POST data so only the file input is lost.

## 5. CSRF with multipart

- Panel forms use `hx-headers='{"X-CSRFToken": ...}'` on `<body>` (project convention), which works with multipart because the token travels in a header. Django's CSRF middleware accepts the `X-CSRFToken` header and falls back to the `csrfmiddlewaretoken` POST field. Source: https://docs.djangoproject.com/en/5.2/howto/csrf/ (multipart specifics: background).
- If the spec ever adds custom upload handlers, they must be set before `request.POST` is accessed, which forces splitting CSRF decorators around the handler-changing view (see file-uploads page). Out of scope: the spec should simply say no custom upload handlers.
- Inline forms that include `{% csrf_token %}` as a hidden field also work with multipart. Requirement: a test posting multipart with a valid token to an inline and dialog action succeeds, and without it returns 403.

## 6. Accessibility (WCAG 2.2) for file inputs and errors

- Label: every file input needs an associated `<label for>` (WCAG 1.3.1, 3.3.2, 4.1.2). Do not hide the native input with `display:none` for a custom button; if styled, keep it focusable with visible focus (2.4.7, 2.4.11). Use Tailwind `file:` variants to style the native control. Sources: https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html , https://www.w3.org/WAI/tutorials/forms/
- Instructions: state constraints (allowed types, max size) in help text associated via `aria-describedby` (3.3.2). The framework renders `help_text` linked to the input; the consumer supplies content.
- Errors (3.3.1 Error Identification): error is text, identifies the field, and is programmatically associated: `aria-invalid="true"` on the input and `aria-describedby` pointing to the error element id. (3.3.3 Error Suggestion): the "choose the file again" message itself is the suggestion. Sources: https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html , https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html
- Announcing errors after an htmx swap: the swapped form replaces the focused element, so focus is lost. Best practice (4.1.3 Status Messages): after a 422 swap, move focus to the first invalid field or an error summary, or use a `role="alert"` region. The spec should check what the framework already does for other fields on 422 and require the file field to behave identically; the risk is the file input being skipped because it renders from a different widget template.
- Disabled-while-uploading: the label change to "Uploading…" is announced only if in a live region. Prefer `aria-busy="true"` on the form plus a visually hidden `role="status"` element. A `disabled` button can drop keyboard focus in some browsers; `aria-disabled` is the accessible alternative but `hx-disabled-elt` sets the real `disabled` attribute. Spec: accept `disabled` (decided), note the trade-off, and require the status text be exposed.
- Remove checkbox: a real checkbox whose label names the file ("Remove current file: name"). The "Currently" link text is the file name (2.4.4).
- Dialog: existing modal a11y (focus trap, focus return) is inherited. Closing the dialog mid-upload: spec should decide or consciously leave as today (request completes; swap target may be gone).

## 7. Security baseline and robustness (framework level)

- Framework must not render `file.path`, absolute storage paths, or raw storage exception text; use only the basename (`file.name`) and `file.url`. Django reduces uploaded names to a basename (background). Source: https://docs.djangoproject.com/en/5.2/topics/security/#user-uploaded-content
- The framework does not choose storage/size/type (decided), but the dev reference example should demonstrate a safe consumer pattern: validate extension and content, set a max size, generate storage names via `upload_to` (not the client filename), serve uploads as the `file-storage` skill prescribes. Cross-reference `fls-dev:file-storage` rather than restating.
- Autoescape file names in templates; never mark safe. Test with a name containing `<script>` or quotes.
- Missing multipart encoding: if a consumer form has a file field but the form was rendered without multipart, Django silently yields "required" errors. Deriving encoding from `form.is_multipart()` makes that impossible; tests should assert it. Server-side, nothing else needed.
- Unhandled transport failures: 413/400 from `DATA_UPLOAD_MAX_*` or proxy limits are not swapped, so the user sees nothing. Consider handling `htmx:responseError` and `htmx:sendError` for panel forms (check whether the framework already shows a generic error) and require at least that the Save button resets; say whether a visible generic "upload failed" message is in scope.
- Only touch FILES on POST; GET must not.
- Project convention: no logging unless asked.
- Testing: the Django test client posts multipart by default with `SimpleUploadedFile`; point `MEDIA_ROOT` at a temp dir or use in-memory storage so tests do not write into the repo. Source: https://docs.djangoproject.com/en/5.2/topics/testing/tools/ (background).

## 8. What the spec should require (checklist)

1. `get_form` (FormPanelAction, EditAction, CreateInstanceAction and any override) passes `request.FILES` on POST; no behaviour change for forms without file fields.
2. Inline and modal forms emit `enctype="multipart/form-data"` and `hx-encoding="multipart/form-data"` only when `form.is_multipart()`, from one shared source.
3. 422 re-render: file input empty; field-level message to choose the file again, shown only when a file was submitted, the form is invalid and the file field has no other error; existing instance file still shown with name link and Remove checkbox (when not required); ids wired for `aria-describedby`/`aria-invalid`; focus/announcement same as other fields.
4. ClearableFileInput template override with framework styling; label and help text association; file name link uses `url`; no filesystem paths; escaped output.
5. Save button: `hx-disabled-elt` on the submit button; label "Uploading…" while `htmx-request`; resets on 422, success and transport error; status exposed to assistive tech; file input itself not disabled.
6. Confirm the 422 swap config applies to multipart requests (test/QA).
7. CSRF works for multipart in both shapes (header and hidden field); 403 without.
8. Dev reference page `/panel-framework/` example: optional file field with consumer validators (size, extension), inline and dialog. Tests: successful upload, 422 (input empty, message, existing file kept), clear checkbox, hostile filename escaping, non-file form unchanged.
9. Record as non-goals/rejected: server-side stash, `hx-preserve` retention, progress bar, custom upload handlers, framework-level size/type limits.
10. Edge cases to decide or note: dialog closed mid-upload; proxy/Django size-limit failures (400/413 unswapped) and generic error display.

## Sources

- https://htmx.org/docs/ (File Upload, Request Indicators, Configuring Response Handling, Request Order of Operations)
- https://htmx.org/events/
- https://htmx.org/attributes/hx-disabled-elt/
- https://htmx.org/attributes/hx-preserve/
- https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/
- https://docs.djangoproject.com/en/5.2/ref/forms/widgets/#clearablefileinput
- https://docs.djangoproject.com/en/5.2/ref/forms/fields/#imagefield
- https://docs.djangoproject.com/en/5.2/ref/settings/
- https://docs.djangoproject.com/en/5.2/topics/security/#user-uploaded-content
- https://docs.djangoproject.com/en/5.2/howto/csrf/
- https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file
- https://html.spec.whatwg.org/multipage/input.html#file-upload-state-(type=file)
- https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html
- https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
- https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html

status: ok
