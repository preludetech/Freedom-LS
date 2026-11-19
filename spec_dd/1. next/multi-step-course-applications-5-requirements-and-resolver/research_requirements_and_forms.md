# Research: requirements, the resolver seam, and form sittings

Read-only codebase research for cutting `idea.md`. Paths are relative to the repo root.

## 1. The house pattern for pluggable behaviour

Two worked examples. `COURSE_ACCESS_BACKEND` is the richer one; `MESSAGING_POLICY` is the cleaner, smaller one. A `REQUIREMENT_RESOLVER` setting would copy the `MESSAGING_POLICY` shape and add the content-validation hook from `COURSE_ACCESS_BACKEND`.

**Setting.** Each app has a `config.py` with an `AppSettings` subclass and a module-level `config` (`freedom_ls/course_access/config.py`, `freedom_ls/comms/config.py`). Both come from `freedom_ls/base/app_settings.py`. `declared_settings` maps each name to `Setting(required=True)` or `Setting(default=...)`.
- `COURSE_ACCESS_BACKEND` is `required=True`, and the unset case is reported by `required_settings_errors` (E001).
- `MESSAGING_POLICY` has a default dotted path to a shipped class.
- For the resolver, a default (the fixed-list resolver) is the better fit, so an install works out of the box. Use `Setting(default="freedom_ls.course_applications.<module>.FixedListRequirementResolver")`.
- Skill: `claude_plugins/fls-dev/skills/app-settings/SKILL.md` (overlay on `claude_plugins/django-stack/skills/app-settings/SKILL.md`). The `app_label` gotcha is that the label is the literal `freedom_ls_<app>`.

**Loader.** One `@functools.cache` function that does `import_string(config.X)` and instantiates the class (`freedom_ls/comms/messaging_loader.py`; `freedom_ls/course_access/loader.py`).
- Tests clear the cache with an autouse fixture in `freedom_ls/conftest.py`. `_clear_course_access_backend_cache` clears before and after each test. `_clear_messaging_policy_cache` also hooks `setting_changed` so `override_settings` clears it.
- A new loader needs its own fixture in that file. This is easy to forget, and the symptom is order-dependent test failures.
- The course-access loader also wraps the backend in `VisibilityEnforcingBackend(DeadlineEnforcingBackend(...))`, so no backend can skip core rules. The resolver needs the same idea only if some rule must hold for every resolver. One candidate is "an accepted requirement stays accepted". The idea puts that rule in FLS's reconcile step, not the resolver, so a wrapper is probably unnecessary.

**Base class.** A plain class, not an `abc.ABC` (the project forbids abstract bases). Methods raise `NotImplementedError`. The docstring says why: a downstream subclass that forgets a method fails on first use, not at import (`MessagingPolicy` in `freedom_ls/comms/messaging_policy.py`; `CourseAccessBackend` in `freedom_ls/course_access/backends.py`). It also has optional "many" variants with a looping default (`can_reply_many`, `get_access_many`), which matter for an inbox of applications.

**`*Decision` value.** A frozen dataclass.
- `CourseAccessDecision` is a plain bag of fields.
- `MessagingDecision` is stricter. It has `__post_init__` invariants, `allow()` and `refuse(reason)` constructors, and a `__bool__` that raises `TypeError` so callers must read `.allowed`. The refusal reasons are a `StrEnum` (`MessagingRefusal`).
- For the resolver, `RequirementDecision` would hold the wanted requirements (kind, key, title, description, form ref, document type, holds-back, optional choice group id, options). It should carry no side effects. FLS does the reconcile, because the resolver is a pure function of current data. A dataclass list of `WantedRequirement` plus an explicit `key` for identity is the natural shape.
- Identity matters. The reconcile ("create if not stored, supersede if no longer wanted, keep accepted") needs a stable key per requirement. A fixed-list resolver gets it from the content file. A downstream resolver chooses its own.

