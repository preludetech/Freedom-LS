# Research: how course applications and signup work today

Codebase-only research. Paths are relative to the repo root. Vocabulary follows the project glossary: Learner, Course, Form, FormProgress (a Form Attempt / sitting), CourseApplication, Site, SiteSignupPolicy, LegalConsent, Registration form.

## 1. The apply flow today

### URLs (`freedom_ls/course_applications/urls.py`, `app_name = "course_applications"`)
- `apply/<slug:course_slug>/` -> `views.apply` (name `apply`)
- `status/<uuid:pk>/` -> `application_status` (`status`)
- `application/<uuid:pk>/page/<int:page_number>/` -> `application_form_page` (`form_page`)
- `application/<uuid:pk>/check-your-answers/` -> `application_check_answers` (`check_answers`)

Every application URL beyond `apply` is keyed on the CourseApplication pk (a UUID) and is owned-by-`request.user`.

### Decorators
- `apply` uses `@acquisition_login_required` (see section 2).
- `application_status`, `application_form_page` and `application_check_answers` use plain `@login_required`. They read `request.user` directly: `get_object_or_404(CourseApplication..., pk=pk, user=request.user)` in `_owned_application_with_form` and `application_status`.

### `apply` (views.py)
Order of checks:
1. `get_object_or_404(Course, slug=...)`.
2. `raise_404_if_hidden_unregistered(user, course)` (`course_access/visibility.py`): hidden Courses 404 for unregistered users.
3. `get_application_for_course(user=user, course=course)` (`course_applications/queries.py`). If one exists, redirect to `course_applications:status`. This helper returns `None` for an anonymous user without querying.
4. Coming-soon Courses redirect to `learner_interface:course_detail` (express-interest CTA).
5. If `course.application_form is not None` or the request is a POST: `_start_application(user, course)`. That does `CourseApplication.objects.get_or_create(user=user, course=course)` inside `transaction.atomic()`, then, for a Course that names a form, creates `FormProgress.objects.create(user=user, form=course.application_form)` and saves it to `app.form_progress`. Then:
   - if there is a sitting: redirect to `_resume_url` (the first or resume form page, or `check_answers` if the Form has no pages). GET is enough to start (the CTA is a plain link).
   - if there is no sitting (form-less Course): `record_application_submitted(request, course)` and redirect to status.
6. Otherwise (form-less Course, GET) render `apply.html` (the "Apply to <course>?" confirmation). Confirming is a POST.

### Models that require a non-null user
- `CourseApplication` (`course_applications/models.py`, a `SiteAwareModel`): `user` FK to `AUTH_USER_MODEL`, NOT NULL, `on_delete=CASCADE`. `course` FK NOT NULL. `form_progress` is a nullable `OneToOneField` to `form_engine.FormProgress` (`on_delete=RESTRICT`, `related_name="course_application"`). Unique constraint `unique_application_per_site_user_course` on (site, user, course). `is_submitted` is true when there is no sitting or `form_progress.completed_time` is set.
- `form_engine.FormProgress` (`form_engine/models.py` ~line 239, `SiteAwareModel`): `user = ForeignKey(User, on_delete=CASCADE, related_name="form_progress")`, NOT NULL. The Form FK is PROTECT. `FormProgress.complete()` sends `form_attempt_completed` with `user=self.user`.
- `QuestionAnswer` rows hang off `form_progress`. The answer file upload path is `user_uploads/{form_progress.user_id}/form_answers/...` (`form_engine/models.py` ~line 700), so uploads also assume a user id.
- `LegalConsent.user` and `SignupAttribution.user` are also required, but those are created at signup (section 3).

So today a draft application, its sitting, its answers and any uploads all need an existing `accounts.User`. Nothing in the application stack is anonymous-capable.

### The application form as a form_engine Form
- The Course names its application Form via `Course.application_form` (bound by the content loader from the FORM file named in `access_config["application_form"]`; see `ApplicationCourseAccessBackend.validate_course_config` in `course_applications/backends.py`). The applicant's own sitting is `CourseApplication.form_progress`, and the form is read back from that sitting (`form_progress.form`).
- The Form is content-authored: pages (`FormPage`) contain `FormQuestion`s and `FormContent` blocks. Question types include short_text, long_text, number, date, time, email, url, phone, multiple_choice, checkboxes, dropdown, file_upload. The form_engine can validate typed answers (`typed_answers.py`; a bad answer is a `RejectedAnswer` and nothing is stored).
- The signup fields (email, name) are NOT form_engine questions today. Signup is an allauth `SignupForm` (Django `forms.Form`).

