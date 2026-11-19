# Research: uploads for upload requirements

Read-only research for cutting `idea.md`. Spec 4 in the idea's order ("Upload requirements outside form sittings, with rejection reasons, choices and upload history") is the one this feeds.

## 1. `QuestionAnswerFile` and the file-upload question

**Model** (`freedom_ls/form_engine/models.py`, from `get_user_uploads_storage` down). `QuestionAnswerFile(SiteAwareModel, TimestampedModel)` has a `OneToOneField` to `QuestionAnswer` (`related_name="answer_file"`), a `FileField` and `original_filename` (display and download name only, never a key). One file per answer: a second upload replaces the first, and `save()` deletes the superseded object (`_stored_file_name` reads the old name through `_base_manager`). So the model keeps no history. A version history cannot reuse this model as it stands.

**Question type.** `QuestionType.FILE_UPLOAD` (`freedom_ls/form_engine/schema.py`). It carries no per-question size or type settings. The limits are module constants.

**Validation** is `validate_and_sanitise(uploaded_file) -> (ContentFile, extension)` in `freedom_ls/form_engine/uploads.py`. It is a pure function of an `UploadedFile`. It has no dependency on a sitting, a question, or a request.
- Extension allowlist `.jpg .jpeg .png .pdf`. Size cap `MAX_UPLOAD_BYTES` = 6 MB, checked before reading, then again on a bounded read.
- Content check: a `%PDF-` prefix passes as is (not re-encoded). Anything else is decoded by Pillow (`_reencode_image`): pixel cap 25M read from the header, `verify()` over the whole stream, a decompression-bomb guard from `freedom_ls/base/images.py`, then the format must be JPEG or PNG.
- Images are re-encoded, which drops EXIF and GPS. The detected extension is returned, so the applicant's filename never reaches a key.
- Also exported: `ACCEPT_ATTRIBUTE`, `MAX_UPLOAD_LABEL`, the error strings.
- Fixed limits: a deployment cannot change the size or types, and a document type cannot ask for "PDF only" without a parameter being added.

**Storage.** Alias `user_uploads` through `get_user_uploads_storage()` (a module-level callable on `storage_for_alias`, as the `file-storage` skill requires). Key from `question_answer_file_upload_to`: `user_uploads/{user_id}/form_answers/{answer pk}{ext}`, or `user_uploads/anonymous/{form_progress pk}/form_answers/{answer file pk}{ext}` for a sitting with no user. The skill's rule that every key under `user_uploads/` is prefixed by the owning user (so erasure is a scoped delete) is met. `user_uploads` never overwrites. Keys are pk-derived, not secret; access is the control. `_OVERWRITE_PURPOSES` is in `freedom_ls/deployment/storage.py`.

A new document model needs its own `upload_to` namespace, for example `user_uploads/{user_id}/documents/{pk}{ext}`. Per the skill, two aliases sharing a bucket must not collide, and the same alias with a new sub-prefix is fine. Because each version gets its own row and key, the "delete the superseded object" behaviour of `QuestionAnswerFile.save()` must not be copied: versions are kept.

**Serving and access** (`freedom_ls/form_engine/views.py`):
- `stream_question_answer_file(answer_file)` takes a model row and opens `answer_file.file`, reads `original_filename`, and returns a `FileResponse` as an attachment, `Cache-Control: private, no-store, must-revalidate`, slugified filename plus the FLS-chosen extension, `FileNotFoundError` mapped to 404. Its body is generic, but its signature and the two attribute names it reads are tied to `QuestionAnswerFile`. Reuse means widening the parameter to anything with `.file` and `.original_filename`, or extracting a function taking those two values. That is a small refactor, not a copy.
- Applicant route `own_question_answer_file`: row looked up with `answer__form_progress__in=owned_form_progress(request)`. Ownership is the control.
- Reviewer route `question_answer_file_download_view` (admin): `can_download_answer_files(user)` in `freedom_ls/form_engine/permissions.py`, i.e. the Django model permission `view_questionanswerfile`. Docstring in `uploads.py` says a PDF is served "to its owner, and to a superuser reviewing the application". Organisation-role reviewers (idea, "Who reviews") have no download route today. The document download route for reviewers is new work.

**Upload view** `partial_question_file_upload`: ownership check, question in `sitting_path`, `ratelimit.consume(action="form_file_upload", key=sitting pk)`, `validate_and_sanitise`, then `answer_file.file.save(f"file{extension}", content)`. The rate-limit-then-validate-then-save sequence is view code; a standalone view would repeat the sequence but call the same `ratelimit` and `validate_and_sanitise`. The rate-limit key would be the application pk.

