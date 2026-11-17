# Research: UX patterns for single-file inputs in panel forms

Topic `ux_patterns`. Settled by `answers.md`: one file per field; on a 422 the picker returns empty with a "choose again" message; an existing file shows as a name link plus a "Remove" checkbox (optional fields) plus a picker to replace; Save disabled and labelled "Uploading…" while in flight; no progress bar, drag-and-drop or preview.

Source confidence: GOV.UK, USWDS, Django docs and the project skills were read directly. Primer's page returned only its homepage, and Atlassian and Material were not fetched. Statements about those three, and about Django's default ClearableFileInput labels, come from background knowledge and are marked (unverified).

## 1. What the design systems say

### Label and hint
- GOV.UK: a specific label ("Upload a file", or better the thing, e.g. "Profile picture"). It asks for a file only when needed. It gives no hint wording rules. Its newer component keeps "No file chosen" and the button text short because long text is hard for screen reader users.
- USWDS: every file input has a `<label for>` tied to the input `id`. A separate hint element (`usa-hint`) states restrictions (types, size). One file per input is preferred because multi-select confuses some users.
- Primer / Atlassian / Material (unverified): all pair a visible label with caption/helper text under the control. The restrictions go in that helper text, not the label.

Pattern: label names the thing ("Profile picture"), the hint under the field states restrictions the consumer's form knows, such as types and size. The framework only renders `help_text` (see mapping below).