**Boot-time check.** `checks.py` registered with `@register()`, using Django check IDs `freedom_ls_<app>.E00n`.
- `freedom_ls/comms/checks.py` has E003 (the dotted path imports and is a `MessagingPolicy` subclass) and E004 (an `freedom_ls.`-prefixed path names an app that is not installed).
- `freedom_ls/course_access/checks.py` has E001 (unset), E002 (every stored `Course.access_config` validates under the active backend), and E003 (app not installed).
- Details to copy: the check skips when the app is not being checked (`_comms_not_being_checked`); it avoids importing a module from an uninstalled FLS app, because that raises `RuntimeError`, not `ImportError`; and a DB-reading check catches `DatabaseError`, `OperationalError` and `ProgrammingError` so a fresh checkout stays silent.
- A resolver check would copy E003/E004. A second check, like course_access E002, would validate every course's stored requirement list against the active resolver, so swapping resolvers surfaces bad content at boot.

**Conformance tests.** There are two layers.
- Per-contract unit tests: `freedom_ls/comms/tests/test_messaging_policy.py` (decision invariants, base methods raise), `freedom_ls/comms/tests/test_messaging_loader.py`, `freedom_ls/course_access/tests/test_loader.py`, `test_checks.py`, `test_backends.py`.
- The downstream-facing suite in `freedom_ls/contrib/conformance/`. `test_settings.py::test_configured_backend_instantiates` loads the configured backend and asserts `isinstance(backend, CourseAccessBackend)`. It skips when no consumer app is installed. A `test_configured_requirement_resolver_instantiates` would be added there, and exported from `freedom_ls/contrib/conformance/__init__.py` (`__all__`).
- The idea's "conformance tests" most likely means this: a reusable probe a downstream imports to prove its resolver honours the contract. For a resolver, a stronger probe is possible, such as "pure and idempotent: running twice on unchanged data gives the same decision". That is new work and should be sized as such.

**Content-validation hook.** Course content cannot import the resolver. `freedom_ls/content_engine/config.py` declares `COURSE_ACCESS_CONFIG_VALIDATOR` (default `None`). `freedom_ls/course_access/loader.py::validate_course_access_config` delegates to the backend's single `validate_course_config`. `content_save.py` (about line 569) resolves it with `import_string`, and `content_engine` never imports `course_access`. A requirement-list validator would reuse this hook, or add a sibling hook.

## 2. Where the fixed list lives in course content

**Today.** `Course.access_config` is an opaque JSONField (`freedom_ls/content_engine/models/courses.py`, about line 195, marked "BACKEND-PRIVATE"). Its schema field is `access_config: dict[str, Any] | None` in `freedom_ls/content_engine/schema.py` (about line 459). The demo is `demo_content/functionality_demo_application_gated/course.md`:

```yaml
access_config:
  access_type: application_gated
  application_form: ../functionality_demo_application_form/form.md
```

**Validation chain.**
- `ApplicationCourseAccessBackend.validate_course_config` (`freedom_ls/course_applications/backends.py`) holds `_ALLOWED_CONFIG_KEYS = {"access_type", "application_form"}`. It type-checks `application_form` and refuses it unless `access_type` is `application_gated`.
- The check runs at load (`content_save.py`), at boot (course_access E002), and defensively in `get_access`.
- The loader's own binding pass (`content_save.py` about lines 1238-1261) is the one place core reads an `access_config` key by name. It resolves the author's relative path to a loaded `Form` with `resolve_author_path` and `content_by_path`, and writes the `Course.application_form` FK. It writes `None` when the key is absent so deleting the line unbinds it.

**Where a requirement list goes.** In `access_config`, as a new key. A name like `requirements:` (a list) next to `application_form` is natural. The idea itself says "the course's access configuration". Each entry would have:
- `key` (stable identity)
- `kind` (`form`, `document`, `staff_verification`)
- `title` and `description`
- `form` (a path relative to `course.md`, for the form kind)
- `document_type`
- `holds_back` (`approval`, `registration`, `nothing`)