### Page flow
- `form_engine/page_flow.py`: `resolve_page` (404 on a bad number), `submit_page(current, request.POST, form_progress)` (saves answers via `FormProgress.save_answers`, reports required/rejected errors in a `PageSubmission`), `page_context(...)` (context keys: `form`, `form_page`, `form_progress`, `current_page_num`, `total_pages`, `previous_page_url`, `next_page_url`, `has_next_page`, `read_only`, `existing_answers`, `page_links`, `required_answers_error`, `rejected_answers*`), `render_form_page` (422 on a refused submission, `Cache-Control: no-store`).
- `form_engine/paging.py`: `resume_page_number`, `build_page_links` (the page-jump nav), `unanswered_required_in_form`, `unanswered_required_message`.
- Pages are numbered 1..N by position (`form.pages.all()`); `url_for_page` is supplied by the caller. The view's `RETURN_TO_CHECK = "check"` query marker (`?return=check`) makes an edit from check-your-answers save and go straight back there.
- `application_form_page`: POST accepted -> next page (or check-answers on the last page / when `return=check`). GET calls `form_progress.record_page_reached(page_number)` unless the sitting is read-only (completed). `furthest_page_reached` feeds `resume_page_number`.
- Page numbers are positional and used in the URL, in `build_page_links`, in `furthest_page_reached`, and in the check-answers `sections` (numbered with `enumerate(form.pages.all(), start=1)`). An extra "step" that is not a `FormPage` would not appear in any of those without special handling.

### Check-your-answers and status
- `application_check_answers`: a POST not yet submitted runs `unanswered_required_in_form(form_progress)`; if none: `form_progress.complete()`, `record_application_submitted(request, app.course)`, a `messages.success`, and redirect to `learner_interface:dashboard`. Otherwise 422 with `required_answers_error`. A repeat POST on a submitted application redirects to status. GET builds one card per page with an Edit link (`?return=check`).
- `application_status`: if the sitting is unfinished, it redirects back to `_resume_url`; else renders `application_status.html` (static "received, pending review").
- Submission is a deliberate action: the application is not submitted on creation when a Form exists; it is submitted from check-your-answers.

### Templates (`course_applications/templates/course_applications/`)
`apply.html`, `form_page.html`, `check_your_answers.html`, `application_status.html`, `partials/dashboard_applications.html`.
`form_page.html` extends `_base.html`, loads `form_engine/js/alpine-components.js`, wraps in `<c-page width="narrow">`, and renders: "Application for {{ course.title }}", `<h1>{{ form_page.title }}</h1>`, a `<nav>` of `<c-form-page-link>` (from `page_links`), optional `<c-callout>` when read-only, `{% include "form_engine/partials/answer_errors.html" %}`, then `<form method="post">` with `{% csrf_token %}` and `{% include "form_engine/partials/page_children.html" %}`, then Previous / Next `<c-button>`s (flex, back left, forward right, stacked on mobile).
`page_children.html` loops `form_page.children`: `FORM_QUESTION` -> `form_engine/question.html` (a `<fieldset>` with a numbered `<legend>`, a required asterisk, and a type-specific include under `form_engine/inputs/`, for example `text_input.html` for short_text, email, phone etc.); `FORM_CONTENT` -> `<c-markdown-container>`. Inputs are named `question_<uuid>` and styled with fixed Tailwind classes (`rounded-md border border-border bg-white ...`). Existing answers and rejected text prefill via `existing_answers` / `rejected_answers` context. "Same widgets as the application form pages" therefore means the `form_engine/inputs/*.html` includes driven by a `FormQuestion`, not Django form widgets.
The signup page (`base/templates/account/signup.html`) is different: it uses allauth's `{% element form %}`, renders `{{ field.label_tag }} {{ field }}` per Django field, and has its own consent checkbox markup. It does not share widgets with the application pages.

### Dashboard and access backend
`ApplicationCourseAccessBackend` (`course_applications/backends.py`, the default `COURSE_ACCESS_BACKEND`) returns the CTA: "Apply now" -> `course_applications:apply` for an unregistered visitor on an `application_gated` Course; "View my application" -> status when `get_application_for_course` finds one. `get_access` accepts an anonymous user (`get_application_for_course` returns None for them), so the anonymous CTA already works. `get_dashboard_contributions` lists in-flight applications for an authenticated user (empty for anonymous).

## 2. `acquisition_login_required` (`freedom_ls/accounts/decorators.py`)

