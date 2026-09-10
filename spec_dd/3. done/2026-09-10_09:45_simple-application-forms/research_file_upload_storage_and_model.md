# Research: where the bytes live, and what model change carries a file answer

Scope: the storage alias and key for an application's ID/passport upload, the model shape that
carries it, the `QuestionType` ripple, the `save_answers` blank-deletes-the-row hazard a file input
walks straight into, the deletion chain, and where per-question upload limits are configured. Decisions
1–7 from the prompt are treated as settled and not re-argued.

## 1. Alias and key

**Alias: `user_uploads`.** Walking `claude_plugins/fls-dev/skills/file-storage/SKILL.md`'s two-step
test: (1) does the file need to be readable without logging in — no, only a superuser reviewing an
application in Django admin ever reads it; that rules out the public bucket. (2) who supplies the
bytes, does it identify a person, can it be regenerated — the applicant supplies it, it is literally a
photo ID, and it cannot be regenerated from anything else FLS holds. That is exactly the skill's
description of `user_uploads`, not `reports` (machine-generated, regenerable) and not `course_media`
(author-supplied, no personal data). `user_uploads` is also the alias the skill already names as
carrying "no consumer yet" (`SKILL.md`'s alias table) — this is that alias's first consumer.

**Key shape:**

```
user_uploads/{user.pk}/course_applications/{question_answer_file.pk}{ext}
```

Three requirements, three segments:

- `user_uploads/` — the alias's own namespace, disjoint from `reports/`'s `cohort_reports/` prefix,
  per the skill's "namespace your `upload_to`" rule. Both aliases share the user-data bucket, so a bare
  prefix either could produce is exactly what that rule forbids.
- `{user.pk}/` — the forward-looking erasure rule, applied literally: "every object under
  `user_uploads/` must be prefixed by the uploading user, so a right-to-erasure request becomes a
  scoped delete." The uploading user is `form_progress.user` (the applicant), reached via
  `question_answer_file.answer.form_progress.user`, never anything read from the request. Note this
  segment is *meant* to be predictable from the user — that is the entire point, it is what lets a
  future erasure job list-and-delete everything under one prefix without a database join. `User.pk` is
  a small sequential integer by design (`accounts/models.py:69-71`: "User is the one object whose
  identity appears in a URL as a small sequential number"), so this segment is guessable — deliberately,
  and safely, because it names a *scope*, not an *object*, and the bucket is private with signed URLs
  (`SIGNED_URL_PURPOSES` includes `USER_UPLOADS_PURPOSE`, `deployment/storage.py:29`; enforced by
  `check_private_media_aliases_sign_their_urls`, `deployment/checks.py:281-321`). Guessing the prefix
  gets you a folder name, not a readable object.
- `course_applications/{question_answer_file.pk}{ext}` — the leaf, which *is* the access-control-
  relevant part and must not be guessable, mirroring why `report_upload_path` keys on the report's own
  pk rather than the cohort name (`reports/models.py:25-34`: "the pk is a uuid4, so it alone makes the
  name unique... nothing user-facing reads this name"). `question_answer_file.pk` is a `SiteAwareModel`
  UUID (§2), so it carries the same guarantee. It must not be derived from the original filename for the
  same reason `organisation_logo_upload_to` never interpolates one (`organisations/models.py:20-32`):
  a filename is attacker-controlled, can carry `../` segments, and two applicants naming their scan
  `id.pdf` would collide if the key were filename-derived. `course_applications/` is an inner
  sub-namespace, not required by the skill but cheap insurance — a later second consumer of
  `user_uploads` (a profile picture, say) then can't collide with this one inside the same user's
  prefix.

**Overwrite: no `_OVERWRITE_PURPOSES` entry.** Decision 7 ("replacing an upload deletes the old
object") sounds like it wants overwrite semantics, but it does not, for the reason the skill spells
out for `Organisation.logo`: `_OVERWRITE_PURPOSES` is a *per-alias* setting (`_alias_entry`,
`deployment/storage.py:104-137`), and `user_uploads` has no consumer of its own yet besides this one —
turning overwrite on for the whole alias to suit one field is precisely what the skill forbids ("Do not
add an existing purpose to that set to suit one field: it changes the guarantee for every other field
on that alias"). It is also unnecessary: a *replace* here means re-saving the **same**
`QuestionAnswerFile` row with a new `file` (§2), so the key is stable except for `{ext}` — exactly the
shape the skill warns about ("a stable key whose extension can change writes a second object unless the
model deletes the one it superseded"). The fix is `Organisation.save()`'s pattern, not
`file_overwrite=True`: capture the previously-stored file name before `super().save()`, save, then
`current.storage.delete(previous)` if the name changed (`organisations/models.py:116-135`). Concretely,
`QuestionAnswerFile.save()` needs the same superseded-object sweep `Organisation.save()` already does,
scoped to its one `file` field.

The one place a real object-storage cost has to be named directly: `form_engine` has never before had a
`FileField`, a private bucket, or a superseded-object sweep. Whichever model gets it (§2) is where that
operational surface — storage aliasing, signed URLs, delete-on-replace — enters `form_engine` for the
first time.

## 2. Where the file hangs

**Recommendation: a new child model in `form_engine`, `QuestionAnswerFile`, in a `OneToOneField` to
`QuestionAnswer` (`on_delete=models.CASCADE`).** Not a `FileField` directly on `QuestionAnswer`, and not
a `course_applications`-owned table.

**Why not a bare `FileField` on `QuestionAnswer`:** `QuestionAnswer` (`form_engine/models.py:572-593`)
is one row per `(form_progress, question)`, shared by every quiz, survey and now application answer in
the system. A file answer needs more than one column to be safe: the `FileField` itself, the original
filename (kept for display since the key deliberately discards it, §1), and the quarantine state
(decision 5 — `scan_status`, below). That is three-to-four columns landing on a hot, shared table that
is `NULL` for every non-file row it will ever hold — today 100% of them, and likely close to that
forever, since most questions are text or choice. A dedicated child model keeps `QuestionAnswer` exactly
as wide as it is today for every quiz and survey, and confines the new object-storage machinery (§1) to
a table that only exists where a `FILE_UPLOAD` question is actually answered.

**Why not a `course_applications`-owned table (the June research's `ApplicationFile`):** decision 1 is
that answers live in `FormProgress`/`QuestionAnswer`, full stop — "no parallel application-question
family." A file **is** an answer to a `FormQuestion`; routing it to a `course_applications` table would
mean one of a `QuestionAnswer`'s siblings is reachable through `form_engine` and the other only through
`course_applications`, which is exactly the fork decision 1 exists to prevent. It would also require
`FormQuestion` — a `form_engine` model — to somehow resolve where an application stores its file, which
is an edge from `form_engine` to `course_applications` that idea.md is explicit does not exist ("`
form_engine` gains none, so the graph stays acyclic"). Keeping the file inside `form_engine` is not a
style preference here; it is forced by the two decisions already made.

**The crux, answered directly: yes, a file-upload question type means `form_engine` grows a file
concept, and yes, that is consistent with "some forms are just forms."** The same shape decision 2
already established for `UNSCORED` applies here without alteration: `FormStrategy.UNSCORED` is a
property of the *form* ("an unscored form is a form nobody scores; an application form is one use of
that"); `QuestionType.FILE_UPLOAD` is a property of the *question* ("a file-upload question is a
question `form_engine` can render and store an answer for; an ID-scan question is one use of that"). A
plain survey asking "upload a photo of your finished project" is exactly as legitimate a `FILE_UPLOAD`
question as an ID scan is, and needs none of `course_applications`. Nothing about the type is
application-shaped; `CourseApplication` remains the only thing that knows it is looking at an
application's answers, exactly as decision 2 requires.

**What it costs, named plainly:** `form_engine` — an app that today has zero object-storage
dependencies, no private bucket, no quarantine state, and no per-user data-erasure surface — gains all
four, permanently, for every deployment that uses it, whether or not that deployment ever builds a
file-upload question. That is a real, load-bearing widening of what "extract `form_engine`" (August
2026) bought: the extraction spec's whole justification was avoiding a duplicated `Form → FormPage →
FormQuestion → QuestionOption` family; this spec now also hands the extracted app a duplicated-nowhere
storage responsibility it did not have before. It is the right place for it (the alternative forks the
answer family the extraction was built to prevent), but it is not free, and nothing about the reuse
decision made this file-shaped growth cheaper than building it fresh would have been — the saving in
this feature is entirely on the question/answer/paging side, not on the storage side, where there was
nothing to reuse.

`QuestionAnswerFile` fields, sketched:

```python
class ScanStatus(models.TextChoices):
    PENDING = "pending", _("Pending scan")
    CLEAN = "clean", _("Clean")
    INFECTED = "infected", _("Infected")

class QuestionAnswerFile(SiteAwareModel, TimestampedModel):
    answer = models.OneToOneField(QuestionAnswer, on_delete=models.CASCADE, related_name="file_answer")
    file = models.FileField(upload_to=question_answer_file_upload_to, storage=get_user_uploads_storage)
    original_filename = models.CharField(max_length=255)
    scan_status = models.CharField(max_length=20, choices=ScanStatus.choices, default=ScanStatus.PENDING)
```

`scan_status` is new vocabulary — FLS has no existing quarantine field to reuse — and it is deliberately
inert: nothing ships that ever transitions it away from `PENDING` (decision 5, "FLS ships the state and
the seam, and no scanner"). The seam only means something if something reads it: the Django admin's
rendering of `QuestionAnswerFile` must not surface a link (signed URL or otherwise) unless
`scan_status == CLEAN` — showing the metadata (filename, size, uploaded-at) but withholding the object
itself while `PENDING`. Without that one check, `scan_status` is a decorative column; with it, a
deployment that never wires a scanner has correctly built itself a permanently-unreadable-but-safely-
retained upload, which is the honest consequence of shipping the seam without the scanner, not a bug in
it.

## 3. The `QuestionType` addition

New member: `FILE_UPLOAD = "file_upload"`. Unlike `NUMBER` (which joined `FREE_TEXT_QUESTION_TYPES` and
rode the existing text/options switch for free — see `research_question_types_and_validation.md` §2),
**`FILE_UPLOAD` fits neither storage slot on `QuestionAnswer`** and cannot join that frozenset. It needs
its own third branch everywhere that frozenset is the switch between "write `text_answer`" and "write
`selected_options`" — and a second, narrower frozenset everywhere the question is really "does this
question have a `correct` option to score against," where `FILE_UPLOAD` behaves like free text (no) but
must not be reached by the same membership test that decides where to write it.

| Site | Today | What changes for `FILE_UPLOAD` |
| --- | --- | --- |
| `FREE_TEXT_QUESTION_TYPES` (`enums.py:22`) | `{SHORT_TEXT, LONG_TEXT}` | `FILE_UPLOAD` does **not** join. It needs a third storage branch, not membership in the text/options switch. |
| `has_submitted_answer` (`submissions.py:23-32`) | Checks `post_data` only, branches on the frozenset | Needs a `files: MultiValueDict` parameter and a third branch for `FILE_UPLOAD` — see §4, this is also where the blank-deletion hazard lives. |
| `submitted_text_answer` / `submitted_option_ids` (`submissions.py:13-20`) | Two extraction functions, one per storage slot | A third, `submitted_file(question, files)`, reading `files.get(f"question_{question.id}")`. |
| `save_answers` (`models.py:290-311`) | Two-way `if question.type in FREE_TEXT_QUESTION_TYPES` | Needs a third branch and a `files` parameter threaded in from every caller (`learner_interface/views.py:1106` and `:1439`). See §4 for why the "no answer" branch cannot be reused as-is. |
| `get_incorrect_quiz_answers` (`models.py:505-569`) | Skips scoring when `question.type in FREE_TEXT_QUESTION_TYPES` (`:537`) | Must also skip `FILE_UPLOAD` — a file question has no `correct` option, so without this it falls through to the options-comparison branch and is reported as an always-wrong multiple-choice question with no selected or correct options to show. |
| `score_category_value_sum` (`models.py:324-450`) | Only processes `question.type == "multiple_choice"` (`:348`), an allowlist not an exclusion | Already safe — `FILE_UPLOAD` is excluded by never matching, no change needed. Worth noting as the one site that was already written defensively. |
| `reports/indexes.py` `build_sat_questions` (`:557-564`) and `index_distractors` (`:620-632`) | Both exclude `question.type in FREE_TEXT_QUESTION_TYPES` | Same gap as `get_incorrect_quiz_answers`: a `FILE_UPLOAD` question placed in a `QUIZ`-strategy form (a narrow, authoring-mistake case, not the application path, which uses `UNSCORED`) would otherwise be scored as an empty multiple-choice question. |
| pydantic `FormQuestion` / `QuestionType` (`schema.py:13-19`, `:105-139`) | Four-member `StrEnum`, no file-specific fields | Add `FILE_UPLOAD = "file_upload"`, plus the two config fields from §6, with a `model_validator` requiring them only when `type == FILE_UPLOAD` (mirroring `Form.validate_quiz_fields`, `schema.py:51-74`). |
| `course_form_page.html` (`:128-142`, form input partials at `:38-105`) | Explicit `{% elif question.type == "..." %}` ladder, falls into `ERROR! UNHANDLED FORM TYPE` otherwise | New `form-input-file-upload` partial (`<input type="file">`) and a new branch. **Also**: the enclosing `<form id="runner-page-form" method="post" ...>` (`:422`) carries no `enctype`, so it defaults to `application/x-www-form-urlencoded` — a file chosen in that form today would not upload at all. Adding `enctype="multipart/form-data"` to that tag is a required, easy-to-miss part of this change. |

Recommend introducing the second frozenset explicitly rather than special-casing three call sites
individually:

```python
# enums.py
UNSCORABLE_QUESTION_TYPES = FREE_TEXT_QUESTION_TYPES | frozenset({QuestionType.FILE_UPLOAD})
```

`get_incorrect_quiz_answers`, `build_sat_questions`, and `index_distractors` switch to
`UNSCORABLE_QUESTION_TYPES`; `has_submitted_answer`, `submitted_text_answer`, and `save_answers` keep
reading `FREE_TEXT_QUESTION_TYPES` as the storage-slot switch and gain an explicit third branch for
`FILE_UPLOAD` rather than folding it into either set. Two frozensets answering two different questions
("what column does this write" vs. "can this be scored") is a smaller, more honest change than stretching
one frozenset to answer both, which is exactly the trap `FILE_UPLOAD` would fall into if it were folded
into `FREE_TEXT_QUESTION_TYPES` for convenience.

## 4. The blank-deletes-the-row hazard — the most important finding here

**The exact path.** `form_fill_page` (`learner_interface/views.py:1087-1121`) always calls, on every
page POST:

```python
form_progress.save_answers(questions, request.POST)      # views.py:1106 — request.POST only, no request.FILES
```

Inside `save_answers` (`form_engine/models.py:290-311`):

```python
for question in questions:
    if not has_submitted_answer(question, post_data):
        self.answers.filter(question=question).delete()
        continue
    ...
```

`has_submitted_answer` (`submissions.py:23-32`) today only ever consults `post_data`. An `<input
type="file">` **never re-submits its previous value** — no browser prefills a file input from a prior
page load, on privacy grounds, full stop. So the very first time an applicant returns to a page
carrying an already-answered `FILE_UPLOAD` question — resuming tomorrow, clicking Back then Next again,
or the runner's own resume redirect landing them there (the "resume walks backward" defect idea.md
already names, `idea.md`: "Defects this work sits on top of") — and re-POSTs that page **without
re-selecting the file**, `request.FILES` (once threaded in, §3) carries nothing for that question,
`has_submitted_answer` returns `False`, and `save_answers` runs `self.answers.filter(question=question)
.delete()` — silently deleting the row holding the already-uploaded ID scan, and (via the `OneToOneField`
`CASCADE` from `QuestionAnswer` to `QuestionAnswerFile`, §2) the file record with it. The bytes in the
bucket are then orphaned (§5) and the applicant has no visible reason their upload vanished.

A second, independent call site hits the same code with the same shape: `_save_posted_page_answers`
(`learner_interface/views.py:1418-1439`), used by the "leaving will submit and save" exit path, calls
`form_progress.save_answers(page_questions(...), post_data)` on whatever page the applicant was standing
on when they chose to leave — again with no special handling for a question whose answer does not travel
in `post_data`/`request.FILES` unless freshly chosen in that exact page load.

**What has to change, precisely, so this cannot happen:**

1. `has_submitted_answer` needs a `files` parameter and, for `FILE_UPLOAD`, must not be answerable from
   `post_data`/`files` alone — "submitted" for a file question is `bool(files.get(...))`, but "already
   answered, still valid" is a **separate** question this function cannot answer, because it has no
   database access and is a pure function of the POST body (`submissions.py`'s own docstring: "kept free
   of model imports").
2. `save_answers`'s per-question loop therefore needs a **third outcome** for `FILE_UPLOAD`, not the
   binary "has an answer / delete the row" it runs today:
   - a new file is present in `files` → replace it (delete the superseded object per §1, write the new
     one);
   - no new file, and no existing `QuestionAnswerFile` for this `(form_progress, question)` → genuinely
     blank, behave exactly as today (delete-if-present is a no-op, `required` still flags it upstream);
   - no new file, but an existing `QuestionAnswerFile` **is** present → do nothing. Leave the row and the
     file untouched. This is the branch that does not exist today and is the entire fix.
3. The required-answers check in `form_fill_page` (`views.py:1098-1101`,
   `question.required and not has_submitted_answer(question, request.POST)`) has the identical blind
   spot one level up: an already-answered required file question with no new upload in this POST must
   not be reported as unanswered either, or a returning applicant would be told to re-upload a document
   they already provided, every single time they touch that page. This needs the same "check existing
   state, not just this POST" fix, sourced from `form_progress.existing_answers_dict(questions)`
   (`models.py:274-288`), which the view already computes for the GET path and would need computing
   ahead of the POST branch too.

None of this is exotic — it is the direct, mechanical consequence of `<input type="file">`'s browser
behaviour meeting a save routine whose entire contract is "no answer in this POST means delete the
answer," written for input types that always resubmit whatever they last held. Skipping this fix does
not fail loudly; it fails by quietly destroying evidence an applicant believes they already gave, on the
most ordinary possible action (leaving and coming back, or the page order defect idea.md already flags).

## 5. Deletion chain

**Django does not delete storage objects when a row is deleted — confirmed, and nothing in the current
codebase does this automatically for a brand-new file field.** `Organisation.save()`
(`organisations/models.py:116-135`) only cleans up a *superseded* object on save, not a deleted row.
The one precedent that does clean up on delete is `reports/signals.py:15-27`:

```python
@receiver(post_delete, sender=GeneratedReport)
def delete_report_file(sender, instance, **kwargs):
    if not instance.file:
        return
    instance.file.delete(save=False)
```

`QuestionAnswerFile` needs the identical pattern: a `post_delete` receiver that calls
`instance.file.delete(save=False)`. Django's deletion collector instantiates every row a cascade will
touch (that is how `pre_delete`/`post_delete` signals fire per-object even when the delete originates
several FKs away — a `User.delete()` cascading down through `FormProgress` → `QuestionAnswer` →
`QuestionAnswerFile` still fires this receiver for each `QuestionAnswerFile` row it removes), so one
receiver at the bottom of the chain is sufficient; nothing further up needs its own cleanup logic.

**The chain, traced:**

- `User → FormProgress`: `CASCADE` (`form_engine/models.py:205-207`).
- `FormProgress → QuestionAnswer`: `CASCADE` (`:575-577`).
- `QuestionAnswer → QuestionAnswerFile` (new): `CASCADE`, via the `OneToOneField` on the child.
- Deleting a `User` therefore cascades all the way to the file row and — once the `post_delete` receiver
  above exists — all the way to the object in the bucket. This is what makes the erasure rule in §1 real:
  because the key is prefixed `user_uploads/{user.pk}/...`, a scoped delete is possible either by
  deleting the `User` (which cascades correctly) or by deleting the prefix directly against the bucket
  API for a narrower erasure that does not touch the account.
- `CourseApplication → User`: `CASCADE` (`course_applications/models.py:32-36`); `CourseApplication → Form`:
  resolved once at creation, not `on_delete`-relevant here. Nothing points **up** from
  `QuestionAnswerFile` toward `CourseApplication` or its (not-yet-built) review record — Django cascades
  flow only from the referenced row toward the rows referencing it, never the reverse. So the risk decision
  6 names — "deleting the ID scan must leave the application and its review record intact" — is not a
  live hazard in the FK graph as it stands; it would only become one if a future review-record model were
  given a `CASCADE` FK *pointing into* `QuestionAnswerFile`, which nothing here proposes and which
  `research_application_pii.md` §4's `SET_NULL` recommendation for `CourseApplication.form_progress`
  already guards against at the layer above. The concrete instruction this leaves for implementation is
  narrower than "get the FK right": **a "delete this upload" action must be implemented as
  `question_answer_file.delete()`, never as a shortcut that deletes or touches `CourseApplication` or
  `FormProgress` to get there** — the FK graph makes the safe version trivial and the unsafe version is
  simply not the natural thing to reach for.

## 6. Per-question upload configuration

**On `FormQuestion`, not settings.** A size cap or type allowlist that lived in Django settings would be
one number/list for every `FILE_UPLOAD` question in the entire deployment — wrong the moment a course
wants a 2MB passport photo and another wants a 15MB scanned PDF of a longer document. This is a property
of the *question*, the same place `required` already lives (`FormQuestion.required`, `models.py:145`),
not a property of the deployment. Two new fields, required only when `type == FILE_UPLOAD`:

```python
# form_engine/models.py — FormQuestion
allowed_upload_extensions = models.JSONField(blank=True, null=True)  # e.g. ["pdf", "jpg", "jpeg", "png"]
max_upload_size_mb = models.PositiveSmallIntegerField(blank=True, null=True)
```

```python
# form_engine/schema.py — pydantic FormQuestion
allowed_upload_extensions: list[str] | None = Field(
    None, description="Required if type is file_upload. Lower-case extensions without the dot."
)
max_upload_size_mb: int | None = Field(
    None, description="Required if type is file_upload. Maximum upload size in megabytes."
)
```

with a `model_validator` requiring both when `type == FILE_UPLOAD` and forbidding both otherwise —
exactly `Form.validate_quiz_fields`'s shape (`schema.py:51-74`), applied to a question instead of a
form. Enforcement of the limit itself (rejecting a wrong-extension or oversized upload) is a view-level
check, following the precedent `research_question_types_and_validation.md` §4 already set for
per-question validation: "not the pydantic schema (validates the author's YAML, not a learner's
submission), and not the model" — a static `FileExtensionValidator` can't vary per question, so the
check reads `question.allowed_upload_extensions`/`question.max_upload_size_mb` at submission time in the
runner view, alongside the existing `required` check, returning the same 422-and-re-render the missing-
required-answer path already uses.

Author-facing YAML, in the `demo_content` format used throughout
`research_question_types_and_validation.md` §6:

```yaml
question: Please upload a scan or clear photo of your ID book, ID card, or passport photo page.
type: file_upload
required: true
allowed_upload_extensions: [pdf, jpg, jpeg, png]
max_upload_size_mb: 10
uuid: 6f1a2b3c-0000-4000-8000-000000000090
```

status: ok
