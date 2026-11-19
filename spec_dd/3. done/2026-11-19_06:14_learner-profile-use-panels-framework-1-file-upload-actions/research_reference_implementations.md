# Research: reference implementations for file upload in a panel/admin-style framework

Topic: `reference_implementations`. Question: how do comparable projects solve file upload for htmx/ajax-posted form actions?

Method note: written from knowledge of these projects' documented behaviour; URLs are the canonical docs, not re-fetched in this session. Verify exact attribute names before the spec cites them.

## Settled inputs (from answers.md)

- Failed (422) re-render: file input returns empty with a "choose again" message on the field. No server stash.
- Existing file: name as link, "Remove" checkbox when optional, picker to replace (ClearableFileInput behaviour).
- In flight: Save disabled and relabelled "Uploading…". No progress bar.

## 1. How the framework decides to send multipart

| System | Mechanism |
|---|---|
| Django admin | Template emits `enctype="multipart/form-data"` when `has_file_field` is true. The admin computes it from `form.is_multipart()` (and inline formsets' `is_multipart()`). Auto-detection, no flag. |
| Django core | `Form.is_multipart()` is true if any widget has `needs_multipart_form = True` (`FileInput` and subclasses). Docs tell template authors to branch on it. |
| django-unfold | Reuses admin's `has_file_field` / `form.is_multipart` logic in its overridden change_form templates. Auto. |
| Wagtail admin | Generic form templates use `{% if form.is_multipart %} enctype="multipart/form-data"{% endif %}`. Auto. Its image/document upload views are separate multipart forms. |
| django-crispy-forms | `FormHelper.form_tag` renders `<form>`; helper adds `enctype="multipart/form-data"` when `form.is_multipart()`. Auto. Also `helper.attrs` for manual override. |
| django-cotton | No form component by default; project components pass `enctype` through attributes. Patterns in the wild: `<c-form :form="form">` computing `enctype` from `form.is_multipart`. |
| Neapolitan | Generated templates use `{% if form.is_multipart %}` style conditional in its form template; plain POST, no htmx. |
| htmx | htmx does NOT auto-switch encoding. Needs `hx-encoding="multipart/form-data"` on the form (or the element or an ancestor; `hx-encoding` is inherited). Otherwise the file field posts as a filename string only. Without the attribute, the native `enctype` on a `<form>` is honoured by htmx for form-triggered requests (htmx reads `enctype` attribute on the form too), but `hx-encoding` is the documented route. |
| Filament (Laravel) | Upload fields (`FileUpload`) are Livewire-driven: a file is uploaded immediately on pick to a temp location, the form state holds a temp reference. Not a form-submit upload. |
| Livewire | `WithFileUploads` trait; chosen file uploads to a temporary signed route at once, property becomes a `TemporaryUploadedFile`; on save, app moves it. Events `livewire-upload-start/progress/finish/error`. |
| Rails ActiveStorage | Form helper `f.file_field` makes `form_with` multipart automatically; `direct_upload: true` uploads straight to storage via JS and submits a signed blob id. |
| Phoenix LiveView | `allow_upload/3` plus `<.live_file_input>`; upload runs over the socket on pick, with entries holding progress and errors; `consume_uploaded_entries` on submit. |

Pattern: every server-rendered form system auto-detects (Django `is_multipart()`, Rails `file_field`). Only the htmx layer needs an extra attribute, so the right place is one shared form template/helper that emits both `enctype` and `hx-encoding` conditionally on `form.is_multipart()`. The upload-on-pick systems (Livewire, Filament, LiveView, ActiveStorage direct) all keep temp state server-side or in storage, which is the design the answers explicitly rejected.

## 2. How files reach the form

- Django: `Form(data=request.POST, files=request.FILES, instance=...)`. Admin and every ModelForm view pass `request.FILES` as the second positional argument. The framework gap named in idea.md (`get_form` builds from `request.POST` only) is exactly this.
- Applicable generic rule: pass `files=request.FILES` always (an empty `MultiValueDict` for non-multipart requests is harmless), so forms without a file field behave as today. Django admin does the same unconditionally.
- Widget semantics to rely on: `FileField.clean(data, initial)` returns `initial` when no new file is sent; `ClearableFileInput` posts `<name>-clear` and returns `False` to clear; clearing a required field is a validation error. The framework gets all of this for free by handing the form both `files` and `instance`.

## 3. Existing file display and clear

- Django admin / `ClearableFileInput`: "Currently: <a href=url>name</a>", a "Clear" checkbox (only if field not required), "Change: <input type=file>". Template `django/forms/widgets/clearable_file_input.html`. In Django 6.x, check whether the widget templates changed (the 5.x widgets were restyled via template overrides, `use_fieldset` in some). Overridable per project via a form renderer or `template_name`.
- django-unfold: restyles the admin widget with Tailwind via `UnfoldAdminFileFieldWidget`, which keeps the current-file link, clear checkbox and file input. Closest analogue: Tailwind-styled ClearableFileInput.
- Wagtail: current image/document shown with a "Replace/Remove" style control in its chooser widgets; a different pattern (chooser), not applicable.
- Filament: shows file chips with a remove button (JS state), not applicable to plain posts.
- Applicable: the answers already choose ClearableFileInput. The framework should (a) use the Django widget with a framework template override so styling is generic Tailwind (no FLS names), (b) not rely on `MEDIA_URL` assumptions beyond `file.url`; if a storage returns no URL, the widget should degrade to name-only text.

## 4. Errors for files

- Django admin: field errors rendered above the widget; after a failed submit the browser cannot re-populate a file input, so the field comes back empty. Admin does not message "choose again" for a field whose other values were fine; users see the other fields kept and the file lost silently unless the form has a model-saved file. This is the "lost silently" problem idea.md wants to avoid.
- Django docs note a file input cannot be pre-filled for security reasons.
- Workarounds elsewhere: django-file-resubmit and similar apps stash uploads in cache and render a hidden key (the stash design the answers rejected). Wagtail/Filament/Livewire avoid the problem by uploading on pick.
- Applicable: add a non-field error or field-level note only when the bound form had a file in `request.FILES` for a file field and the form is invalid (or any other error exists). Implementation sketch: after `is_valid()` is false, for each file field with a posted file, append a message such as "Choose the file again" (via `form.add_error` before rendering, or a template note), and render the empty input. If the file field itself is invalid (size, type) the consumer's own message already applies; no extra message needed for that field, just an empty input. Keep status 422 as today.
- Caveat: `add_error` on a field after validation is fine for display, but must not make a previously valid form invalid on the success path; do it only on the invalid branch.

## 5. In-flight UI

- htmx events: `htmx:beforeRequest`, `htmx:afterRequest`, and `htmx:xhr:progress` (with `loaded`/`total`) for progress. htmx docs sample: a `<progress>` bound to `htmx:xhr:progress` (the "file upload" example). Answers chose no progress bar.
- htmx built-ins for a disabled button: `hx-disabled-elt="this"` or `hx-disabled-elt="find button[type=submit]"` (htmx 2.x) disables the element during the request. `hx-indicator` toggles `htmx-request` class for CSS spinners. Label swap can be done with CSS keyed on `.htmx-request` or with Alpine/hyperscript, or a tiny `htmx:beforeRequest` handler. Pure CSS option: two spans inside the button, one shown only under `.htmx-request`, which avoids JS.
- Livewire: `wire:loading` and `wire:loading.attr="disabled"`, comparable declarative pattern. Filament disables submit while uploads in progress. LiveView disables on upload-pending via `entry.progress`.
- Applicable: `hx-disabled-elt` plus a CSS label swap is the most generic and needs no framework JS. Should apply to every panel form (inline and dialog) or only multipart forms; idea.md says forms without file fields must behave as today, so scope it to multipart forms to avoid changing existing behaviour.
- Dialog gotcha: htmx 2 inheritance of `hx-disabled-elt`/`hx-encoding`; setting them on the `<form>` element works for both shapes. If an inline form's swap target replaces the form on 422, the new form gets the attributes again from the same template, so state resets cleanly.

## 6. What is applicable for a generic framework

1. One shared place decides multipart: the form-rendering template(s) emit `enctype="multipart/form-data"` and `hx-encoding="multipart/form-data"` iff `form.is_multipart`. No per-action flag needed; mirrors Django admin and crispy forms. A flag adds a way to get it wrong. Offer no override unless a consumer has a non-Django form.
2. `get_form` passes `files=request.FILES` alongside `data=request.POST` in `FormPanelAction`, `EditAction`, `CreateInstanceAction` (shared helper, avoid duplicating).
3. Framework-styled ClearableFileInput template override scoped to the framework, with generic Tailwind classes. No storage, size or type logic (matches idea.md).
4. "Choose again" message appended only on the invalid branch for file fields that had an upload.
5. In-flight: `hx-disabled-elt` on the submit button and CSS-based label swap to "Uploading…", only for multipart forms.
6. Django-only guarantees to test: multipart sent for inline and dialog; file arrives in `cleaned_data`; instance file kept when no new file; Remove checkbox clears optional file; 422 returns empty input with the message; non-file form unchanged (no `hx-encoding`, no `hx-disabled-elt`).
7. Do not copy: upload-on-pick, temp storage and signed routes (Livewire, Filament, ActiveStorage direct, LiveView). They need storage decisions the framework must not make, and the answers rejected the stash.

## Open questions for the spec

- How the dialog `modal/form.html` renders and whether `hx-encoding` on the `<form>` works when the dialog content is loaded by htmx swap (it should; verify in a test with the Django test client posting multipart plus a browser check).
- Whether the "Uploading…" label should be configurable text (i18n) via the existing template context.
- Django 6.x ClearableFileInput template and `Form.template_name` changes; confirm the override path.

## References

- Django file uploads: https://docs.djangoproject.com/en/stable/topics/http/file-uploads/
- Django `Form.is_multipart()`: https://docs.djangoproject.com/en/stable/ref/forms/api/#django.forms.Form.is_multipart
- Django `ClearableFileInput`: https://docs.djangoproject.com/en/stable/ref/forms/widgets/#clearablefileinput
- Django admin change_form (`has_file_field`): https://github.com/django/django/blob/main/django/contrib/admin/templates/admin/change_form.html
- htmx `hx-encoding`: https://htmx.org/attributes/hx-encoding/
- htmx `hx-disabled-elt`: https://htmx.org/attributes/hx-disabled-elt/
- htmx file upload example (progress): https://htmx.org/examples/file-upload/
- django-unfold: https://unfoldadmin.com/ and https://github.com/unfoldadmin/django-unfold
- Wagtail forms: https://docs.wagtail.org/en/stable/
- django-crispy-forms helper: https://django-crispy-forms.readthedocs.io/en/latest/form_helper.html
- django-cotton: https://django-cotton.com/
- Neapolitan: https://github.com/carltongibson/neapolitan
- django-htmx: https://django-htmx.readthedocs.io/
- Filament FileUpload: https://filamentphp.com/docs/3.x/forms/fields/file-upload
- Livewire uploads: https://livewire.laravel.com/docs/uploads
- Rails ActiveStorage direct uploads: https://guides.rubyonrails.org/active_storage_overview.html#direct-uploads
- Phoenix LiveView uploads: https://hexdocs.pm/phoenix_live_view/uploads.html

status: ok
