# Research: asking for help and recommendations from application answers

Read-only research for cutting `idea.md` into specs. Sources: the two ideas named below, `freedom_ls/` code as of 2026-11-19.

## 1. Overlap with the help desk

Source: `spec_dd/1. next/user-communication-help-desk/idea.md`. It is a one-paragraph idea, not yet a spec.

**Shared today: nothing.** The help desk's model, queue and screen are all unbuilt. Only its constraints are written down:

- A shared queue needs its own model, because a `Conversation` (`freedom_ls/comms/models.py`) is always exactly two users, one per pair per site.
- That queue model links to a `Conversation` once an educator picks the request up.
- Educators may reply only to learners they are an educator of (`educators_of`), so `MESSAGING_POLICY` (`freedom_ls/comms/messaging_policy.py`) has to let the picker answer.

**Differences that matter:**

| | Help desk | Applicant help request |
| --- | --- | --- |
| Asker | A signed-in `Learner` | A signed-in user or an anonymous applicant (no `User`, only `AnonymousApplicant`) |
| Anchor | A course content item in the player | A `CourseApplication` plus a requirement or form page |
| Goes to | Educators of that learner | Reviewers of the application's organisation |
| Reply channel | In-app `Conversation` | A person calls the number. No reply thread in FLS |
| Contact data | The `User` | Name, phone, good time to call, typed on the form |
| Lifecycle | Open, picked up, linked to a `Conversation` | Open, then done. No in-app reply |

**Recommendation: share nothing in the models or the queue.** A help-desk ticket's shape (picked up, then a two-person conversation) does not fit an anonymous asker with no `User`, and a call request has no conversation to link. Forcing one model to carry both means a nullable `User`, a nullable `Conversation` and two anchor kinds. Both specs would then wait on each other.

**Two cheap things worth aligning on, with no shared code:**

- Use the same words. Pick "help request" for one and a distinct word for the other, so the glossary does not hold two meanings. The applicant one is a **callback request** or **help request**. The help-desk one should keep "help ticket" (the idea already says "help tickets have to be defined here").
- Whichever ships second can reuse the pattern of the first for the reviewer or educator inbox screen. That is a UI pattern, not a model.

**What a later merge would look like.** If a deployment wants one inbox, a read-only list view that unions both querysets is a small job and needs no shared model.

## 2. Notifications

`freedom_ls/comms/notify.py::raise_notification(user=, category=, target=, site_id=, data=)` takes a `User` recipient only. Categories live in `freedom_ls/base/notification_categories.py` (`FLS_NOTIFICATION_CATEGORIES`: `course.registered`, `course.paused`, `course.resumed`, `deadline.extended`, `bulk_action.finished`). Rules are in `claude_plugins/fls-dev/skills/notifications/SKILL.md`.

**A help request to reviewers: yes, passes the test.**

- Someone else caused it (the applicant, not the reviewer). The recipient is never the actor.
- A person is waiting on a reviewer, so it is time-sensitive with a real cost (an applicant stuck mid-form).
- Nothing already shows it. The Messages badge covers `Conversation` unread only. A help request is not a message, so no "already has an unread signal" exclusion applies.

If it ships, the spec must answer the skill's five checklist questions:

1. The actor is the applicant. A reviewer who also applies (an educator applying for a course) could be both. Skip when recipient equals the applicant's `User`.
2. Without it the reviewer sees the request only on opening the review inbox.
3. They call the applicant. Link to the application's review page.
4. One burst per applicant is plausible (several asks in an hour). Consider `rollup=True`. The skill says no FLS category uses it today but the machinery is tested.
5. In-app only until email delivery backends exist.

Constraints the spec must handle:

- `raise_notification` is per `User`. The recipients are everyone holding the organisation role, so the spec fans out one call per reviewer. How the role is read depends on `application-review-ui`, which has no spec yet (`spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md`).
- The category's `url_builder` lives in a module that must import from `educator_interface` or `course_applications`. Check import direction against `comms`.
- With no reviewers (nobody holds the role), the request must still be stored and still fire the signal or webhook.