**Consequences for loading.**
- The new key has to be added to `_ALLOWED_CONFIG_KEYS`, and `validate_course_config` has to validate the entries (types, unique keys, enums). Validation has to move out of the backend, or the backend delegates to the resolver. The hook is `COURSE_ACCESS_CONFIG_VALIDATOR` today, and the backend owns the access-config slice. A fixed-list resolver reads the list, but a downstream resolver may ignore it. So decide whether the list is validated by the backend (always) or by the resolver's own `validate_course_config`. The simplest option is for the backend to validate the list's shape whenever present, since the key is in its allowed set.
- Form refs need resolving to `Form` rows, like `application_form` does. The existing binding pass is not extensible for a list. A loader pass would store resolved form ids in the stored config, or a requirement-definition model would hold them. The alternative is to keep paths in the JSON and resolve at runtime by content path, but the loader rejects missing forms today, which is the better behaviour. Expect a content_save change in `freedom_ls/content_engine/management/commands/content_save.py`. Tests for it live in `freedom_ls/content_engine/tests/management/commands/test_content_save.py`.
- Keep the `access_config` "backend-private" rule: no view or template may read it. The fixed-list resolver is the only reader, so the rule holds if the resolver is the reader.
- `application_form` today means "the one form a course asks". With requirements, the application form would be requirement number one of kind form. Decide whether `application_form` stays as the first sitting (back-compat, simplest) or becomes a requirement. See section 4.
- A demo needs a new `demo_content/` course (or an extended `functionality_demo_application_gated`), plus a test like `freedom_ls/content_engine/tests/demo_content/test_application_form.py`.

## 3. form_engine: completing, and reopening

**Model.** `FormProgress` in `freedom_ls/form_engine/models.py` (line 281):
- `completed_time` (null until complete)
- `scores` (JSON)
- `furthest_page_reached` (a forward-only high-water mark; `record_page_reached` never moves it back)
- `asked` (JSON, the frozen path, written at completion)

**`complete()`** (line 446). It is idempotent: a second call returns at once when `completed_time` is set. Inside `transaction.atomic()` it:
1. Computes `current_path(self)`.
2. Deletes the sitting's own off-path answers (cascades to files; the `QuestionAnswerFile` post_delete receiver in `freedom_ls/form_engine/receivers.py` removes the stored object on commit).
3. Sets `asked = path.as_asked()`.
4. Sets `completed_time`.
5. Scores via `self.score(path)` (scoring strategies in `scoring.py`).
6. Saves.

After the block it sends `form_attempt_completed(sender, user, form, attempt)` (`freedom_ls/form_engine/signals.py`).

**What listens to `form_attempt_completed`.** Only `learner_progress/signals.py::recalculate_course_progress_on_form_attempt`. It looks up `CourseFormAttempt` for the attempt and recalculates the course percentage. It does nothing for an attempt with no `CourseFormAttempt`, such as an application form. So course_applications does not listen to completion at all today. It reads `completed_time` derived (`CourseApplication.is_submitted`).

**Path logic.** `conditions.py`:
- `current_path(fp)` computes the path from the answers.
- `sitting_path(fp, answers=None)` returns the frozen path if `asked` is set, else the full path if completed with `asked` null (a legacy sitting), else the computed path.
- `compute_path` / `_path` / `frozen_path` / `full_path` build the branch-logic path. This is `SittingPath` with `question_ids`, `content_ids` and `numbered_pages()`.

**Who calls `complete()`.** In app code:
- `course_applications/views.py::application_check_answers` (line 844)
- `learner_interface/views.py` (lines 2079 and 2432, the quiz/survey runner)
- `learner_progress/attempts.py::finalise_stale_incomplete` (submit-on-exit)

The rest are QA helpers.