**Delete.** `delete_question_answer_file` (`freedom_ls/form_engine/receivers.py`) is a `post_delete` on `QuestionAnswerFile` that deletes the stored object in `transaction.on_commit`. A new document-version model needs the same receiver. This is the one pattern to extract: a shared helper, or a receiver connected to each file-owning model, so a row delete always takes the object with it.

**Callable without copying, from outside a sitting:**
- `validate_and_sanitise` as is.
- `get_user_uploads_storage` as is.
- The streaming body, after the small widening above.
- The "delete the object when the row goes" receiver, as a shared helper.

Needs new code: the model (one row per version, FK to the requirement), its `upload_to`, the owner and reviewer access checks, the view.

## 2. Other upload code

- **Panel framework file-upload actions** (`spec_dd/3. done/2026-11-19_06:14_learner-profile-use-panels-framework-1-file-upload-actions/1. spec.md`). `FormPanelAction` gets `request.FILES`, multipart attributes, `PanelClearableFileInput` (`freedom_ls/panel_framework/widgets.py`), a choose-again message after a 422, and the "Uploading…" label. It explicitly leaves storage, size limits and type checks to the host form and model, and imports no FLS app. It is a UI path an educator-side or applicant-side panel could use: a `FormPanelAction` whose form's `clean_<field>` calls `validate_and_sanitise`. It is not a storage or validation layer. The applicant requirements page is not obviously a panel page, so the standalone upload view may be plain HTMX like the form file widget (`form_engine/inputs/file_upload.html`).
- **Profile pictures** (`freedom_ls/accounts/models.py`, `forms.py`, `images.py`, `validators.py`). Alias `profile_pictures`, key `profile_pictures/{user_pk}/{uuid}.webp`, a separate Pillow validator and encoder (`validate_profile_picture`, `encode_profile_picture`). Image-only, WebP. The form deletes the superseded object under a row lock. Different rules (no PDF), so not a match for documents. It shares `freedom_ls/base/images.py` with `form_engine/uploads.py`, which is the existing sign that image safety helpers live in `base`.
- **Organisation logo** (`freedom_ls/organisations/models.py`, `validators.py`): public alias, stable key, overwrite. Not relevant except as the counter-example in the `file-storage` skill.
- **`GeneratedReport.file`** (`freedom_ls/reports/models.py`): alias `reports`. Generated, not user-supplied.
- **Certificates** (`spec_dd/1. next/learner-public-profile-4-certificates/idea.md`, not yet a spec). It wants PDF or image with the same untrusted-upload checks ("following the pattern of the existing image and logo checks"), a uuid key, and removal that removes the stored file. It lists the storage alias as open (`certificates` is public, `user_uploads` private) and sets malware scanning aside, leaving only "a place for it". It is a second consumer of document-style upload validation. If both specs want PDF/JPEG/PNG with 6 MB, `validate_and_sanitise` should move from `form_engine` to a neutral place (`base`, beside `images.py`) when the second consumer lands, or `form_engine` stays the owner and both import it. The idea says "reused, not copied", so the decision is where it lives, not whether to share. Recommend: leave it in `form_engine` for the first consumer and import it from there; moving it is a rename-only change that can come with certificates.

## 3. Erasure and retention

`freedom_ls/course_applications/erasure.py` has one function, `erase_anonymous_applicant(applicant)`: refuses a claimed applicant (`claimed_at` set, `ValueError`), otherwise `applicant.delete()`. The cascade does the rest:
- `AnonymousApplicant` -> `CourseApplication` (`OneToOneField`, `CASCADE`, `models.py`).
- `CourseApplication.form_progress` is `RESTRICT`, so the sitting does not cascade. `erase_the_sitting_nobody_owns` (`course_applications/receivers.py`, `post_delete` on `CourseApplication`) deletes the user-less `FormProgress` explicitly, which cascades to `QuestionAnswer`, `QuestionAnswerFile` and, through `delete_question_answer_file`, the stored object. A sitting with a user is not touched there ("reachable through that user").
- `erase_unclaimed_applicants_with_the_users_address` (`pre_delete` on `User`) erases unclaimed applicants that applied with the user's address.
- A deleted `User` cascades to `CourseApplication` (`user`, `CASCADE`) and to `AnonymousApplicant.user` (`CASCADE`). The sitting's `FormProgress.user` is also user-keyed, so form files go with the user via `FormProgress`.

There is no time-based retention. The `simple-application-forms` idea lists "a retention scheduler" as out of scope (`spec_dd/3. done/2026-09-10_09:45_simple-application-forms/idea.md`). Erasure is event-driven only: delete the user, or an admin or shell calls `erase_anonymous_applicant`.