- Authenticated: the view runs unchanged.
- Anonymous: `redirect_to_auth(request, next_url=request.get_full_path(), auth_url=acquisition_auth_url(request))` (`accounts/utils.py`).
- `acquisition_auth_url`: `reverse("account_signup")` while `get_adapter(request).is_open_for_signup(request)` is true (per-site `SiteSignupPolicy.allow_signups`, falling back to `ALLOW_SIGN_UPS`); otherwise `None`, which `redirect_to_auth` resolves to `settings.LOGIN_URL` (login).
- `redirect_to_auth` builds the target with `django.contrib.auth.views.redirect_to_login(next_url, auth_url)`, so the URL is `/accounts/signup/?next=/<apply path>`. For an htmx request it returns 204 with `HX-Redirect`. `next_url` is built server side from `request.get_full_path()`.
- After signup the `next` (the apply URL) is carried through the allauth signup form's `redirect_field`, through mandatory email verification, and through any additional registration forms; the destination is validated as same-host (`accounts/views.py::_safe_post_completion_redirect` uses `url_has_allowed_host_and_scheme`). Documented in `docs/product/authentication.md` ("Intended destination is preserved") and `docs/product/learner-experience.md` ("Deferred-login Intent Completion": "Apply now" lands on the first form page after login or signup).
- Related: `course_interest/views.py` (express interest) uses the same `acquisition_auth_url` + `redirect_to_auth` pattern for its anonymous POST.
- Net: today an anonymous applicant is sent to the full allauth signup page (password, consent boxes) and must verify their email before they are logged in and returned to apply. That detour is the derailment the idea describes.

## 3. Signup today

### Settings (`config/settings_base.py`, ~lines 417-470)
- `ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "first_name*", "last_name"]`
- `ACCOUNT_LOGIN_METHODS = {"email"}`; `ACCOUNT_USER_MODEL_USERNAME_FIELD = None`
- `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`; `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` (confirming the link logs the user in); `ACCOUNT_LOGIN_ON_PASSWORD_RESET = True`
- `ACCOUNT_ADAPTER = "freedom_ls.accounts.allauth_account_adapter.AccountAdapter"`; `ACCOUNT_FORMS = {"signup": "freedom_ls.accounts.forms.SiteAwareSignupForm"}`
- `ACCOUNT_PREVENT_ENUMERATION = True` (responses do not reveal whether an email is registered)
- `ACCOUNT_RATE_LIMITS = {"signup": "5/m/ip", "login_failed": "10/m/ip,5/5m/key"}` (off in dev). The comment notes `signup` cannot carry a `key` rate.
- `ALLOW_SIGN_UPS = True`, `REQUIRE_TERMS_ACCEPTANCE = False` (True in `settings_dev.py`), `REQUIRE_NAME = True`, `ADDITIONAL_REGISTRATION_FORMS = []`, `LOGIN_REDIRECT_URL = "/"`.
- No passwordless / login-by-code settings, no socialaccount, and allauth headless is commented out (`config/urls.py`). Passwords are always set at signup; 10-character minimum, Argon2 (relaxed validators in dev).

### `SiteAwareSignupForm` (`accounts/forms.py`, extends allauth `SignupForm`)
Fields: email, password1, password2 (from allauth), `first_name` (required unless `get_effective_require_name(policy)` is false), `last_name` (optional), `fax_number` honeypot (`HoneypotInput`, hidden; a filled value adds a non-field error and logs a warning with the IP), and, when `get_effective_require_terms_acceptance(policy)` is true and the doc resolves (`has_legal_doc(site, "terms"|"privacy")`), required `accept_terms` / `accept_privacy` BooleanFields. Outside a request it raises `RuntimeError` when consent is in play (fail closed). `custom_signup(request, user)` writes one `LegalConsent` per ticked box inside `transaction.atomic()` using `get_legal_doc(site, ...)` (version and git blob hash) and `get_client_ip(request)` (`consent_method="signup_checkbox"`).

### `SiteSignupPolicy` (`accounts/models.py`, one row per Site, `SiteAwareModel`)
`allow_signups`, `require_name`, `require_terms_acceptance`, `additional_registration_forms` (JSON list of dotted paths). Helpers in `accounts/utils.py`: `get_signup_policy_for_request`, `get_effective_require_name`, `get_effective_require_terms_acceptance`, `get_effective_additional_registration_forms`. These read through `_base_manager` to avoid the ambient thread-local site filter. Fallbacks come from `accounts/config.py` (`config.REQUIRE_NAME` etc.). See `claude_plugins/fls-dev/skills/registration/SKILL.md`.