**What reopening touches.**
1. **A new `FormProgress.reopen()`.** It sets `completed_time = None`. It must also decide about `asked` and `scores`. Clearing `asked` makes `sitting_path` compute from answers again, which is what a live sitting needs. Clearing `scores` is right for a scored form, but an application form has none.
2. **Answers survive completion**, but only the on-path ones. `complete()` deleted the off-path answers. After reopening, those are gone, which is acceptable because they were never asked. If the applicant changes a gate answer, newly opened questions are blank. This is exactly how a live sitting behaves.
3. **`furthest_page_reached`** stays. It is a forward-only mark, which suits "resume where you left off". It never goes backward, and the view's resume logic (`resume_page_number` in `paging.py`) reads it. Whether to reset it is a product choice; keeping it is simpler.
4. **Re-completion.** The second `complete()` runs the whole flow again and fires `form_attempt_completed` again. Any receiver must be safe to run twice for one sitting. `recalculate_course_progress_on_form_attempt` is safe (idempotent recalculation). A receiver that treats the signal as "first submit" would not be. Add a field or signal argument, or a separate signal, so receivers can tell first completion from re-completion. The `is_submitted` property in `course_applications/models.py` is derived from `completed_time`, so a reopened accepted sitting briefly reads as a draft. That matches the idea ("puts it back to submitted" is handled by the requirement status, not the sitting).
5. **Read-only guards that check `completed_time`:**
   - `form_engine/views.py` (lines 99 and 146) refuses file attach/remove on a completed sitting.
   - `form_engine/session_access.py::owned_form_progress` (line 52) matches only `completed_time__isnull=True` for anonymous sittings. So an anonymous applicant cannot reach a completed sitting through the session at all (also `_owned_application_with_form` in `course_applications/views.py`, line 707, 404s a user-less submitted application). Reopening for an anonymous applicant is therefore a no-go until claimed, or the owner function must be widened. In practice a reopen happens after the claim link, when the application has a `user`.
   - `application_form_page` sets `read_only = form_progress.completed_time is not None`, and `application_check_answers` shows `submitted`. These would show editable again after a reopen. No change needed beyond the reopen itself.
6. **Course progress and quiz attempts** are the danger. `CourseFormAttempt` ties an attempt to a course progress record; many attempts per placement is how retakes work (`freedom_ls/learner_progress/models.py` line 254, `attempts.py` creating a new `FormProgress` per retake). A reopened quiz would let a learner edit answers after being scored, defeating retakes.

**Who decides whether reopening is allowed.** The idea says the owner. The cleanest fit with the code today:
- `FormProgress.reopen()` would be the mechanism only. It does the state change. It does not check permission, and it refuses a `FormProgress` that is not completed.
- The owner calls it, and decides first. The application views are the owner of the application sitting, and `learner_interface` is the owner of quiz sittings. A quiz sitting simply never gets a view that calls `reopen()`. No flag is needed.
- If a guard is wanted for safety (so a future quiz view cannot reopen by mistake), the owner can be asked through the existing "this sitting has a `CourseFormAttempt`" fact. The `form_engine` docs say form_engine knows nothing about courses (`FormProgress` docstring, `CourseFormAttempt` docstring), so the check must live above form_engine, not in `reopen()`.
- A weaker alternative is a field on `FormProgress` such as `reopenable`. That puts policy in the data, which the house pattern avoids. Prefer the owner-calls approach.

**Existing reopen/edit-after-submit code.** None. The grep for "reopen" and for setting `completed_time` to `None` finds nothing in app code, only tests that set `completed_time=None` through factories to build drafts. "Edit" links on the check-your-answers page (`application_check_answers`, `RETURN_TO_CHECK`) edit a draft before submit only. After submit, `application_form_page` redirects POSTs to the status page. There is no precedent, so the reopen spec is new behaviour.

## 4. How the application sitting is created and driven today

**Creation.** `_start_application` in `freedom_ls/course_applications/views.py` (line 86):
- It runs in `transaction.atomic()`.
- It does `CourseApplication.objects.get_or_create(course=..., user=... | anonymous_applicant=...)`.
- It locks the row with `select_for_update`.
- If `course.application_form` is set and `app.form_progress` is null, it creates `FormProgress(user=user, form=course.application_form)` and saves it onto `app.form_progress`.

The sitting is a draft. A course with no application form skips straight to "submitted at creation", and `is_submitted` is true when `form_progress is None`.

**Entry views.**
- `apply` handles a signed-in applicant. An existing application goes to its status page; a new one starts and redirects to `_resume_url`.
- `_anonymous_apply` / `applicant_details` handle an anonymous visitor. They create an `AnonymousApplicant` (email, name, consent evidence), start the application, and call `allow_anonymous_form_progress(request, app.form_progress)` so the session can reach the user-less sitting. Ownership is the control (`owned_applications`, `anonymous_session.py`).
- Pages: `application_form_page` (calls `sitting_path`, `off_path_landing`, `resolve_page`, `submit_page`, `page_context`, `render_form_page` from `freedom_ls/form_engine/page_flow.py`) and `application_check_answers` (the one submit point: `unanswered_required_in_form`, then `form_progress.complete()`).
- The status page (`application_status`) redirects an unfinished sitting back to its form, so it shows nothing until submit.
- File answers use the form_engine endpoints (`partial_question_file_upload`, `owned_file_question` in `freedom_ls/form_engine/views.py`), scoped by `owned_form_progress(request)`. Validation and sanitising is `freedom_ls/form_engine/uploads.py::validate_and_sanitise`. An upload requirement outside a form would reuse this and the storage, as the idea asks.