**What new upload records must join:**
1. A document-version row FK'd to the requirement, which cascades from the requirement, which cascades from `CourseApplication`. Then the existing `AnonymousApplicant.delete()` and user-delete paths reach it with no change to `erasure.py`.
2. The stored object needs its own `post_delete` receiver with `on_commit` (see section 1). Without it, deleting an application leaves the scan of a licence or medical in the bucket. `user_uploads` is the bucket the skill says must be sweepable by owner prefix.
3. Superseded requirements and every earlier version are kept by design, so nothing is deleted on supersede. Erasure must therefore cascade through superseded requirements too. A model that soft-hides rows must not be filtered out of the cascade (any manager that filters hidden rows must not be the cascade path; Django cascades use `_base_manager`, so this is fine as long as nothing uses `on_delete=DO_NOTHING` or `PROTECT`).
4. Key prefix: anonymous applicants have no user id. The form path uses `user_uploads/anonymous/{form_progress pk}/…` and keeps that key after a claim (deletion is row-driven). The document path needs the same split, keyed on the application pk for anonymous ones. Keying on `CourseApplication.pk` for both is simpler but breaks the skill's "prefixed by the owning user" rule for signed-in applicants.
5. The test for erasure is `freedom_ls/course_applications/tests/test_erasure.py`; a document case belongs there.
6. A claimed applicant refuses erasure here. The document rows hang off the application, so they follow the user-delete path.

The idea says medical and identity documents get "the same storage, retention and access rules", so no extra retention here either.

## 4. Anonymous applicants

Yes, an unclaimed applicant can upload through the form sitting. The sitting has `user = None`. The ownership check is `owned_form_progress(request)` in `freedom_ls/form_engine/session_access.py`: a signed-in user gets `FormProgress.filter(user=request.user)`; an anonymous request gets `user__isnull=True, completed_time__isnull=True, pk__in=<pks held in the session under form_engine_anonymous_form_progress>`. `allow_anonymous_form_progress` writes the pk when the sitting is created, `forget_all_anonymous_form_progress` clears the list when the session gains a user.

Consequences for upload requirements:
- The anonymous grant is the session only (the browser that started the sitting) and it lapses when the sitting is completed (`completed_time__isnull=True`). So an anonymous applicant can upload and download while the form is open, and loses access to it, including downloading their own file, once they submit. The upload view returns 409 for a completed sitting.
- Any document uploaded weeks after the form is finished must therefore be a signed-in applicant. The claim flow (`freedom_ls/course_applications/claims.py`: claim token, `attach_to_user`, `convert_attached_application`) is what makes an anonymous applicant a user. The applicant sees "one page listing their requirements" over weeks, which is not workable for the session-only grant. The idea does not say if upload requirements are open to unclaimed applicants. Recommend the spec decide: upload requirements need a claimed application (the user exists, signed in). If anonymous document upload is wanted, the access check needs a new grant: the claim token or a per-application session grant, which is a bigger design than the form's.
- Note `remembered_anonymous_applicants(request)` and `application_of` in `course_applications` track anonymous applicants in the session separately from `form_engine`'s list.
- Files of an anonymous sitting are keyed `user_uploads/anonymous/{sitting pk}/…`. They are protected only by being reachable through the owner lookup, with no URL secrecy.

## 5. `file-scanning`

- There is no `file-scanning` directory anywhere under `spec_dd/` (glob finds none). Other documents refer to `spec_dd/1. next/file-scanning/1. spec.md` and `0. idea.md` as if they existed, and call it "parked in next" or "ready". Treat it as missing or moved. Do not link to a path that does not exist.
- `spec_dd/corporate-readiness/README.md`: named in the list "`file-scanning`, `content_snapshots` and `compliance-form-randomization`", described as what a compliance auditor asks about ("is uploaded content safe"). Under item 5 "Pull forward the planned security items" it is one of four items (enforce CSP, fix the educator-interface authorisation gap, land `file-scanning`, route media downloads through the access check), "individually small", together the answers to SIG or CAIQ questionnaires.
- Other mentions: `learner-public-profile-4-certificates` leaves "a place for it". `simple-application-forms` says the spec "owns the whole question" and had code that was parked; research there designed `scan_status`, ClamAV and a `@task` by row id with `transaction.on_commit` plus a housekeeping sweep (`spec_dd/1. next/learner-interface-features-5-protected-video/research_video_infrastructure.md` summarises it, including "do not ship a seam with nothing real behind it; a safe default must clear nothing", and a `FILE_SCAN_BACKEND` that was removed).
- In code: no scanning hook exists. `freedom_ls/form_engine/migrations/0003_remove_questionanswerfile_scan_status.py` removed the `scan_status` column that an earlier version of the model had. No `FILE_SCAN_BACKEND`, no clamd use, no quarantine in `freedom_ls/`. Format sniffing and re-encoding in `uploads.py` is the only defence today.
- The idea says scanning "should land before a deployment takes medical or identity documents in production". For spec 4 that means: leave no hook that pretends to scan, and keep the design amenable (a document version row can gain a status column later; the download route is the single gate where a quarantine check would sit, as `course-applications-admin/idea.md` already notes for the admin route).

