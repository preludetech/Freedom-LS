# Research: existing-flow touchpoints for anonymous course applications

Topic: every place that assumes an applicant is an authenticated `User`, and every downstream consumer that would have to cope with a `CourseApplication` that has no user yet. Code-reading only. No design is proposed here. "Needs" lines say what the anonymous flow would require from that spot, not how to build it.

All paths are relative to the project root. Line numbers were read at the current HEAD (318784b6).

## 0. Headline facts for the spec writer

1. The identity chain is `CourseApplication.user` (non-null FK, CASCADE) and `FormProgress.user` (non-null FK, CASCADE). Both are non-null today. The application form sitting (`FormProgress`) is what holds the answers and the uploaded files, so an application with no user means a `FormProgress` with no user too, or a sitting that is re-parented at claim time.
2. Nothing in `form_engine/page_flow.py`, `paging.py` or `queries.py` reads `user`. The owner assumption lives in the course_applications views (`user=request.user` lookups), the form_engine file views, and `QuestionAnswerFile`'s storage key.
3. `get_application_for_course`, `get_active_applications`, `get_access` and `get_dashboard_contributions` already treat an anonymous user as "no application". The anonymous visitor therefore always sees "Apply now" and a draft started anonymously is invisible to every one of them.
4. A claim step has two house patterns to mirror: the session-stash plus `login_required` landing view in `course_interest` (section 9), and the `next`-carrying redirect from `RegistrationCompletionMiddleware`. Both are GET-based, and both survive allauth's session-key cycling (pinned by `test_signup_arm_*` tests).
5. `user.registered` fires from `AccountAdapter.save_user`, and `SignupAttribution` and `LegalConsent` are written from signup hooks. All three depend on the signup request, not on `next`, so a signup made from the application's handoff records them normally (section 8).
6. `CourseApplication` and `CourseInterest` fire no webhook event today. `record_application_submitted` is a GA4 session event that reads nothing off `request.user`.

---

## 1. `freedom_ls/course_applications/`

### views.py

| Where | What it assumes | Anonymous flow needs |
| --- | --- | --- |
| `views.py:16,59` `@acquisition_login_required` on `apply` | Anonymous visitor is redirected to `account_signup?next=<apply url>` (or login when signups are closed) before any view code runs, including the visibility check. | The decorator removed or replaced on `apply` so an anonymous GET reaches the view. The decorator itself stays in use on `initiate_course_access` (`learner_interface/views.py:845`) and must not change. |
| `views.py:81-83` `user = cast(User, request.user)` | "acquisition_login_required guarantees an authenticated User." | A `User | AnonymousUser` path through `apply`. Type hints are mandatory and `# type: ignore` is banned, so the signature of `_start_application(user: User, course)` (`:39`) has to change. |
| `views.py:86` `raise_404_if_hidden_unregistered(user, course)` | Gets an authenticated user. | Already safe with `AnonymousUser` (section 3). Behaviour change: today an anonymous visitor to a hidden course's apply URL gets a signup redirect, never a 404 (see `test_deferred_login.py:459-474`). With the decorator gone they get a 404. That is the correct no-enumeration answer but it is a visible change. |
| `views.py:91` `get_application_for_course(user=user, course=course)` | Returns the existing application, which short-circuits to the status page (also before the coming-soon redirect, `:88-90`). | For an anonymous visitor this returns `None` (queries.py:31). An anonymous visitor who already started a draft has no way to find it again unless something other than `user` identifies it (session or token). |
| `views.py:97-98` coming-soon redirect | Independent of user. | Unchanged. |
| `views.py:100-105` `if course.application_form is not None or request.method == "POST"` then `_start_application` | Creates the application and the draft sitting on **any GET**, including prefetches and crawler hits. | An anonymous GET that creates rows is a bot and prefetch problem the authenticated flow does not have (the authenticated flow is bounded by signup). Applies to unclaimed-row growth and the expiry job in section 7. |
| `views.py:39-56` `_start_application(user, course)`: `get_or_create(user=user, course=course)` and `FormProgress.objects.create(user=user, ...)` | Race-safety comes from `UniqueConstraint(site, user, course)`. | See models.py below: with `user` NULL the constraint does not deduplicate. |
| `views.py:102-105` `record_application_submitted(request, course)` in the **no-form** branch | "Creating the application is the submission itself." | A no-form course: the submission moment is currently application creation. If creation happens before authentication, "submitted" and "claimed" separate for that branch too. |
| `views.py:114` `@login_required` on `application_status` and `views.py:128-132` `pk=pk, user=request.user` | The status page is owner-only, 404 for non-owners. | Today an anonymous visitor to the status URL is redirected to `account_login?next=...` (`test_views.py:313-322`, `test_deferred_login.py:497-511`). If the status page must be reachable pre-claim, ownership needs an anonymous identity. Otherwise leave as is. |
| `views.py:142-157` `_owned_application_with_form` (`pk=pk, user=request.user`) | Shared by the form page and check-answers views, and the only access control on them. | The single choke point for "who may see this application's pages". Both `application_form_page` (`:183`, `@login_required`) and `application_check_answers` (`:229`, `@login_required`) go through it. |
| `views.py:244-251` `form_progress.complete()` then `record_application_submitted` then `messages.success` then `redirect("learner_interface:dashboard")` | Submit lands on the **dashboard**, which is an authenticated-only panel. The success message text is "has been submitted and is pending review". | The authenticate-at-the-end step belongs right where this POST is. `FormProgress.complete()` (form_engine/models.py:395-404) stamps `completed_time`, scores, saves and sends `form_attempt_completed(user=self.user, ...)`. Completion before claim means the sitting is "submitted" while unowned (see section 2). |
| `views.py:253-254` POST on a submitted application redirects to status | Idempotent re-POST. | Same behaviour needed for a claimed application. |
| `views.py:289` `Cache-Control: no-store` on check-answers | Shows personal data. | Keep for an unclaimed draft. |
| `views.py:76-78` NOTE comment: "when application review lands, the POST body will wrap get_or_create in an atomic block and call app.submit() ..." | TODO-style NOTE. | Must not be deleted (CLAUDE.md). The application-review spec (section 10) will add `submit()` and `state`; an anonymous draft pre-dates `state`. |