**One application, several form sittings.** Possible, but a real model change:
- `CourseApplication.form_progress` is a nullable `OneToOneField` (RESTRICT) with `related_name="course_application"`. It is read in about 94 places across 13 non-test files (`views.py` 39, `admin.py` 10, `api.py` 9, `resources.py` 9, `receivers.py` 7, `claims.py` 6, `models.py` 5).
- Readers: the API serializer `get_answers` and prefetches (`api.py`), `is_submitted` and `submitted_time` (derive from the one sitting), the dashboard panel filter (`backends.py`: `form_progress__isnull=False, form_progress__completed_time__isnull=True`), the signal receivers that touch `updated_at` through `form_progress_id=...` (`receivers.py`), `erase_the_sitting_nobody_owns` (deletes the user-less sitting on application delete), `claims.py` (attach and discard drafts), the admin and the CSV resources.
- A form requirement would own its own sitting: `ApplicationRequirement.form_progress` (nullable, one-to-one). This is additive. `CourseApplication.form_progress` can stay as the primary application form for a first PR, so every existing reader keeps working.
- The idea's reopen text says "any of their form requirements". That fits requirement-owned sittings. The cleanest cut: leave `CourseApplication.form_progress` alone in the requirements spec, treat it as "the application form", and let additional form requirements point at their own sittings. The API/status/admin then read the application form unchanged, and gain a requirements list later. Merging the primary sitting into the requirements model (so there is one path) is a cleanup that can follow, and is a risky migration (data move and RESTRICT FK).
- Anonymous applicants. A second sitting needs `allow_anonymous_form_progress` for each, and the session only reaches a draft (`owned_form_progress` requires `completed_time__isnull=True` for user-less sittings). A requirement form that is completed and then reopened is unreachable for an anonymous applicant until they claim. Requirements are probably authenticated-only after the claim, but this has to be said in the spec. Anything on the requirements page for an unverified applicant is a decision for the specs, not an accident.
- The one-per-course unique constraint is on (site, user, course), unaffected.

## 5. Where "re-run the resolver after every event" hooks in

**Signals that exist now** (`course_applications/receivers.py`, connected in `apps.py` `ready()`):
- `post_save` on `FormProgress`, `post_save`/`post_delete` on `QuestionAnswer`, and on `QuestionAnswerFile`. Each only calls `touch_application_updated_at` (bumps `updated_at` for the changed-since API). They do not run any logic.
- `form_attempt_completed` has no receiver in `course_applications`.
- `post_save` on `AnonymousApplicant` and `User`, `post_delete` on `CourseApplication`, `pre_delete` on `User`, `user_logged_in`.