**Application events generally:**

| Event | Notify? | Reason |
| --- | --- | --- |
| Applicant submits | Reviewers: probably yes, but gets a review inbox with its own count. The inbox is the "already visible" surface once it exists. Decide in `application-review-ui` | Applicant is the actor, reviewers are not |
| Verdict (accepted, turned down) | Applicant: yes if they have a `User`. An anonymous applicant gets email through the existing claim flow instead | A reviewer acted. The applicant may not be on the page |
| Application approved | Applicant: yes, same reason. Not a duplicate of a registration notification: approval happens before registration | A reviewer acted |
| Approved, then `course.registered` | Do not raise a second one. The existing `course.registered` already fires for registrations created by someone else. Check that the approval path does not double-notify | One event, one notification |
| Applicant's own save, reopen, upload | No | They did it |
| Requirement superseded by the resolver | No, unless it adds work for the applicant. The requirements page shows it | Page is the feedback |

Anonymous applicants cannot receive in-app notifications at all (no `User`). Anything they must hear goes by email through the claim-link path in `freedom_ls/course_applications/claims.py`. That is a separate decision from the bell.

## 3. Webhooks, course interest, lead capture

**How event types are declared:** a list of `(value, label)` pairs, `FLS_WEBHOOK_EVENT_TYPES` in `freedom_ls/base/webhook_event_types.py`, read through `freedom_ls/webhooks/config.py` (`WEBHOOK_EVENT_TYPES` setting). It sits outside the app registry so settings can import it. `WEBHOOK_EVENT_TYPE_SAMPLES` in the same file holds a sample payload per type, used for test sends. `freedom_ls/webhooks/registry.py::validate_event_type` raises `ValueError` on an unknown type.

**How events fire:** `freedom_ls/webhooks/events.py::fire_webhook_event(event_type, payload, site=None)` takes the site from the request thread-local, or from the caller. With neither it drops the event. `fire_webhook_event_for_site` writes a `WebhookEvent`, then enqueues `dispatch_event`, which creates a `WebhookDelivery` per active, subscribed `WebhookEndpoint` for the site. `freedom_ls/learner_management/utils.py::fire_webhook_event_on_commit` is the helper most callers use. Callers do not use a Django signal. They call the function directly.

**Course applications today have no webhook event types.** The `apis-for-lead-monitoring-*` specs gave `CourseApplication` a polled API only: `GET /api/v1/course-applications/` with `updated_since`, scope `course_applications` (`freedom_ls/course_applications/api.py`). `freedom_ls/course_applications/receivers.py` touches `updated_at` on sitting, answer, file and applicant saves so pollers see changes. A `CourseApplication` change is therefore visible to polling CRMs, but a help request would not be, unless the request also touches `CourseApplication.updated_at` or the API gains a help-request endpoint.

**Recommendation for the signal or webhook:** the idea says "a signal or webhook". Do the webhook. It is the house pattern and a deployment already configures endpoints in the admin.

- Add `application.help_requested` to `FLS_WEBHOOK_EVENT_TYPES` and a sample to `WEBHOOK_EVENT_TYPE_SAMPLES`.
- Payload: application id, course id and title, organisation id, applicant email and name, phone (E.164), good time, question text, anchor (requirement id or form page), and whether the applicant had an account. No new Django `Signal` is needed. If a deployment wants an in-process hook, add one signal as a second call, not as the main mechanism.
- Fire through `fire_webhook_event_on_commit`. That helper lives in `learner_management`, so `course_applications` would import it or the spec moves the helper. Check `course_applications`' existing imports first.
- A request from an anonymous applicant has a request context and a site, so the thread-local lookup works. Pass `site` explicitly anyway.
- The payload carries a phone number and free text. Note that in the webhook docs. Webhook payloads here already carry `user_email`.

**`freedom_ls/course_interest`:** `CourseInterest` (`freedom_ls/course_interest/models.py`) is a `User` and a `Course` and two timestamps. No phone number, no free text, no anonymous path. Nothing to reuse.