## 6. Where "document type" could live

Precedents:
- Deployment-named classes by dotted setting with loader, boot check and conformance tests: `MESSAGING_POLICY` (`freedom_ls/comms/messaging_loader.py`, `checks.py`, `MessagingDecision` in `messaging_policy.py`) and `COURSE_ACCESS_BACKEND` (`freedom_ls/content_engine/models/courses.py`). The idea's requirement resolver follows this.
- `freedom_ls/accounts/registration_forms.py` resolves deployment-defined form classes by `import_string` from a setting.
- A document type is a registry of Python objects, not a single class chosen by one setting. A setting that names a module or a list of dotted paths, loaded once with a boot-time check, fits. The registry needs a stable string key because that key is stored on the requirement row and is what content refers to.

**A document type minimally needs:**
- A stable key (slug), stored on the requirement.
- A label for the applicant and the reviewer.
- A description, authorable in content (the idea's rule: "document type descriptions" are content). Content must refer to the key. FLS must handle a key content names that Python does not define (boot or content-load check). The content side would live with the course's access configuration ("fixed list of requirements" in the idea), so the schema work is in `content_engine`/`content_base`, not here.
- The rejection reasons it allows (per document type, in Python, next to the resolver; FLS ships a generic set). Each reason: key, reviewer label, applicant explanation.
- Optional later, not needed in the first cut: allowed types and size overrides, a validity or expiry rule. Do not add them now (project rule: do not build what was not asked). Since the validator has fixed limits, a type's `accept` would be unenforceable without a change to `uploads.py`.

The per-type descriptions being content and the keys and reasons being Python is exactly the idea's content-versus-Python rule.

## 7. Size

Is "upload requirements + version history + applicant history view + reviewer seeing versions" one PR? No, and it depends on the requirement model.

Dependencies:
- The upload is "one thing an applicant provides for one requirement", so a requirement row (status: outstanding, submitted, accepted, turned down, superseded), the resolver run after each event, and the applicant requirements page must exist first (spec 3 in the idea's order). An upload requirement is a kind of requirement; a version is a child of it.
- "The reason each was not accepted" and "the reviewer sees versions" need the reviewer verdict with a rejection reason and the reviewer's UI (spec 1 and the verdict part of spec 4 itself). The idea puts rejection reasons, choices and upload history together in spec 4, and that is already large.
- Reviewer download needs an organisation-role access check, which depends on spec 1 (organisation roles). The form path's `view_questionanswerfile` permission and "superuser" docs do not cover it.

Pieces, in build order, each small enough for a PR on its own:
1. Document version model, `upload_to`, delete receiver, widened streaming helper, erasure test. Tests of validation reuse. (Medium, no UI.)
2. Applicant upload view on a requirement, rate limit, owner check, re-upload creating a new version and moving the requirement to submitted, the resolver run after the event. (Medium.)
3. Applicant page: current document and collapsed history with reasons. Needs rejection reasons from the verdict model. (Medium.)
4. Reviewer view of versions and download. Needs the organisation-role access check. (Medium.)
5. Document type registry, with generic rejection reasons and the boot check. Needed by 3 and 4 for the reason labels and by the verdict. (Small to medium; can come first.)

Suggested cut: the registry and the verdict reasons come with the requirement spec or as an early slice of spec 4. Model plus upload plus applicant history is one PR (items 1 to 3). The reviewer UI waits for, or lands with, `application-review-ui`. Keeping all five together would be a large PR with three apps touched (`form_engine` helper widening, the new requirement app code, the educator interface). The one thing that cannot move out is item 1's delete receiver and erasure test: a version table without them leaks files.

## Open questions for the spec

- May an unclaimed applicant work on upload requirements? Today's session grant lapses on completion. Recommend: no, require a claimed account.
- Where does `validate_and_sanitise` live once certificates become a second consumer?
- Key prefix for document files: user id (matches the skill) versus application pk (works for anonymous).
- The `file-scanning` spec directory is missing even though several documents point at it.

Sources: files named above in the repository only. No web sources.

status: ok