**What this means for the hook.**
- **Answer saved.** `QuestionAnswer` `post_save`/`post_delete` is the existing signal. But it fires once per answer row during `FormProgress.save_answers` (per question), and the resolver would run many times per page. It also does not fire for selected-option changes, which `receivers.py` already notes: options change through `selected_options.set()`, which sends no signal, and `save_answers` saves the answer afterwards, so the save lands on the receiver. A signal per row is the wrong grain. The right hook is one call per page submission: after `submit_page` in `application_form_page`, or one new "answers saved" signal from `save_answers`. The better design is a single explicit function, `rerun_requirements(application)`, called from the views that make changes. Receivers hide the call order, and the file notes that a receiver in a module nothing imports "fails silently rather than loudly".
- **Sitting completed.** `form_attempt_completed` exists and fires after the atomic block. A course_applications receiver can map the attempt to its application (`FormProgress.course_application` reverse OneToOne today, or a requirement's sitting). This is the one existing event that needs no new signal. Remember the receiver sits outside the sitting's transaction (the signal fires after it), so a failure in the resolver does not roll back completion.
- **Document uploaded.** No model exists yet; the upload-requirement spec adds one, and its save path calls the re-run.
- **Verdict given.** New (reviewer action); the action function calls the re-run inside the same transaction as the verdict. A verdict should be atomic with the re-run, since the review screen promises "the applicant will be asked to: ...".

**Recommendation.** Make the re-run one function (`reconcile_requirements(application)`: call the resolver, diff it with stored rows, create / supersede, never touch accepted). Call it explicitly from each event site, wrapped in a `select_for_update` on the application to serialise concurrent events (as `_start_application` does). Use the signal only where one already exists (`form_attempt_completed`). Add a reconcile-is-idempotent test: running twice on unchanged data changes nothing and writes nothing (so `updated_at` does not move, which matters for the changed-since API).

## 6. Size, and where to split

The idea's own order is review states first, then branch logic, then requirements plus resolver plus reopen. That third item is too big for one PR. A split by outcome that each stands alone:

1. **Reopening a completed form sitting, in `form_engine`.** Mechanism only: `FormProgress.reopen()`, prefilled earlier answers (already the case, since the answers survive), a way for a re-completion to be told apart from a first one, tests. It is a sensible standalone spec and can land first. It is user-visible only through its first consumer, so give it a thin consumer so it ships a visible outcome: let an applicant reopen their own submitted application form before the application is reviewed, from the status page, with the audit entry deferred until the review states exist (or recorded through whatever the review spec adds). If the review states have not landed, the consumer can be limited to "until approved" with no states and so "until submitted and not yet reviewed" is the only available rule. This ordering is a real dependency: "until the application is approved" needs the state machine from `application-review-ui`.
2. **Requirements model, resolver seam, and fixed-list resolver.** `ApplicationRequirement` (kind, status, holds-back, key, choice group, picked option, optional FK to a sitting), the `REQUIREMENT_RESOLVER` setting, loader, `RequirementDecision`, boot checks, conformance probe, the reconcile function, the content `requirements:` key and loader/validation. Outcome: an application has a stored list of requirements that follow the course's content. By itself it has no UI beyond admin. So pair it with the applicant page (3), or ship a read-only list on the status page as part of it.
3. **Applicant requirements page, form requirements.** The one page listing requirements and status, working through form requirements (own sittings), using `rerun`-after-completion. Outcome: an applicant can work through several forms in any order.
4. **Staff-verification requirements and reviewer accept/turn down.** Reviewer verdict (accepted, turned down) with free-text note, the held-back checks on approval and registration, the "approved, conditions outstanding" state. Depends on the review states and organisation-role reviewers. Outcome: reviewers clear requirements.
5. **Rejection reasons and the "the applicant will be asked to" preview.** Reason catalogue in Python per document type, applicant explanation, template override, resolver reading the reason. Depends on 2 and 4, and best with upload requirements (4 in the idea's order, "Upload requirements ... with rejection reasons, choices and upload history"), because reasons mostly bite on documents.
6. **Choices.** One-level groups, switching between options, first accepted supersedes the rest. This is applicant UI plus a reconcile rule, and depends on 2 and 3.

So: reopen is the cleanest independent start, requirements plus resolver is the foundation, and the rest each add one user-visible outcome on top. Staff-verification requirements need nothing from documents and can ride with the reviewer accept/turn-down spec. Form requirements need the reopen (for "fix my own mistake"), so landing reopen first removes a dependency.

**Risks to flag.**
- The `form_progress` OneToOne stays as is for now; merging it into requirements is a separate cleanup with real data-migration risk.
- The reconcile step is the heart of the design and the place bugs will live: concurrency (lock the application), idempotence (no writes when nothing changed), "accepted stays accepted", "superseded rows are kept". Give it its own tests and its own review.
- A downstream resolver runs on every event. A slow or failing resolver blocks answer saving. Decide up front whether a resolver failure fails the request or logs and keeps the stored list (the project says no logging unless asked, and "avoid silent failures", so likely fail loudly in dev, and decide for prod in the spec).
- Anonymous applicants can reach only a draft sitting (`owned_form_progress`). Requirements pages and reopen therefore assume a claimed (signed-in) applicant, and the spec must say so.

status: ok
