---
name: reference-application-forms-qa-baseline
description: The whole-run "set the dev DB up for a simple-application-forms frontend QA pass" recipe — four commands plus one enrolment script, what each covers, and why a re-run usually deletes nothing
metadata:
  type: reference
---

Asked Sep 2026 on `simple-application-forms` as a single seven-item end-state spec. It is the
union of three earlier one-fixture asks, so run the existing commands rather than scripting it
by hand. DemoDev is Site **id 3, domain `127.0.0.1:8324`**; `FORCE_SITE_NAME = "DemoDev"` and
`ALLOWED_HOSTS == []` (DEBUG lets `127.0.0.1` through, so `Client(SERVER_NAME="127.0.0.1")`).

## The recipe, in order

```
uv run python manage.py content_save demo_content DemoDev
uv run python manage.py qa_create_application_review_accounts --site-name DemoDev
uv run python manage.py qa_create_application_docs_scenario DemoDev
<enrolment script: applicant -> the three free demo courses>
```

`content_save` accepts the **parent** `demo_content` dir, not just one course dir, and loads all
seven. It is what sets the gated course's `application_form` FK, from
`access_config["application_form"] = "../functionality_demo_application_form/form.md"` — a
relative path resolved at load time, so the form course must be loaded in the same pass.

`qa_create_application_review_accounts` alone satisfies items 2/3/4 (applicant + bystander +
3-perm staff reviewer). Its `_purge_course_data()` already deletes in the RESTRICT-forced order
(CourseApplication -> FormProgress -> CourseProgress -> LearnerCourseRegistration ->
CohortMembership), so **do not hand-write the teardown** — run the command and read its
`removed:` lines. Run it BEFORE the enrolment, because it purges registrations.

`qa_create_application_docs_scenario DemoDev` takes SITE_NAME **positionally** (default DemoDev),
not `--site-name`; it is the odd one out next to the review-accounts command in the same run.

## Two gated courses, and they are easy to confuse

| slug | title | `application_form` |
|---|---|---|
| `functionality-demo-application-gated-course` | Functionality Demo - Application gated course | `Application form` (set) |
| `advanced-product-analytics-masterclass` | Advanced Product Analytics Masterclass | **None** |

The second is the docs-scenario course and is the "gated but names no form" fixture. Both are
`access_config={"access_type": "application_gated"}` — only the FK tells them apart.

## A re-run usually deletes NOTHING

On this pass all three accounts (pks 73/74/75) were already at the target shape: the previous run
had left zero applications, zero `FormProgress`, zero registrations. **Inspect first and report
"already correct"** rather than assuming a teardown is due — the spec is written as if a re-run
always has residue, but the seeding command is destructive-idempotent so the residue is normally
gone already.

The one leftover that DID exist was out of scope: `demodev@email.com` (pk 9, the superuser) holds
`CourseApplication 4408c2b7-...` on the gated course plus 2 `FormProgress`. Do not delete it —
say so, because a tester who walks the apply flow AS the superuser will hit the
`unique_application_per_site_user_course` constraint and see the status page instead.

## Field names / import paths that bit this run

- `CourseFormAttempt` lives in **`freedom_ls.learner_progress.models`**, not `form_engine.models`.
- `TopicProgress` has **no `user`** field: filter `course_progress__learner__user=`.
- `CourseApplication` has **no `status`/`state`** yet on this branch — only
  `user / course / form_progress / created_at / updated_at`. The FSM is a documented NOTE on the
  model, not a field. Printing `a.status` raises `AttributeError`.

## Enrolment shape (item 6)

`LearnerFactory(user=..., organisation=get_default_organisation(site), site=site)` returns the
persona's EXISTING `Learner` (it delegates to `ensure_learner`), then one
`LearnerCourseRegistrationFactory(learner=..., course=..., site=site, is_active=True)` per course.
The `post_save` receiver mints a `CourseProgress` at `progress_percentage=0`,
`last_accessed_item=None` — which is exactly the "fresh outline" item 6 asks for, so there is
nothing extra to zero afterwards. Check
`WebhookEndpoint._base_manager.filter(site=site, is_active=True)` first (0 on DemoDev) so the
`course.registered` announcement fires nowhere.

With `FormProgress` at 0 for the persona, every placement reads "Start Form" by construction
(see [[reference_clearing_form_sittings_around_an_application]] — the button depends on
`FormProgress` alone). The five form placements in the three free courses:
end-with-quiz items 2 & 4, end-with-topic item 3, course-parts items 5 & 7.
Learner course URL is `/courses/<slug>/` (resume) and `/courses/<slug>/<1-based index>/`.

## `qa_reset_course_application` no longer exists

[[reference_withdrawing_a_course_application]] documents it, but the source file was deleted with
the sdd work-file cleanup (only a stale `.pyc` survives in `__pycache__`). Do not go looking for
it — `qa_create_application_review_accounts` covers the same teardown for these three personas.

## Addendum: verified on `google-analytics-setup`, Sep 19 2026 (read-only lookup)

DemoDev on this worktree is Site **id 3, domain `127.0.0.1:8000`** (not `:8324` as above — the
domain differs per worktree, so re-read it rather than trusting this file).

**No demo course title contains "By application."** Callers ask for the gated course by that
phrase, but the stored title is `Functionality Demo - Application gated course`. Match on
`access_config["access_type"] == "application_gated"` instead of on the title.

The two gated courses on THIS branch (the `advanced-product-analytics-masterclass` row named in
the table above is not present here):

| slug | pk | title | `application_form` |
|---|---|---|---|
| `functionality-demo-application-gated-course` | `271eeb30-94db-4261-b409-19888b0ead7d` | Functionality Demo - Application gated course | `Application form` `c974f518-5dc3-44d5-b00d-505f38b35e60` |
| `qa-application-gated-course-no-form` | `be764892-91a9-4ee1-af10-d09b6c8312c2` | QA Application-Gated Course (No Form) | **None** |

### Shape of `Application form` (slug `application-form`, strategy `UNSCORED`, `submit_on_exit=False`)

3 pages, 13 questions, **9 required**:

- p0 "About you" (9 q): required = full name (short_text), DOB (date), email (email),
  years writing software (number), how did you hear (multiple_choice);
  optional = phone, portfolio url, interests (checkboxes), why this course (long_text).
- p1 "Supporting documents" (2 q): required = ID/certificate (**file_upload**);
  optional = anything else (long_text).
- p2 "Availability" (2 q): required = preferred time (time), time zone (dropdown).

The required `file_upload` on p1 is the notable one — an applicant cannot complete the sitting
without attaching a file, so any "submitted application" fixture needs a real upload.

`FormQuestion.required` defaults to **True**; `FormPage`/`FormQuestion` reach via
`FormPage._base_manager.filter(form=f)` / `FormQuestion._base_manager.filter(form_page=p)`,
both ordered by `order` (1-based in this fixture).

### QA personas

`qa-learner-b@email.com` is **pk 70, site 3**. On this pass it had **zero** `CourseApplication`
rows on any course — as did the gated course itself (zero applications from anyone, so the
`demodev@email.com` leftover noted above is gone on this branch). Confirm before assuming residue.
