# Panel framework form actions accept file uploads

Spec 1 of 3 in the Account area on panels effort. Read the "Account area on panels" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A panel framework form action can carry a file field. A user picks a file in an inline panel form
or in a dialog, saves, and the action receives the file. When the form comes back with errors
(HTTP 422), the user is told the file has to be chosen again or the file is kept; the spec picks
one, and nothing is lost silently.

## Why

The account area (`learner-profile-use-panels-framework-3-account-page`) needs a profile picture
panel, and `learner-public-profile-4-certificates` needs certificate uploads. Today
`FormPanelAction.get_form` and `EditAction.get_form` build their forms from `request.POST` only,
and `panel_framework/modal/form.html` posts without multipart encoding. The only upload in the
educator interface, the learner CSV import, is a plain Django view. Upload is a framework gap, not
a consumer detail, so it belongs in the framework once rather than in each page.

## What is settled

- The capability lives in `freedom_ls/panel_framework`, generic, with no FLS name in it. It must
  survive `extract_panels_framework-3-standalone-backend` and
  `extract_panels_framework-4-template-contract` unchanged in behaviour.
- It covers both the inline panel form (the shape `LearnerNamePanel` uses) and the dialog form
  (`panel_framework/modal/form.html`), for `FormPanelAction` and its subclasses, including
  `EditAction` and `CreateInstanceAction`.
- Forms without a file field behave exactly as they do today.
- Validation errors return 422, as every panel form does.
- The framework does not decide storage, size limits or file-type checks. Those belong to the
  consumer's form and model, which validate the upload as any Django form does.
- The dev reference page at `/panel-framework/` gains an example of a file field on a panel
  form, with framework tests for the inline and dialog shapes.
- No consumer page changes in this spec. The picture panel is
  `learner-profile-use-panels-framework-3-account-page`.

## Open until the spec

- Whether a chosen file survives a 422 re-render, or the form tells the user to choose it again.
- How an existing file is shown and cleared in the form (current file name, a remove control).
- Upload progress or a disabled Save while uploading.

## Out of scope

- Image cropping, resizing or previews.
- Drag-and-drop upload and multiple files in one field.
- Any consumer panel.

## Resources

- `spec_dd/1. next/learner-profile-use-panels-framework/research_panel_framework_fit.md`, "File
  upload: not supported"
- Skills: `fls-dev:panel-framework`, `ds:htmx`, `fls-dev:file-storage`
