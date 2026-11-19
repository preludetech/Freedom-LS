# Upload requirements

Spec 7 of 10 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Applicants upload a document for an upload requirement, outside any form sitting, and upload again
when the resolver asks for the same upload again. They see the current document and a collapsed history of earlier uploads. Reviewers see and download every version on the review screen.

## Why

Some courses need documents before approval: an identity document, a medical certificate, a prior
qualification. Without this, applicants email them and the reviewer has no record of which version was judged. The history answers "did you get my document?" before the applicant has to ask.

## What is settled

- An upload requirement takes a document on its own, outside any form sitting. It takes one again when the resolver asks for the same upload again.
- Every version is its own row, kept. The form's file answer model (`QuestionAnswerFile`) keeps no history, deletes the superseded object on save, and is not reused for storage. The version row hangs off the requirement and cascades from it.
- Reuse, not copy:
  - `validate_and_sanitise` stays in `form_engine` and is imported from there; the file types and 6 MB cap it enforces apply to every document.
  - The `user_uploads` storage alias.
  - The file streaming helper, widened to take any file row (anything with a file and an original filename).
  - A shared delete-the-object-when-the-row-goes receiver, connected to the form's file answer model and to the version model, so a row delete always takes the stored object with it.
- Erasure cascades through the application to every version, including those on superseded requirements. Nothing may filter, protect or skip superseded rows on that path. A test in the existing erasure tests proves that deleting an application, by the anonymous-applicant erasure path and by the user-delete path, removes the rows and the stored objects.
- Document types are a Python registry a deployment extends. Each type has a stable key, a label, and the rejection reasons it allows on top of the generic set from `multi-step-course-applications-6-reviewer-verdicts`. The registry is loaded once with a boot check.
- A type's description is content, authored on the course's requirement list and referenced by the type's key. A key content names that the registry does not define fails at content load and at boot.
- Uploads need a claimed applicant. The session-only access an anonymous form sitting has lapses when the sitting is completed, so it cannot carry weeks of document work.
- An upload moves the requirement to submitted and runs the reconcile.
- The upload is rate limited, keyed on the application, and runs the same validate-then-save sequence the form's file upload uses.
- The applicant sees the current document and a collapsed history of earlier uploads, including those on superseded requirements, each with the reason it was not accepted. The reason's applicant explanation comes from the document type's reason.
- Reviewers see and download every version on the review screen. The download is access-checked by the reviewer capability from `multi-step-course-applications-2-reviewers-and-inbox`. The applicant's own download is checked by ownership of the application.
- Files are served as attachments, uncached, through one download route per audience.
- Medical and identity documents get no special handling: the same storage, retention and access rules as every other upload.
- Uploaded files are not scanned, and no scanning hook is built. File scanning is not planned. Format checks and re-encoding in `validate_and_sanitise` are the defence.
- Per-type size or file-type limits are not built. The validator's limits are fixed, so a type could not enforce them.

## Open until the spec

- The storage key prefix for document files: the owning user's id, as the `file-storage` skill requires of every key under `user_uploads/`, or the application id. Claimed applicants always have a user, which favours the user id.

## Out of scope

- Scanning uploaded files.
- Per-type size, file-type or expiry rules.
- Anonymous (unclaimed) document upload.
- Moving `validate_and_sanitise` to a neutral place; that can come with a second consumer such as `learner-public-profile-4-certificates`.

## Resources

- `spec_dd/1. next/multi-step-course-applications-7-upload-requirements/research_uploads.md`: the existing upload, storage, streaming, erasure and access code, and the document type precedents.
- `claude_plugins/fls-dev/skills/file-storage/SKILL.md`
- Siblings: `multi-step-course-applications-5-requirements-and-resolver` (requirements and the reconcile), `multi-step-course-applications-6-reviewer-verdicts` (verdicts and the generic rejection reasons), `multi-step-course-applications-8-choices` (also changes the reconcile and requirements page).