### queries.py

- `queries.py:31-32` `get_application_for_course`: `if not user.is_authenticated: return None`. Zero queries for anonymous. Tested at `tests/test_queries.py:42-51` ("returns_none_with_no_query"). Needs: if an anonymous visitor's own draft is to be found by course, this contract (no query, None) changes or a second lookup is added. Either way that test and its "no query" assertion are affected.
- `queries.py:48-49` `get_active_applications`: `.none()` for anonymous, zero queries (`tests/test_queries.py:60-67`). Used only by the dashboard backend contribution. An unclaimed draft correctly should not appear here (no user), and a just-claimed one will, so it needs no change except that once claimed, `form_progress__completed_time` null (a draft) already shows in `get_active_applications` (it returns all of a user's applications with no state filter). Check that a claimed-but-unsubmitted draft rendering is intended (see dashboard partial, section 5).

### backends.py (`ApplicationCourseAccessBackend`)

- `backends.py:130-133`: `is_registered_for_course(user, course)` returns False for anonymous (`learner_management/utils.py:30-31`), so a gated course falls through to the application branch.
- `backends.py:137-139` imports `get_application_for_course` and gets `None` for anonymous.
- `backends.py:155-167`: anonymous visitor gets `CourseAccessDecision(cta_label="Apply now", cta_url=reverse("course_applications:apply", ...), can_self_register=False, ...)`. The decision never branches on authentication. So the course-detail CTA already points anonymous visitors at the apply URL. What changes is only what that URL does.
- `backends.py:141-153`: a returning applicant gets "View my application" with the status URL. An anonymous visitor with a draft in progress cannot get this because the lookup is by `user`. Needs: decide whether a draft the visitor started should show "Continue application" (a `CourseAccessDecision` change, whose fields are listed in section 3) or stay "Apply now".
- `backends.py:201-221` `get_dashboard_contributions(user)`: calls `get_active_applications(user)` and returns `[]` when empty. `learner_interface/views.py:635` only calls it when `inputs.is_auth`, so it is never called for an anonymous user in practice. Tested for anonymous at `tests/test_backends.py:517-527` and `course_access/tests/test_backends.py:283-288`.
- Tests encoding anonymous behaviour of the backend: `course_applications/tests/test_backends.py:493-511` (`test_anonymous_user_on_gated_course_returns_apply_now_with_no_query`: asserts **no application query** for anonymous). If a draft lookup for anonymous visitors is added, the no-query assertion has to change.

### models.py

- `models.py:37-41` `user = ForeignKey(AUTH_USER_MODEL, on_delete=CASCADE, related_name="course_applications")`, non-null. Needs: a way to hold an application with no user (nullable user, or a separate pre-claim record), plus an owner identity (the email address the idea says is collected) on the application.
- `models.py:62-67` `UniqueConstraint(fields=["site", "user", "course"], name="unique_application_per_site_user_course")`. In PostgreSQL, NULLs are distinct in a unique constraint, so a nullable `user` would stop deduplicating anonymous rows, and `get_or_create` race-safety (`views.py:46-48` comment) goes with it. Needs: a different uniqueness story for unclaimed rows, and a story for a claimant who already has an application to the same course (claim collision).
- `models.py:51-57` `form_progress` is `OneToOneField(..., on_delete=RESTRICT)` and null for a no-form course. `models.py:72-82` `is_submitted` treats "no sitting" as submitted-on-creation, and "sitting with `completed_time`" as submitted. Needs: for a no-form course, a created-but-unclaimed row would read as `is_submitted` True. That is wrong if the visitor has not authenticated yet.
- `models.py:24-29` docstring NOTE about application review adding `state`, `submitted_at`, etc. Do not delete.
- `models.py:70` `__str__` prints `self.user_id`; with a null user it prints `None`.
- Migrations present: `0001_initial.py`, `0002_courseapplication_form_and_more.py`, `0003_remove_courseapplication_form_and_more.py`. Existing migration files must not be edited (CLAUDE.md).

### admin.py

- `admin.py:24` `USER_ERASURE_CASCADE_MODELS.add(CourseApplication)`: the user-erasure path is the only way an application is deleted (the admin denies delete, `:142-145`). An unclaimed application has no user to erase, so only an expiry job (section 7) or a deliberate admin path can remove it, and its `FormProgress` has RESTRICT (`models.py:55`) so the application must be deleted before the sitting.
- `admin.py:78` `list_select_related = ["user", ...]`, `admin.py:102` `select_related("user", ...)`, `admin.py:147-153` `applicant_email` reads `obj.user.email` and `applicant_name` reads `obj.user.first_name`. Both raise `AttributeError` on a null user. Needs: show the entered email address for an unclaimed application.
- `admin.py:88-93` `search_fields = ["user__email", "user__first_name", "user__last_name", "course__title"]`. An unclaimed application is unsearchable by its email until that email is a field on the application.
- `admin.py:118` `admin_change_link(request, obj.user)` in `render_change_form`: fails or renders blank for a null user.
- `admin.py:27-55` `CourseApplicationSubmittedFilter`: "submitted" = no sitting OR sitting completed. An unclaimed completed sitting would count as submitted. Needs: a notion of "claimed" next to "submitted".
- `tests/test_admin.py` uses `client.force_login(staff)` throughout; no anonymous coverage.

### factories.py

- `factories.py:23` `user = factory.SubFactory(UserFactory)`. Needs: an unclaimed variant, or a trait, for tests. No other factory change needed because `FormProgress` is created by `form_engine.factories` (see section 2).

### Templates

- `apply.html` (no-form confirmation): extends `_base.html`, has a form POST with `{% csrf_token %}`, "Submit application" and "Cancel" buttons. It says "You are about to submit an application" and does not read `request.user`. Needs: the email field the idea asks for (prefilled from `request.user.email` if signed in) lives either here (no-form courses) or on the first form page (form courses). The form-course flow skips this page entirely (`views.py:100-105`), so for form courses the email capture has no page to live on today.
- `form_page.html`: extends `_base.html`; the form posts to its own URL; no `request.user` reference. Uses `application.pk` for the "Your answers" link (`:60`).
- `check_your_answers.html`: no `request.user` reference. Download link `{% url 'form_engine:own_question_answer_file' file_pk=... %}` (`:54`) goes to a `@login_required` view that filters by the owner (section 2). That link breaks for an anonymous applicant who has uploaded a file. `Submit application` is a plain POST form (`:81-84`). This page is the natural place for "authenticate right at the end".
- `application_status.html`: static "received and is currently pending review" text plus "Back to dashboard" button (`:26`) linking `learner_interface:dashboard`. Needs: nothing for a claimed application. NOTE comment at `:20-24` must not be deleted.
- `partials/dashboard_applications.html` (dashboard panel): see section 5.
- Header: `_base.html` includes `partials/header_bar.html`, which for an anonymous visitor includes `partials/login_prompt.html` (section 5).

### Tests that encode "anonymous goes to signup/login" and will need to change or be added

`course_applications/tests/test_views.py`:
- `:67-74` `test_get_unauthenticated_redirects_to_signup` (asserts `Location == account_signup?next=<apply url>`). Encodes the behaviour being removed.
- `:313-322` `test_unauthenticated_redirects_to_login` for the **status** page. Stays valid if the status page stays owner-only.
- Everything else in `test_views.py` uses `client.force_login(user)` (for example `:47,60,79,98,116,132,143,159,171,196,...,1104`) and covers the authenticated flow, which should be unchanged for a signed-in applicant.

`accounts/tests/test_deferred_login.py` (module docstring `:4-8` describes apply as an `acquisition_login_required` flow):
- `:166-181` `test_anonymous_access_to_apply_redirects_to_signup_with_next`: encodes the removed behaviour.
- `:184-202` `test_deferred_login_gated_course_lands_on_apply_page`: authenticated; stays.
- `:329-353` `test_deferred_login_apply_round_trip_creates_no_application`: asserts an anonymous apply POST redirects to login and that, after sign-in, following `next` lands on the 200 confirmation page with **no** `CourseApplication` row. Directly contradicted if an anonymous POST/GET now creates a row.
- `:356-371` `test_deferred_login_apply_repeat_submissions_stay_idempotent`: authenticated; stays.
- `:417-451` `test_deferred_login_application_status_owner_sees_status_page` and `..._non_owner_gets_404`: depend on status page login redirect; stay if status stays owner-only.
- `:459-474` `test_anonymous_access_to_hidden_course_apply_redirects_to_signup_not_404`: encodes the removed behaviour. The sibling at `:477-494` (`initiate_course_access`) stays.
- `:497-511` `test_anonymous_access_to_status_for_hidden_course_application_redirects_to_login`: stays if status stays owner-only.
- `:259-321` the signup-arm tests for express interest are the precedent for an apply signup-arm test (they use `django_db(transaction=True)`, `_signup_payload`, `_confirm_url_for`).

`accounts/tests/test_header_auth_links_carry_next.py`:
- The `login_page_for_apply` fixture docstring (`:50-56`) says "Apply itself now sends an anonymous visitor to signup (see test_acquisition_login_required.py)". The fixture builds the login page URL directly with `?next=<apply url>`, so it keeps working, but the docstring becomes stale.

`accounts/tests/test_acquisition_login_required.py`: tests the decorator in isolation with an `rf` request. No change (the decorator still exists for other views).

`learner_interface/tests/test_course_detail_public.py:100-131` asserts "Apply now" and the apply URL for an anonymous visitor on a gated course. These stay valid as long as the CTA label and URL for an anonymous visitor are unchanged.

`course_access/tests/test_analytics_events.py` (3 references to apply/application): reads the `record_application_submitted` event; see section 3.

`contrib/conformance/test_urls.py:50-57` pins the URL names `course_applications:apply` and `course_applications:status`. Renaming or splitting those URLs would trip it. A claim URL added in this app is not covered, but a new URL name may need an entry if the conformance list is exhaustive.

Playwright: `course_applications/tests/playwright/test_application_form_flow.py` drives the authenticated form flow.

---

## 2. `freedom_ls/form_engine/`

### `FormProgress.user` and its readers

- `form_engine/models.py:247-249` `user = ForeignKey(User, on_delete=CASCADE, related_name="form_progress")`, non-null. No unique constraint involves `user` (the model has none beyond the base). `FormProgress` is site-aware.
- `models.py:265-266` `__str__` uses `self.user`.
- `models.py:403` `complete()` sends `form_attempt_completed.send(sender=type(self), user=self.user, form=self.form, attempt=self)`. The only receiver is `learner_progress/signals.py:96-119`, which takes `attempt` only, looks up `CourseFormAttempt` and returns if none. It does nothing for an application sitting (the docstring there says so explicitly). So completing an unowned sitting is safe for that receiver, but `user=None` would be sent to any downstream receiver that reads `user`.
- `models.py:680` `QuestionAnswer.__str__` uses `self.form_progress.user`.
- **`models.py:700` `user_id = instance.answer.form_progress.user_id` then `return f"user_uploads/{user_id}/form_answers/{instance.pk}{extension}"`**: the file's storage key is built from the sitting's owner id. With no user this key would be `user_uploads/None/...`. Needs: a stable key that does not depend on a user who does not exist yet, and a decision on whether files are moved when the application is claimed (keys are not rewritable in place for S3 without a copy). `QuestionAnswerFile.save` (`:724`) and a post_delete receiver remove the stored object.
- Other readers (all use `user` to scope a user's own sittings, so they exclude an unowned sitting naturally):
  - `form_engine/admin.py:264,287,305,327,389,428,444-446`: `FormProgress` admin `list_display`/`list_select_related` include `"user"`, `search_fields = ("user__email", "form__title")` (`:281`), `readonly += ["user", "form"]` (`:327`), and the answer-file admin shows `str(obj.answer.form_progress.user)` as "Applicant" (`:444-446`). All need to cope with a null user if `FormProgress.user` becomes nullable.
  - `learner_progress/attempts.py:92-94` `FormProgress.objects.create(user=course_progress.learner.user, ...)`: a course-attempt sitting is always user-owned. Unaffected, but this is why `FormProgress.user` being nullable would be a loosening that this caller does not need.
  - `learner_progress/signals.py:96-119`, `learner_progress/queries.py`, `learner_progress/models.py:268` (`CourseFormAttempt.form_progress` OneToOne, CASCADE): course-form attempts only.
  - `reports/indexes.py:325,436` and `reports/gather.py`: filter `FormProgress` per learner; an unowned sitting is never selected.
  - `learner_interface/utils.py`, `views.py`, `apis.py`, partials `form_progress_scores.html` and `exam_previous_attempts.html`: course quiz and exam flows.
  - `qa_helpers` and `dev_tools` commands that create or clear sittings (about 20 files): all pass `user=`. `dev_tools/management/commands/danger_clear_all_course_progress.py` and `danger_content_delete.py` touch `FormProgress`.
- `form_engine/factories.py`: `FormProgressFactory` needs a user trait or `user=None` variant if the column becomes nullable.

### Page flow, paging, queries: no user dependency

- `page_flow.py` (`resolve_page`, `page_context`, `render_form_page`, `submit_page`), `paging.py` (`resume_page_number`, `unanswered_required_in_form`, `unanswered_required_message`, `build_page_links`) and `queries.py` (`page_questions`) take a `FormProgress` and a `Form`; grep found no `user` reference in any of them. They would work on an unowned sitting unchanged. The identity check is entirely in the calling view.
- `FormProgress.save_answers` (`models.py:348-393`), `existing_answers_dict` (`:332`) and `record_page_reached` (`:298`) also do not read `user`.
- Required-answer completeness (`unanswered_required_in_form`) is the "whole-form check" at `views.py:242`; it is the gate before authentication would be asked.

### How `answer_file` is uploaded and served

- Upload and remove: `form_engine/views.py:79-134`, both `@login_required @require_POST`. `_owned_file_question` (`:33-52`) resolves `FormProgress` with `pk=progress_pk, user=request.user`. An anonymous applicant cannot upload a file today and would get an HTMX redirect to login. The widget template is `form_engine/templates/form_engine/inputs/file_upload.html` and posts to these endpoints using `form_progress.pk`.
- Applicant download: `form_engine/views.py:162-174` `own_question_answer_file` (`@login_required`), `get_object_or_404(..., answer__form_progress__user=request.user)`. The docstring says "Ownership is the whole control: the lookup is scoped to the signed-in owner of the sitting, never to the unguessability of the URL." Needs: if an anonymous applicant can attach and download a file, the control that replaces "signed-in owner" has to be a deliberate one. The docstring states the rule that the URL's unguessability is not the control.
- Staff download: `form_engine/views.py:177-188` `question_answer_file_download_view`, gated by `can_download_answer_files(request.user)` (`form_engine/permissions.py`). No user-ownership assumption.
- `form_engine/uploads.py:1-102`: validation only (extension, 6 MB cap, PDF magic, Pillow re-encode with EXIF/GPS strip). The module docstring says files are served "to its owner, and to a superuser reviewing the application". No `user` reference. Needs: anonymous file upload is an unauthenticated write path to storage; the size cap and re-encode already bound it, but there is no per-visitor limit. `spec_dd/1. next/file-scanning/1. spec.md` (section 10) is the content-scanning follow-up and describes the same files.
- `form_engine/templates/form_engine/partials/answer_errors.html` and `page_children.html` are included by `form_page.html`; no user reads.

### Admin for `FormProgress`

Covered above (`form_engine/admin.py:264-327`). `admin.py:253` `can_download_answer_files(request.user)` is the staff permission and unaffected. `admin.py:292` comment: an admin action completes an attempt, which "scores the attempt and sends form_attempt_completed".

---

## 3. `freedom_ls/course_access/`

- `analytics_events.py:48-49` `record_application_submitted(request, course)` calls `_record_course_access_requested(request, course, "application")`, which calls `record_analytics_event(request, COURSE_ACCESS_REQUESTED, course_event_params(course) | {"request_kind": "application"})`. `course_event_params` (`:20-31`) returns `course_slug`, `course_id`, `access_type` and reads nothing off `request.user`. `record_analytics_event` (`base/analytics_events.py:90-118`) stores the event in `request.session[ANALYTICS_EVENTS_SESSION_KEY]` (deduped by whole payload) and the next page render emits it. So it already works for an anonymous request, with one condition: it needs a session, and the **session key is cycled at login and signup** (the express-interest signup-arm test pins that the session stash survives). Whether the event should fire at anonymous submit or at claim is a spec decision; at claim the same request that holds the event is the post-auth request. `record_sign_up` (`base/analytics_events.py:121-123`) is called from `save_user`, so a signup from the handoff records `sign_up` plus `course_access_requested` in the same session if both fire.
- `base/analytics_events.py:43`: `user_id` is a reserved GA4 parameter name that the recorder rejects, so no user identifier can be added to the event.
- `visibility.py:20-37` `raise_404_if_hidden_unregistered(user: RequestUser, course)`: calls `is_registered_for_course(user, course)`, which returns False for an anonymous user (`learner_management/utils.py:30-31`). So anonymous plus hidden gives 404. It is already anonymous-safe, and `override_visibility_to_visible()` lifts it. No change needed.
- `backends.py:41-61` `CourseAccessDecision` (frozen dataclass) fields: `cta_label`, `cta_url`, `can_self_register`, `can_access_content`, `enrolment_summary`, `acquisition_heading`, `acquisition_subtext`, `is_accessible_for_free`. The class docstring says "All callers read only these four fields" and "no caller may branch on `Course.access_config` directly". Needs: any "Continue your application" affordance for an anonymous visitor goes through these fields. No new field is needed to keep "Apply now" for anonymous.
- `backends.py` base classes: `FreeOnlyCourseAccessBackend` and `VisibilityEnforcingBackend` (`filter_visible` is not overridden by `ApplicationCourseAccessBackend`, `course_applications/backends.py:66-68`). `DashboardContribution` (`backends.py:76-86`): `template_name` plus an opaque `context` dict with a deliberate `Any`.
- `learner_management/utils.py:16-36` `is_registered_for_course(user, course)`: `if not user.is_authenticated: return False`.
- Dependency edges to keep: `course_access` must never import `course_applications` (`docs/app_structure.md:195`, `course_access -.-> course_applications` is a runtime-only dotted edge for tests); `learner_interface` reaches applications only through `get_dashboard_contributions` (`queries.py` docstring).

---

## 4. `freedom_ls/webhooks/`

- Registered event types are only `user.registered`, `course.completed`, `course.registered` (`base/webhook_event_types.py:1-5`). **No application event exists.** `webhooks/presets.py:51-57` has a preset whose JSON body uses `{{ event.data.user_email }}` (an email-marketing style subscriber payload); `delivery.py:27-31` `build_webhook_payload(event)` renders from the stored `WebhookEvent.payload`. Nothing reads an application.
- Payloads all carry `user_id` and `user_email` (`webhook_event_types.py:8-30`). `user.registered` also carries `first_name`, `last_name`.
- `user.registered` is fired from `accounts/allauth_account_adapter.py:127-148` `save_user` when `commit` is true, with `user_id=user.pk`, `user_email`, `first_name`, `last_name`, followed by `record_sign_up(request)`. It fires for any signup including one arriving from an application handoff.
- Needs (if the spec wants integrators told about an application): a new event type would have to cope with an unclaimed application having an email but no `user_id`. `course.registered` (`learner_progress/signals.py:157-168`) is sent only when a registration row is created and carries `user_id` unconditionally; approving an application does not create a registration today (`research_fls_user_attributes_and_registrations.md:183` in the corporate-job-course-recommendations research confirms application does not create registrations).
- `referral-attribution-over-time/research_attributable_events.md:111` confirms "`CourseApplication` and `CourseInterest` fire no webhook event at all today."

---

## 5. `freedom_ls/learner_interface/` and the header

- Course detail CTA: `learner_interface/views.py:703-811`. `is_registered = get_is_registered(user=request.user, course=course)` (`:712`), `raise_404_if_hidden_unregistered` (`:715`), `decision = get_course_access_backend().get_access(user=request.user, course=course)` (`:716`). For a non-registered visitor, `start_url = decision.cta_url; cta_label = decision.cta_label` (`:737-738`). So an anonymous visitor on a gated course sees "Apply now" linking to `course_applications:apply` today. `cast("User", request.user)` at `:732` is only on the registered branch.
- `course_detail.html:174-176` renders `<c-button href="{{ start_url }}" class="w-full">{{ cta_label }}</c-button>`, a plain link, so the apply entry is a **GET**. `course_detail.html:153-166` shows `acquisition_heading` / `acquisition_subtext` ("Application required" / "Apply and we'll review your request.").
- `initiate_course_access` (`learner_interface/views.py:845-909`, `@acquisition_login_required`): for a gated course `decision.can_self_register` is False so it redirects to `decision.cta_url` (the apply URL) at `:876-882`. Anonymous visitors hitting this URL are sent to signup first. It stays an authenticated chokepoint; it only matters that the apply URL it redirects to is reachable by a signed-in user.
- Dashboard: `learner_interface/views.py:631-640` calls `inputs.backend.get_dashboard_contributions(user=request.user)` only `if inputs.is_auth`, renders each via `render_to_string(c.template_name, c.context, request=request)`. Comment at `:632-633`: "anonymous visitors have no panels". Needs: nothing for a claimed application. A claimed draft application (sitting not completed) would appear in `get_active_applications` (no state filter, `queries.py:50-52`) and render in `partials/dashboard_applications.html`; check whether the panel's link copy for a draft is right (it links to the status page, which redirects an unfinished sitting back to the form, `views.py:133-134`).
- Submit-success redirect (`course_applications/views.py:251`) goes to `learner_interface:dashboard`.
- Header: `base/templates/_base.html` includes `partials/header_bar.html`. For an anonymous visitor it includes `partials/login_prompt.html:2-9`, which builds the Login and Signup links with `{% url_with_next "account_login" %}` / `"account_signup"`. `accounts/templatetags/accounts_tags.py:18-36` `url_with_next` calls allauth's `passthrough_next_redirect_url(request, url, "next")`, which carries only a `next` that is **already present in the current request's query string or POST**. It does not add the current page as `next`. So on an anonymous application page (no `?next=`), the header Login/Signup links carry no way back to the application. Needs: anonymous application pages need either an explicit `next` in the links or a session-held pending-claim, because the header links will not do it.
- `account/login.html:16-20,49-53` and `account/signup.html:79` also use `url_with_next`, so `next` set on the auth page persists across the signup/login toggle (this is what `test_header_auth_links_carry_next.py` pins).
- Anonymous-safe pieces: `get_course_index` is anonymous-safe (comment at `:717-718`). Course detail tests for anonymous visitors live in `learner_interface/tests/test_course_detail_public.py` and `test_course_access_integration.py` (40 references to apply/application).

---

## 6. `freedom_ls/qa_helpers/management/commands/`

- `qa_reset_course_application.py`: deletes a QA applicant's `CourseApplication` then the `FormProgress` it names (RESTRICT order, `:8-9`, `:88-152`), found by `CourseApplication._base_manager.filter(user=user, course=course)` (`:100-101`) and a `user` argument. Needs: an unclaimed application has no user, so this command cannot find it; a way to reset by email address or by the application's id is needed, and the doc says a "fresh apply mints a brand-new FormProgress".
- `qa_create_application_review_accounts.py`: creates staff and permission accounts (`_ensure_user`, `:90-118`) with `set_password(email)`; `_purge_course_data(user)` deletes applications and sittings by `user=user` (`:147-155`); `_describe` counts `CourseApplication._base_manager.filter(user=user)` (`:181-182`). It names `view_courseapplication` / `view_formprogress` permissions (`:67-69`). Assumes every application has an owner; an unclaimed one is not purged by it.
- `qa_create_application_docs_scenario.py`: builds a learner `demodev_applicant@email.com` with an in-flight `CourseApplication` via `CourseApplicationFactory(user=learner, ...)` / `get_or_create(user=learner, ...)` (`:326-353`) so the dashboard panel renders for screenshots. Needs: an unclaimed-draft scenario if docs screenshots of the anonymous flow are wanted.
- `qa_create_clean_applicant.py` (18 application references) and `qa_clear_form_sittings.py`, `qa_complete_form.py` also take a `user`.

---

## 7. `freedom_ls/deployment/housekeeping.py`

- `run_housekeeping_sweeps()` (`:221-308`) runs, in order and each in its own `try/except SWEEP_FAILURES = (CommandError, DatabaseError)`: `prune_db_task_results`, `clearsessions`, the late-unpicked-task check, the orphaned RUNNING task reaper (`mark_orphaned_running_tasks_failed`, bookkeeping not recovery), and the orphaned RUNNING cohort report reaper (`mark_orphaned_running_reports_failed`, uses `GeneratedReport._base_manager`). Returns `HousekeepingOutcome(sweep_failures, findings, notes)`. Invoked by the `fls_run_housekeeping` management command (`deployment/management/commands/fls_run_housekeeping.py`); the downstream deploy supplies the schedule.
- Config: `deployment/config.py` holds `HOUSEKEEPING_*_MAX_AGE_SECONDS` settings (`config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS`, `..._ORPHANED_TASK_..._`, `..._ORPHANED_REPORT_...`); a new sweep would add a setting there. Tests: `deployment/tests/test_housekeeping.py`, `test_config.py`.
- **Dependency edge:** `docs/app_structure.md:84-87,251` lists `deployment --> base, content_engine, organisations, reports` and no `course_applications`. A sweep inside `deployment/housekeeping.py` that deletes expired unclaimed applications would add `deployment -> course_applications`, which `app_structure.md` does not allow today; `course_applications` is an optional app (`COURSE_ACCESS_BACKEND` can drop it, and `dev_tools` guards with `apps.is_installed("freedom_ls.course_applications")`). The existing sweeps use `_base_manager` because housekeeping has no request and so no site. Cleanup of the stored files has to go through `QuestionAnswerFile`'s post_delete receiver, so the sweep has to delete rows via the ORM (not `queryset._raw_delete`) and in the order application then `FormProgress` (RESTRICT).
- Session retention bounds an anonymous visitor's claim handle if it lives in the session: `config/settings_prod.py:51` `SESSION_COOKIE_AGE = 1209600` (2 weeks), and `clearsessions` runs in housekeeping. `settings_dev.py:141` sets only the cookie name. The existing "Data Retention, Deletion, and Subject Rights" roadmap section says files an applicant uploads "are kept until deleted by hand, and deleting the applicant's account is the only thing that removes them automatically" (`docs/product/roadmap.md:106`); an unowned application has no account whose deletion removes it.

---

## 8. `freedom_ls/referral_tracking/` and the `accounts` signup path

What a signup made from the application's handoff would record (all independent of `next`):

- `user.registered` webhook: `AccountAdapter.save_user` (`accounts/allauth_account_adapter.py:127-148`), then `record_sign_up(request)` (GA4 `sign_up`, method "email").
- `LegalConsent`: `SiteAwareSignupForm.custom_signup` (`accounts/forms.py:169-206`) writes `LegalConsent` rows for the checkboxes submitted (`accept_terms`, `accept_privacy`, `consent_method="signup_checkbox"`, `ip_address=get_client_ip(request)`) inside `transaction.atomic()`. Only if the site's policy requires terms (`get_effective_require_terms_acceptance`). **Needs:** if an anonymous applicant is asked for an email only and then signs up, the signup form is the existing and only consent capture. `LegalConsent` is in `USER_ERASURE_CASCADE_MODELS` (`accounts/admin.py:20`). Anonymous applicants would leave personal data (email, answers, files) with no consent record and no account; `get_client_ip` raises `PermissionDenied` when `TRUSTED_PROXY_IP_HEADER` is configured and the header is missing (`accounts/utils.py:23-60`).
- Honeypot and `SiteAwareSignupForm` fields: `first_name` required by policy, `last_name` optional, `fax_number` honeypot; the email is typed again on signup. The idea wants the email prefilled where signed in; on signup, `account/login.html` already offers a signup link with `email=` prefilled (`url_with_next "account_signup" email=form.data.login`), a precedent for passing an email to the signup page.
- `SignupAttribution`: `referral_tracking/signals.py:21-45` receiver on allauth `user_signed_up` calls `record_signup_attribution(request, user, client_ip)` (`capture.py:215-243`), which reads the first-touch cookie (or records `direct`/`none`), `_ga`/`_fbp`/`_fbc` cookies, `client_ip` and `User-Agent` off the signup request. OneToOne on user (`models.py:52-55`), written exactly once, in `USER_ERASURE_CASCADE_MODELS` (`referral_tracking/admin.py:81`). A signup from the handoff gets attribution from its own request cookies, same as any signup. A user who already exists and logs in rather than signs up gets none (that is the login-gap the `referral-attribution-over-time` spec fills with `user_logged_in`).
- `next` handling on signup: allauth passes `next` through the signup and email-confirmation flow (`test_signup_arm_*` in `test_deferred_login.py:259-321`), and `accounts/views.py:60-68` `_safe_post_completion_redirect` validates it with `url_has_allowed_host_and_scheme`. Nothing in `referral_tracking` or `accounts` depends on `next`. The claim could ride on `next` plus a session value, as `course_interest` does.
- `RegistrationCompletionMiddleware` (`accounts/middleware.py:79-127`) redirects any authenticated, non-superuser user with incomplete `additional_registration_forms` to `accounts:complete_registration`, carrying `next=request.get_full_path()` for a GET/HEAD non-HTMX request (`:123-127`) and dropping `next` otherwise. Exempt names are in `EXEMPT_URL_NAMES` (`:29-46`). **Needs:** a claim URL that is a GET (so it can be the post-auth `next`) will be intercepted and replayed after profile completion, which is the desired behaviour; a POST claim would be dropped. The completion state is cached in `request.session[CACHE_SESSION_KEY]`.
- Open signup policy: `acquisition_auth_url` (`accounts/utils.py:113-121`) returns signup while `is_open_for_signup`, else None (login). `is_open_for_signup` (`allauth_account_adapter.py:161-185`) reads `SiteSignupPolicy` or `config.ALLOW_SIGN_UPS`. **Needs:** when signups are closed on the site, the handoff has to go to login, and a person with no account cannot finish; the anonymous draft would never be claimed. `redirect_to_auth` (`:124-153`) returns 204 plus `HX-Redirect` for HTMX requests and 302 otherwise.

---

## 9. Existing "pending action in session" patterns

### `course_interest` (closest precedent)

- `course_interest/views.py:25` `_PENDING_INTEREST_SESSION_KEY = "course_interest_pending_slug"`.
- `partial_express_interest` (`:36-76`, POST-only HTMX): anonymous branch (`:54-62`) builds `next_url = reverse("course_interest:deferred_express_interest", ...)`, stores `request.session[_PENDING_INTEREST_SESSION_KEY] = course_slug`, and returns `redirect_to_auth(request, next_url=next_url, auth_url=acquisition_auth_url(request))`. It resolves **before** the course lookup so an anonymous POST for any slug gets an identical redirect (no existence leak).
- `deferred_express_interest` (`:110-130`, `@login_required`, GET): looks up the course, applies visibility, `request.session.pop(KEY, None)`, writes only `if pending_slug == course_slug and course.visibility == COMING_SOON`, then redirects to the course detail. The docstring: "records the interest only for the slug that view stashed in the session on the way out, so a forged `<img src>` or a link prefetch of this URL writes nothing."
- `partial_remove_interest` (`:79-107`): anonymous goes to `redirect_to_auth(request, next_url=course_detail)` with nothing deferred.
- URL registered at `course_interest/urls.py` (name `course_interest:deferred_express_interest`, also pinned in `contrib/conformance/test_urls.py:69`). History in `spec_dd/3. done/2026-09-01_17:04_bug-interested-login-405/` (plan lines 108-117, 199, 225-232).
- Tests: `test_deferred_login.py:210-321` and `course_interest/tests/test_views.py:312-351,423-`. They show the stash survives the allauth session-key cycle during signup and email confirmation (`transaction=True`).
- Difference to note: interest is one idempotent row per (user, course) and carries no data. An application carries answers and files, so what is stashed is a handle to the draft, not a slug. The session carries the draft only in that browser, so confirming an email in another browser or device loses the stash.

### accounts middleware / `complete_registration`

- `RegistrationCompletionMiddleware` (section 8) is the other house pattern: a redirect that carries `next=<current full path>` and a session cache (`CACHE_SESSION_KEY = "_registration_completion_state"`) keyed by a hash of config. `complete_registration_view` (`accounts/views.py:76-113`, `@login_required`) re-emits `next` as a hidden field (`next_value`, `:107-112`) and ends in `_safe_post_completion_redirect`, which validates `next` with `url_has_allowed_host_and_scheme`.
- Header-link `next` carry: `accounts/templatetags/accounts_tags.py:18-36` (see section 5).
- Analytics events are also a session-list pattern (`base/analytics_events.py:112-118`, "a new list, not an in-place append, so the session middleware's dirty check sees the change").

---

## 10. Specs in `spec_dd/1. next/` and `spec_dd/2. in progress/` that touch applications, review or signup

`spec_dd/2. in progress/`: nothing else touches applications. A grep of that folder for `CourseApplication`, `course_applications` and `signup` found only incidental mentions in `user-communication-3-messaging-policy/research_flexible_configurable_comms.md` and two `corporate-job-course-recommendations-1-hr-attributes` research notes. This idea's own `idea.md` and `todo.md` are also there.

`spec_dd/1. next/`:

- `educator-interface-full-polish/application-review-ui/` (`idea.md`, `research_review_workflow.md`): the review workflow. `CourseApplication` gains `state = FSMField(default="draft", protected=True)`, `submitted_at`/`decided_at`/`decided_by`, submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions, `ApplicationNote`, `ApplicationStateTransition`, the `application_state_changed` signal and an active-state **partial unique index replacing the plain constraint**. Review UI in `educator_interface`. **Collision points:** (a) its `submit` transition needs an actor (`request.user`), which an unclaimed application does not have; (b) the partial unique index replaces `unique_application_per_site_user_course` (the same constraint the anonymous flow needs to rework for NULL users); (c) the model docstring and the NOTE comments in `views.py`, `models.py` and `application_status.html` point at it. Its "draft" state is the natural home for "unclaimed draft" if the anonymous idea lands first or second, so the ordering has to be decided.
- `roadmap.md` (`spec_dd/1. next/roadmap.md:128,213,236`): puts application review "its own effort once the rebuilt panel framework exists"; `:213` says application review adds approved and rejected notification events.
- `referral-attribution-over-time/1. spec.md` (and research): records a per-user attribution timeline. Lines 285-287 plan to hook `_start_application` (`views.py`) on the `created` branch of `get_or_create` with `kind=course_application`, `target=app`, `occurred_at=app.created_at`. Lines 84-86 treat `CourseApplication.created_at` as the conversion's `occurred_at`. Also adds a `user_logged_in` receiver. **Collision:** it assumes the application exists with a user at `_start_application`. If the application is created anonymously, the attribution conversion event has no user to attach to until claim; and "when the person acted" (anonymous creation) differs from when they authenticated. Its line 422 defines new edges `course_applications -> referral_tracking`.
- `failed-login-follow-up/idea.md`: staff follow-up for people who got stuck on login after clicking Apply. States "`CourseInterest` and `CourseApplication` both require a `User`" and nothing persists an anonymous email. Anonymous apply with an email address solves the same problem from the other side. Overlap is the capture-an-anonymous-email privacy analysis in `research_capturing_failed_signin_intent.md` (POPIA s69 / PECR consent for follow-up).
- `file-scanning/1. spec.md`: scanning for `QuestionAnswerFile`s (identity document scans). Anonymous uploads widen who can put files into storage. Its code sketch at `:336` notes a UUID primary key for the actor, "never the anonymous user Django types it as".
- `form-engine-branch-logic/` (`idea.md`, `research_*.md`): conditional logic on form pages, reusing `form_engine/paging.py` and the `course_applications` shell and check-your-answers page (`research_conditional_logic_models.md:10`, `research_branching_ux_and_accessibility.md:5,306`, `research_answer_lifecycle_and_reporting.md:277`). Touches the same views; no identity change.
- `test-organisation-and-hygene-7-course-access-and-applications/idea.md`: restructures tests that import `course_applications` (the `course_access` tests against the runtime edge, `course_applications`' `learner_progress` import and its conftest helper). **Collision:** it is about to move tests this idea needs to edit (`tests/conftest.py`, `test_views.py`).
- `corporate-job-course-recommendations*` (several ideas and research): registration rules and recommend outcomes; `research_fls_backends_and_toggles.md` documents that `COURSE_ACCESS_BACKEND` selects the application backend and `course_applications` is the existing model of an optional app extending registration. No overlap with identity.
- `test-organisation-and-hygene-12-accounts`, `-13-learner-interface-part-1`, `-4-shared-test-infrastructure`: test restructuring in apps this idea edits.

Done specs worth reading (not in scope of the grep but referenced): `spec_dd/3. done/2026-09-10_09:45_simple-application-forms/` (draft and submit semantics, file upload security, `form_engine` reuse), and `more-prominent-signup-button` (the `acquisition_login_required` routing).

---

## 11. `docs/product/` pages that describe current behaviour and will need updating

- `docs/product/learner-experience.md`
  - `## Summary` (`:5-21`), the paragraph at `:7`: "Login is required only at the committing action (enrolment or application)."
  - `## Course Detail Page` (`:103`), the "Application-gated course, no prior application -> Apply now, which starts an application" and "existing application -> View my application" bullets (`:121-122`).
  - `## Deferred-login Intent Completion` (`:154`): `:156` says an anonymous click on "Apply now" lands on signup or login, and `:159` says after login or signup "the learner lands on the first page of the course's application form, or on the apply confirmation page when the course has no form. The application is not auto-submitted". The core of this section changes for "Apply now".
  - `## Self-Registration` (`:178`), `:182`: "Attempting to do so routes them into the application flow instead."
  - `## Applying to a Course` (`:188`): `:190-210`, the whole section including idempotence (`:200`) and "no review or approval workflow" (`:210`), and the screenshots list.
- `docs/product/roadmap.md`: `## Course Applications` (`:44-57`, status line `:46` and the "Review and approval" bullet `:52`; line `:57` says review "will not require rearchitecting ... the apply flow"); the summary line at `:8`; `## Data Retention, Deletion, and Subject Rights` (`:98-106`), whose `:106` states uploaded application files are kept until deleted by hand or the account is deleted (an unowned draft with files is outside that rule).
- `docs/product/security-and-data-handling.md`: line `:15` (applicant uploads are downloaded only through a permission-checked view), the `applicant uploads` section referenced at `:122`, and the personal-data inventory around `:122-131` (answers and ID scans now held before an account exists).
- `docs/product/admin-interface.md`: `:16` (applications read in the admin by applicant, course, submitted or draft; "nobody can add, edit or delete an application there") and `:90` (the form progress record behind a course application cannot be deleted).
- `docs/product/signup-attribution.md`: `## How It Works` (`:13`) and `## What Is Recorded` (`:19`) if the handoff signup adds any attribution detail.
- `docs/product/webhooks.md` and `docs/product/authentication.md` (`:44`): only if a webhook event or an authentication copy changes.
- `docs/product/configuration-and-extension.md:62`: "the apply flow, its call-to-action, and its dashboard panel all belong to the backend, so switching removes them entirely": an unclaimed-draft expiry job in `deployment` would break "removes them entirely" unless it is guarded.
- `docs/product/multi-tenancy-and-isolation.md:63`: applications "not organisation-scoped"; unclaimed applications are site-scoped only.
- `docs/product/README.md:21`: the Learner Experience row summarises "self-enrolment or application".
- `docs/app_structure.md`: the edge list (`:71-76`, `:84-87`, `:248`, `:251`) if housekeeping or `referral_tracking` gains an edge.
- Screenshots referenced: `learner_course_detail_gated.png`, `learner_apply_confirm.png`, `learner_application_status.png`, `learner_application_check_answers.png`, `learner_application_form_*`, `learner_dashboard_applications.png` (all under `docs/product/screenshots/`).

---

## 12. Quick checklist of authenticated-User assumptions (path:line)

1. `freedom_ls/course_applications/views.py:59` `@acquisition_login_required` on `apply`
2. `freedom_ls/course_applications/views.py:81-83` `cast(User, request.user)`
3. `freedom_ls/course_applications/views.py:39-56` `_start_application(user: User, ...)`
4. `freedom_ls/course_applications/views.py:114,128-132` `@login_required` and `user=request.user` on status
5. `freedom_ls/course_applications/views.py:142-157,183,229` ownership lookup and `@login_required` on form pages and check-answers
6. `freedom_ls/course_applications/views.py:251` submit-success redirect to the authenticated dashboard
7. `freedom_ls/course_applications/models.py:37-41` non-null `user`
8. `freedom_ls/course_applications/models.py:62-67` unique constraint on `(site, user, course)`
9. `freedom_ls/course_applications/models.py:72-82` `is_submitted`
10. `freedom_ls/course_applications/queries.py:31,48` anonymous returns None / empty
11. `freedom_ls/course_applications/backends.py:130-167,201-221` CTA and dashboard branches
12. `freedom_ls/course_applications/admin.py:78,88-93,102,118,147-153` `user` select_related, search, link, columns
13. `freedom_ls/form_engine/models.py:247-249,266,403,680,700` `FormProgress.user` and its uses (storage key at `:700`)
14. `freedom_ls/form_engine/views.py:33-52,79,115,162-174` owner-scoped upload, remove and download
15. `freedom_ls/form_engine/admin.py:264-327,389,428,444-446` user columns and "Applicant"
16. `freedom_ls/learner_interface/views.py:635` dashboard contributions gated on `is_auth`
17. `freedom_ls/base/templates/partials/login_prompt.html:2-9` header links carry only a `next` already in the request
18. `freedom_ls/qa_helpers/management/commands/qa_reset_course_application.py:100-101`, `qa_create_application_review_accounts.py:147-155,181-182` look up by `user`
19. `freedom_ls/deployment/housekeeping.py:221-308` no application sweep; `docs/app_structure.md:251` has no `deployment -> course_applications` edge

---

status: ok