### Showing the stored file
- GOV.UK's guidance on previously uploaded files is to show the file as a choice so the user need not upload again, and to think about shared devices before exposing a preview or download.
- USWDS lists the selected file's name (and a thumbnail, which this spec excludes). It specifies no remove or change wording.
- Django `ClearableFileInput` (docs: https://docs.djangoproject.com/en/stable/ref/forms/widgets/#clearablefileinput): renders the file input plus a clear checkbox only when the field is not required and has initial data. Its default text is "Currently: <link>", a "Clear" checkbox and "Change:" before the picker (unverified; the docs page does not list them).

Pattern: current file name as a link, then a way to clear, then a picker to replace.

### Remove and replace wording
No system standardises it. The common vocabulary is "Remove" (Primer, Atlassian, GOV.UK multi-file "Delete"/"Remove" uses) and "Replace" or "Change" for the picker. The decided "Remove" matches. Django's stock "Clear" and "Change:" should be overridden for consistency:
- Checkbox label: "Remove <file name>" (accessible name carries the object, as the framework's "two buttons never share a bare verb" rule and the card rule on accessible names ask) or visibly "Remove". With several file fields on one page, the bare word repeats, so give the checkbox `aria-label`/visually hidden text naming the field ("Remove profile picture").
- Picker label when a file exists: keep the field label, and let the hint or the surrounding text say that choosing a file replaces the current one ("Choose a file to replace it"). Avoid a second visible label such as "Change:".
- Remove is a checkbox applied on Save, not an immediate action. Say so in wording that is true after the action: the checkbox is "Remove" and the file goes on Save. Remove and a newly chosen file both set: Django's clear-vs-upload rule makes the upload win, or raises a validation error on the field (Django raises "Please either submit a file or check the clear checkbox, not both."). The spec should pick one and word it.

### "Choose the file again" message after a 422
- GOV.UK's file-upload error wording: "Select a <thing>" for no file ("Select a report"). Other errors: "The selected file must be a CSV or ODS", "The selected file must be smaller than 2MB", "The selected file could not be uploaded – try again". It has no dedicated wording for re-choosing after a failed form (it says that itself; the nearest are "Select a …" and the "try again" line).
- The project's voice (`.claude/skills/brand-guidelines/voice.md`, "Error messages"): name the problem, suggest the fix, leave blame out, end on a full stop.

Candidate wording, in the voice and GOV.UK's "Select a …" style:
- "Choose your profile picture again. The form had other errors, so the file was not kept." This names the cause and the fix.
- Shorter: "Choose the file again. It is not kept when the form has errors."
- When the file itself is invalid, the consumer's own message wins (GOV.UK style: "The selected file must be smaller than 2 MB."). Do not stack the "choose again" line on top of it; the picker is empty either way.
- Use "Choose" (the picker's own verb) rather than GOV.UK's "Select", so the message matches the control. This is the framework's own message wording and is a spec decision.

Show it only when the failed post carried a file, or when a file was required and none came back. A 422 with no file chosen and nothing stored needs no extra message beyond the field's own required error.

### In-flight button state
- GOV.UK, USWDS: neither defines an uploading label. GOV.UK's button guidance prevents double submit, and its uploading state is left to teams.
- The framework already has the convention: a dialog's `loading_text` ends in the ellipsis character "…", and `hx-disabled-elt` is `find button[type='submit']` (panel-framework skill, "Dialogs, sheets and the quick view"). The decided "Uploading…" fits this exactly and should come from the same `loading_text` mechanism where the form has a file field, rather than a new one.
- Keep the label one line at 375px (brand-guidelines visual: "A button label fits on one line"). "Uploading…" is shorter than "Save".
- Announce the change: a button whose label changes is not announced by every screen reader. A polite live region or `aria-busy` on the form covers this (the spec decides; a framework-wide live region does not exist today, as far as these two skills say).
- Disabling only the form's own submit buttons is enforced by `test_every_dialog_disables_only_its_own_submit_buttons`. Do not disable the file input itself; a disabled input is not sent.

## 2. Accessibility checklist
- A visible `<label for>` bound to the file input's `id` (USWDS). Django's `BoundField.label_tag` does this, as long as the widget template keeps the `id` on the file input and not on the checkbox.
- Hint and error ids joined in `aria-describedby` on the file input, plus `aria-invalid="true"` in the error state. This is the framework's inline-form rule: one line under the field, no field label prefix, `role="alert"`, input names it with `aria-describedby` and has `aria-invalid`. It fits the file field unchanged.
- The error ids must be on the file input, not on the "Currently" link or the Remove checkbox.
- The Remove checkbox has its own label that names the object. The stored file's link is a real link, not an underlined-by-default `<a>`: in panel pages every anchor is a control and needs `no-underline`/`<c-button variant="link">` (skill "Controls are components"; `test_no_control_link_is_hand_styled`). The file link opens the file, so it should be a `<c-button variant="link">` or the row-link style.
- Keyboard: a native `<input type="file">` is tabbable and opens the picker with Space/Enter. Do not hide it behind a custom styled button unless the native input stays focusable (USWDS notes a screen reader confusion with its combined drag/choose control, and voice-control users cannot always trigger a hidden input). Keep the native input, framework-styled, with the focus ring kept (skill: buttons, links and fields keep their focus rings).
- Do not rely on colour: the error line carries text, and Signal on white is 5.0:1 (brand visual).
- Focus after a 422 re-render: the inline form shows one line under the field with `role="alert"`, so the failing field's message is announced. In a dialog, the framework's `partials/error_summary.html` and its `tabindex="-1"` focus handling apply (skill: dialog shapes; a multi-field dialog uses the error summary).
- The empty picker after a 422 is a native input: browsers do not allow a script to restore a chosen file, so the empty state is the platform behaviour, and the message should say so rather than hide it (nothing lost silently).
- Do not require preview/download of the stored file where it is sensitive (GOV.UK shared-device point). The link is the consumer's call (an unguessable or authenticated URL); the framework only renders `field.value.url`.

## 3. Mapping to the panel framework's rules

| Pattern | Fits the framework how | Gap or decision for the spec |
|---|---|---|
| Label + hint under the field | "A field's hint sits directly under the field as its help text" | Hint comes from the form field's `help_text`; the framework adds no restrictions text |
| Inline error, one line, no label prefix, `role="alert"`, `aria-describedby`, `aria-invalid` | Existing inline-form rule | Apply it to the file input; add the "choose again" line as that field's error (or as a second line of the same alert) |
| Dialog error display | `partials/error_summary.html` and `<c-panel-notice tone="error">` | Same choose-again wording; summary entry links to the file input |
| Stored file as name link | Anchors are controls; use `<c-button variant="link">` or the row-link style | Widget template override needed; not Django's bare `<a>` |
| Remove checkbox only when optional | Matches ClearableFileInput's own rule | Name the object in the accessible name; decide upload-plus-remove outcome |
| Replace picker | Native input, framework base styling (form inputs take no classes) | None; no custom button |
| Save "Uploading…" | `loading_text` ends in "…"; `hx-disabled-elt="find button[type='submit']"` | Inline panel forms (not dialogs) need the same behaviour; the invariants cover dialogs only, so the spec should add a test for the inline shape |
| Multipart encoding | not a UX pattern, but required: `hx-encoding="multipart/form-data"` on `<form>` and `enctype` for the no-JavaScript path | Only when the form has a file field; forms without one stay unchanged (idea.md) |
| One size body text, buttons one line at 375px | Dialog and brand rules | "Uploading…" and "Remove" fit; keep the message short enough to wrap in the body without scroll |
| Voice: name the problem, suggest the fix, no blame | `voice.md` "Error messages" | Message above names cause (form had errors) and fix (choose again) |

## 4. Recommended wording (to settle in the spec)
- Choose-again error (framework-supplied, shown when the post carried a file and the form came back 422): "Choose the file again. It is not kept when the form has errors." Alternative that names the field: "Choose your <field label> again…" (reads better in a dialog summary).
- Remove control: checkbox label "Remove", with the field name in its accessible name.
- Current file: the file's base name as a link, text above or beside the picker, with no "Currently:" prefix.
- In flight: Save becomes "Uploading…" and is disabled; restored when the response arrives.
- Never claim the file was saved or lost in a way that is untrue after the action (voice rule: every sentence true after the action).

## 5. Open questions for the spec
1. Upload plus Remove ticked together: upload wins silently, or a field error? Django's default is an error; the idea's "nothing is lost silently" favours keeping that error.
2. Where does the in-flight label come from for inline forms: reuse `loading_text` on `FormPanelAction`, or a file-field-only default?
3. Is a live-region announcement for the busy state in scope, given no existing framework mechanism?
4. Does the file link need an `aria-label` that says it opens in a new tab or downloads? Depends on the consumer's storage (`fls-dev:file-storage`).

## References
- GOV.UK Design System, File upload: https://design-system.service.gov.uk/components/file-upload/
- USWDS, File input: https://designsystem.digital.gov/components/file-input/
- Django, ClearableFileInput: https://docs.djangoproject.com/en/stable/ref/forms/widgets/#clearablefileinput
- Primer (page returned only its homepage; claims unverified): https://primer.style/components/file-input
- Project: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `.claude/skills/brand-guidelines/voice.md`, `.claude/skills/brand-guidelines/visual.md`

status: ok