### Legal consent / legal_docs
`legal_docs/_default/{terms,privacy}.md` (or `legal_docs/<site_domain>/`), read from the git blob at HEAD with YAML frontmatter. `LegalConsent` (`SiteAwareModel`) is append-only (`save()` raises on update; admin read-only), with `user` NOT NULL. Consent is bound to the User, not the email address. The signup template renders the checkboxes with links to `accounts:legal_doc`.

### Post-verification registration forms
`ADDITIONAL_REGISTRATION_FORMS` / `SiteSignupPolicy.additional_registration_forms`: `forms.Form` subclasses with `applies_to(user)`, `is_complete(user)`, `save(user)`; fields named `user`, `user_id`, `email` forbidden. `RegistrationCompletionMiddleware` (`accounts/middleware.py`) redirects any authenticated non-superuser with an incomplete form to `accounts:complete_registration` (with `next`), caches completion in the session, and exempts allauth URLs, static/media, and the legal doc and completion URLs. It only acts on authenticated users, so it never touches an anonymous request. `complete_registration_view` is `@login_required` and passes `request.user` to `save`. These forms are NOT asked at signup, only after verification and login.

### How a user is created and site-scoped
- allauth's signup view builds the user via the adapter (`AccountAdapter.save_user`), which calls `super().save_user` and then (if committed) fires the `user.registered` webhook (`freedom_ls.webhooks.events.fire_webhook_event`) and `record_sign_up(request)` (`base/analytics_events.py`, GA/pixel analytics event queued in the session).
- `User` (`accounts/models.py`) is `SiteAwareModelBase` (integer pk, `site` FK PROTECT), `email = EmailField(unique=True)` (globally unique despite the docs saying the same email can exist on two Sites; this is a real mismatch to be aware of), `first_name`/`last_name` default `""`. `site` is set in `SiteAwareModelBase.save()` from the thread-local request via `get_cached_site(request)`.
- `UserManager.create_user(email, password=None, ...)` raises `ValueError("User must have a password")` when no password is given. So the manager cannot create a passwordless user today (see section 5). The manager's `get_queryset` also filters by the ambient request site.
- Signup attribution: `referral_tracking/signals.py` listens to allauth's `user_signed_up` and calls `record_signup_attribution(request=request, user=user, client_ip=...)` (`referral_tracking/capture.py`), writing a `SignupAttribution` row (cookie `fls_attribution` first touch; "direct"/"none" when there is no cookie; best-effort, a `DatabaseError` is sent to Sentry). `docs/product/signup-attribution.md`: an account created any other way (admin, management command, import) gets no record; confirming the email later does not change it. A user created outside allauth's signup view therefore has no attribution unless the code sends/calls `user_signed_up` or the capture function itself.
- Email verification: mandatory. A user cannot log in until the link is followed; following it logs them in (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION`). Docs: `docs/product/authentication.md`.

## 4. Other things hanging off signup or application submit

- Analytics events: `record_sign_up(request)` is fired from `AccountAdapter.save_user`. `record_application_submitted(request, course)` (`course_access/analytics_events.py`, via `_record_course_access_requested(request, course, "application")`) is fired on submit: from `apply` for a form-less Course, and from `application_check_answers` POST. Events are session-queued (`ANALYTICS_EVENTS_SESSION_KEY`), popped by a context processor, and rendered by the Google Tag / Meta Pixel / TikTok Pixel apps' templates. They need `request.session`.
- Referral attribution: as above, only fires on `user_signed_up`. The attribution cookie is read from the request that signs up, so the request that creates the account needs the cookie.
- Webhooks: `user.registered` fired from `AccountAdapter.save_user` (payload user_id, email, names). I found no application-submitted webhook in `course_applications`.
- `form_attempt_completed` signal (sent by `FormProgress.complete()`): the receiver in `learner_progress/signals.py` (`recalculate_course_progress_on_form_attempt`) uses the user and form; it matters for the sitting's completion, not signup.
- Course access: `ApplicationCourseAccessBackend` (see section 1); admin/cohort enrolment bypasses the gate. `is_registered_for_course(user, course)` is used by `get_access` and is fine for an anonymous user per the existing CTA.
- Notifications: I did not find notifications wired to application submission in `course_applications` (no app-specific notification code there). Signup/verification emails go through `AccountAdapter.send_mail` (branded, 8bit encoding).
- Email templates and rate limiting: the signup rate limit is allauth's, attached to its signup view only (`rate_limit(action="signup")`), so a custom view would not inherit it.

## 5. Site-aware constraints relevant to creating a user without a password

- `SiteAwareModel` / `SiteAwareModelBase` (`site_aware_models/models.py`): `site` FK PROTECT; `save()` and `full_clean()` fill `site` from the thread-local request (`_thread_locals.request` via `get_cached_site`) if not set; an unresolved Host (`UnknownSite`) leaves `site` unset and the save fails with a NOT NULL error. `SiteAwareManager` filters by the same ambient site, so queries only see the current Site's rows. CourseApplication, FormProgress, QuestionAnswer, LegalConsent and SiteSignupPolicy are SiteAwareModels; `FormProgress.save_answers` passes `site=self.site` explicitly.
- `User.email` is unique globally (`unique=True`), while `UserManager.get_queryset` filters by site. A lookup for "does this email already exist" through `User.objects` only sees the current Site, but a create of an email that exists on another Site would hit the unique constraint. Treat this as an uncertainty to confirm during design.
- `UserManager.create_user` refuses an empty password, so a passwordless user would need `set_unusable_password()` through a different path (for example `User(...)` + `save()`), which is not something the current code does anywhere I looked. allauth itself creates users via `adapter.new_user` / `save_user` and requires `password1` per `ACCOUNT_SIGNUP_FIELDS`.
- An unusable-password user can only get in through email verification (login-on-confirmation) or password reset; there is no login-by-code.

## 6. Tension points the idea will hit

1. FormProgress and CourseApplication need a user. An anonymous visitor has no `User` row, so there is nowhere to store the in-progress application or its answers (and uploads key on `user_id`) until a user exists. Whatever the first (identity) step collects has to either create the User first or be held somewhere else until submit.
2. The extra step is not a `FormPage`. Page numbering is positional across URLs, `build_page_links`, `furthest_page_reached`, `resume_page_number`, and check-your-answers sections. An identity step ahead of page 1 interacts with all of these ("Previous" on page 1, resume URL, the Edit links, nav).
3. Widgets: the application pages render `FormQuestion` objects through `form_engine/inputs/*.html` (`question_<uuid>` names, answers stored as `QuestionAnswer`). Signup fields are a Django/allauth form with its own markup. Making the identity step look and behave the same requires rendering the signup fields through those input includes (or expressing the fields as questions), and the validation (email format, required names) lives in `SiteAwareSignupForm`/allauth, not in `typed_answers`.
4. "Whatever we would usually ask for on registration, except a password" is policy driven: `SiteSignupPolicy.require_name`, `require_terms_acceptance` (T&C / Privacy checkboxes with `LegalConsent` rows, which require a user and the client IP), the honeypot, plus `ADDITIONAL_REGISTRATION_FORMS` (which today run only after verification, for authenticated users, and may forbid an `email` field). Dropping consent from the anonymous path would diverge from the policy; keeping it means recording `LegalConsent` for a user created outside allauth's `custom_signup`.
5. Email verification is mandatory. A User created without a password and without a verified email can't log in; allauth's "mandatory" setting normally blocks login until verification, and `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` logs them in only after the link is followed. The anonymous applicant needs to remain in the session through the form, and whether the submission waits on verification is open. `RegistrationCompletionMiddleware` and `@login_required` on the page, check and status views all require an authenticated session.
6. Email already registered. `User.email` is globally unique; `ACCOUNT_PREVENT_ENUMERATION = True` deliberately hides which emails have accounts. An anonymous applicant who types an email that has an account (possibly a verified one with a password) cannot silently be given that user's session or application (account takeover / enumeration risk), yet the unique constraint blocks a second row. The unique constraint on CourseApplication (site, user, course) and the existing "already applied -> status" redirect also leak whether that email applied.
7. Passwordless user creation: `UserManager.create_user` demands a password; allauth requires `password1`. A user with an unusable password needs a way in later (password reset or the emailed verification link).
8. Side effects of the allauth signup that a bypass would lose unless re-created: `user.registered` webhook, `record_sign_up` analytics event, `SignupAttribution` (from `user_signed_up`), `LegalConsent`, honeypot, rate limit (`5/m/ip` attached only to allauth's view), verification email, `RegistrationCompletionMiddleware` gating afterwards. Each is wired to allauth's signup view/signals, not to user creation.
9. `apply` currently flows through `acquisition_login_required`, which is shared with enrol-for-free (and the same pattern is in `course_interest`). Any change that lets anonymous users into `apply` must leave the authenticated path and the other acquisition CTAs untouched (requirement 1: authenticated behaviour exactly as now).
10. Where the anonymous user lands afterwards: submission redirects to `learner_interface:dashboard` (login required), and `application_status` is login required.

status: ok