**`lead-capture-forms`** (`spec_dd/1. next/lead-capture-forms/idea.md`): an idea only, not built. It describes public enquiry, "talk to us" and callback forms: a stored submission with its form, answers and first-touch attribution, a staff email per lead, a CSV export. A callback form with a phone and contact method there overlaps with ours in concept (a person who wants a call). Differences: it is not tied to a `CourseApplication`, has no reviewer routing, and uses configuration-defined fields. **Recommendation:** do not wait for it and do not build on it. Keep the applicant help request on its own small model. Note in both specs that a deployment may want one export or CRM feed for both, and that the webhook payload shape of ours should not conflict with it. First-Class-LMS `apps/lead_forms/` (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`) is the reference for the CSV-safe export and the notification email task, if either is wanted. The idea does not ask for either here.

## 4. Phone number form field

Done spec: `spec_dd/3. done/2026-11-12_16:29_phone-number-form-field/1. spec.md`. Code: `freedom_ls/form_engine/phone_numbers.py` exists and is built.

**What a non-form_engine Django form gets: the Python helpers, not a form field.**

- `phone_answer_error(text, country) -> str | None`: validation with the spec's messages. Usable in a `clean_phone` method.
- `e164_phone_answer(text, country)`: the E.164 string to store.
- `country_choices()`: `(code, "South Africa (+27)")` pairs for a `ChoiceField`.
- `browser_country(accept_language)`: preselect from `request.headers["Accept-Language"]`.
- `phone_example(country)` and `phone_examples()`: hint text.
- `display_phone`, `phone_after_calling_code`, `stored_phone_country`: show and refill a stored number.

The module imports no models, and the spec says form_engine must not import `course_applications`, so the dependency runs the right way: `course_applications` may import `form_engine.phone_numbers`.

**What it does not give:**

- No `forms.Field` or widget. The picker plus number input markup is in `form_engine/templates/form_engine/inputs/phone_input.html`, tied to `question_<id>` and `phone_country_<id>` names and to `phone_field_state` (a template tag taking a form_engine question). A plain form would need its own template, or the spec extracts the markup.
- The phone spec explicitly scopes out "the course-applications applicant-details step (a plain Django form)". The help form is the same kind of form, so the same gap applies.
- No model field. Store the E.164 in a `CharField` on the help request.

**Recommendation:** the help-request spec should say how it renders the field. Options:

1. Write a small `PhoneNumberField` and widget in `form_engine` (or `base`) that wraps these helpers and the existing template. Cleanest. The spec is bounded.
2. Duplicate the template into `course_applications`. Cheaper but repeats code, against the project convention.

Option 1 is better. It is also useful for any later plain form. Count it as part of the help-request spec's size.

The `phone-number-form-field` spec says `multi-step-course-applications` was blocked on it. That block is lifted.

## 5. Recommendations

**`RecommendedCourse`** (`freedom_ls/course_recommendations/models.py`): `user` FK, `course` FK, `created_at`. Unique on `(site, user, course)`. A commented-out `form_progress` FK remains in the file. No source, ranking, reason or expiry (decision from the recommend-outcome spec). It is keyed on `User`, not `Learner`.

**Where rows are produced today:**

- Staff in the Django admin (`course_recommendations/admin.py`), and QA commands.
- The recommend outcome of registration rules (`freedom_ls/registration_rules/`): a `RegistrationRule` with `outcome="recommend"`, evaluated in `evaluation.py`, scheduled by `signals.py` and `tasks.py`. Provenance is `RuleRecommendation` in `registration_rules/models.py`. A recommendation with a `RuleRecommendation` is rule-made. One with none is staff-made and rules never touch it. Deleting the last `RuleRecommendation` deletes the `RecommendedCourse`.
- `freedom_ls/course_recommendations/queries.py::clear_registered_recommendations` deletes recommendations for courses the user is registered for, "whoever made them". This applies to a producer from application answers too.

**Is there a pluggable producer seam? No, not for recommendations.**

- `registration_rules/loader.py::get_rule_kind` plus `REGISTRATION_RULE_KINDS` is a pluggable seam, but for rule kinds. `AttributeRuleKind.matching_learners(state)` (`registration_rules/kinds.py`) returns a `QuerySet[Learner]`. It decides who matches from HR attributes (job title, department, location) and is keyed on `Learner` and organisation.
- The registration-rules engine runs from learner and attribute changes. It does not know of application answers or of applicants who are not yet `Learner`s.
- `course_recommendations` has no producer setting, no loader and no `*Decision`. The idea says "the same seam as the resolver", meaning the house pattern (`COURSE_ACCESS_BACKEND`, `MESSAGING_POLICY`: loader, return value, boot-time check, conformance tests). That seam does not exist yet for recommendations. **This spec must create it**, so it is larger than the idea suggests.

**Reuse or new seam?** Two choices for the spec:

1. A new setting such as `APPLICATION_RECOMMENDER` in `course_applications` (or `course_recommendations`), naming a class with one method taking the application and returning the courses to recommend. FLS reconciles the result against `RecommendedCourse` rows. Matches the resolver pattern and does not touch registration rules. Recommended.
2. A new rule kind in `registration_rules`. Does not fit: kinds select `Learner`s by HR attributes, per organisation, with a rule model and admin. An applicant is often not a `Learner`.

**What a producer reading application answers needs:**

- The `CourseApplication` (it gives `user`, `anonymous_applicant`, `form_progress`, `course`). The producer reads the answers from `form_progress`, as the lead-monitoring API does.
- A `User` to attach rows to. `RecommendedCourse.user` is not nullable. **An anonymous applicant has no `User`, so no row can exist.** Rows can only be made once the application has a `user`: signed in at start, or after the claim link is followed (`claims.attach_to_user` in `freedom_ls/course_applications/claims.py`, `adopt_anonymous_applications_on_login` in `receivers.py`). The spec must say: recompute when the application gains a `user`. Making `user` nullable on `RecommendedCourse` is a bigger change that touches the dashboard and the clear logic, so avoid it.
- A learner need not exist. Nothing in `RecommendedCourse` or `get_recommended_courses(user)` requires a `Learner`, so this works. The dashboard section is filtered by `CourseAccessBackend.filter_visible` (`freedom_ls/learner_interface/views.py::_visible_recommendations`), which is what hides non-visible courses.
- A re-run trigger: a signal on answer save, on the application gaining a `user`, and on review events if the producer reads verdicts. `receivers.py` already has `touch_application_on_answer_change`, a place to hang this. Run it as a task after commit, like registration rules.
- Ownership for reconcile. When an applicant changes "e-learning" to "in-person", the producer's earlier rows must go and new ones appear, but staff-made and rule-made rows for the same user must stay. The registration-rules approach (`RuleRecommendation` per rule) shows the problem. The new producer needs its own provenance row (for example `ApplicationRecommendation(application, recommendation)`), or a source field on `RecommendedCourse`. The recommend-outcome spec rejected adding a source field there (decision 3 and "carries no source"), so a provenance table in `course_applications` is the consistent option, with `course_recommendations` gaining no new dependency. If a rule and the application producer both recommend the same course, the shared row must survive until the last holder lets go. That is the same many-owners rule the recommend-outcome spec settled.
- The unregistered check. `clear_registered_recommendations` removes a recommendation once the user registers. The producer must not re-add one for a course the user is registered for. Reuse `registered_course_pairs` (`freedom_ls/learner_management/queries.py`).
- Site and organisation: `RecommendedCourse` is site-aware but has no organisation. Fine.

**Where the learner sees recommendations:** the dashboard, "Recommended courses" section, in `freedom_ls/learner_interface/views.py` (`_visible_recommendations`, `_recommended_section`, around lines 248 and 477) and `dashboard_sections.py`. Paginated. A signed-in applicant who is not registered sees it there. An applicant with no `User` sees nothing, so the application pages themselves may need to show "courses we suggest for you". That is a UI decision the spec must make explicitly. The idea does not ask for it.

## 6. Size and dependencies

**Help requests can ship before application requirements exist.**

- Anchor to the `CourseApplication` plus a free-form "where they were" (form page identifier, or a requirement reference). Store the anchor as a nullable FK to the requirement later, or as a short string and URL now. A string is lighter but loses referential meaning. Prefer: `application` FK, a `page` description (form page number or name) and a nullable `requirement` FK added in the requirements spec by migration. The idea says "do not architect these away", and the house style (see `CourseApplication` docstring) is additive.
- Needs from earlier specs:
  - A reviewer set per application's organisation: `application-review-ui` (state machine, organisation role reviewers, default organisation via `get_default_organisation`). `CourseApplication` has no organisation field today. **Without it, there are no "reviewers of the application's organisation" to route to.** This is the real dependency. If help requests ship first, the fallback is the site's default organisation and its role holders, or site staff, and the spec has to state it. Better to order it after step 1 of the idea's order, as the idea already does.
  - A reviewer screen. Without `application-review-ui`'s inbox, a help-request list would be a standalone screen or the Django admin only. The admin is acceptable as a first cut but the spec should say so.
- Does not need `form-engine-branch-logic` or the requirements work. The form page anchor works on any form page.
- Add: the field helpers (section 4), a webhook type (section 3), optionally a notification category (section 2), and abuse protection for anonymous posts. The existing `honeypot_field()` and `reject_honeypot` in `freedom_ls/accounts/forms.py` (used by `ApplicantEmailForm`) and a rate limit like the claim-email one give a pattern.
- Medium size on its own, assuming the field helper is a small extraction.

**Recommendations can ship independently of review states and requirements.**

- It reads form answers only. Answers exist now (`form_progress`, `QuestionAnswer`). The idea's study-mode question is just a form question, so branch logic is not needed.
- It does not depend on application states or the resolver. If the producer is to read reviewer verdicts later, add that then. Design the producer's input as "the application", so it can read more as the application grows.
- Hard dependencies are the three things above: the new producer seam (section 5), a provenance row for the many-owners rule, and the `User` limit for anonymous applicants. The last one is the main product risk: an anonymous applicant sees no recommendations until claiming.
- Medium size, and larger than help requests because the seam and provenance are new. A first cut limited to signed-in applicants and the claimed case, with the "applicant gains a user" trigger, is a sensible boundary.
- Order between the two does not matter. Neither needs the other. Help requests need application-review's organisation and reviewer role, and recommendations need nothing from the idea's earlier steps.

## References

- `spec_dd/1. next/multi-step-course-applications/idea.md`
- `spec_dd/1. next/user-communication-help-desk/idea.md`
- `spec_dd/1. next/lead-capture-forms/idea.md`
- `spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md`
- `spec_dd/3. done/2026-11-12_16:29_phone-number-form-field/1. spec.md`
- `spec_dd/3. done/2026-10-25_21:23_corporate-job-course-recommendations-3-recommend-outcome/1. spec.md`
- `spec_dd/3. done/2026-11-05_12:26_apis-for-lead-monitoring-2-course-applications/1. spec.md`
- `claude_plugins/fls-dev/skills/notifications/SKILL.md`
- `freedom_ls/webhooks/events.py`, `freedom_ls/base/webhook_event_types.py`
- `freedom_ls/comms/notify.py`, `freedom_ls/base/notification_categories.py`
- `freedom_ls/form_engine/phone_numbers.py`
- `freedom_ls/course_recommendations/models.py`, `freedom_ls/course_recommendations/queries.py`
- `freedom_ls/registration_rules/loader.py`, `freedom_ls/registration_rules/kinds.py`, `freedom_ls/registration_rules/evaluation.py`
- `freedom_ls/course_applications/models.py`, `freedom_ls/course_applications/receivers.py`, `freedom_ls/course_applications/forms.py`
- `freedom_ls/learner_interface/views.py`

status: ok
