---
name: reference-clean-applicant-command
description: qa_create_clean_applicant — the one-persona "verified learner, zero applications, zero sittings, optionally registered" command that replaces hand-scripting the A/B applicant pair
metadata:
  type: reference
---

`qa_create_clean_applicant --email EMAIL [--register-course-slug SLUG]... [--site-name DemoDev]`
(`freedom_ls/qa_helpers/management/commands/qa_create_clean_applicant.py`, written Sep 2026 on
`form_engine_data_field`). One persona per invocation — run it twice for an A/B pair rather than
hardcoding a pair the way `qa_create_application_review_accounts` does.

It does, in order: `_ensure_user` (plain learner, `password=email`, `_base_manager` lookup so a
same-email account on another Site is reset rather than duplicated) -> `_ensure_verified_email`
(`update_or_create`, never `get_or_create`) -> `LearnerFactory` -> `_purge_course_data`
(CourseApplication -> FormProgress -> CourseProgress -> LearnerCourseRegistration ->
CohortMembership, the order the RESTRICT/PROTECTs force) -> one
`LearnerCourseRegistrationFactory` per `--register-course-slug`. It prints every removed row
with its pk and the `.delete()` cascade counts.

Use it instead of `qa_create_application_review_accounts` when the tester names their own
addresses; that command owns exactly `qa_applicant@` / `qa_bystander@` / `qa_reviewer@`.

## The A/B applicant-pair ask (form_engine_data_field, Sep 2026)

`qa.applicant.a@email.com` (pk 71, registered for `functionality-demo-show-end-with-topic`) and
`qa.applicant.b@email.com` (pk 72, no registrations) — B exists only to prove one applicant's
rejected answer does not touch the other's stored answers. Neither existed beforehand, so
**nothing was deleted**; as in [[reference_application_forms_qa_baseline]], inspect before
assuming the spec's "delete the leftovers from the previous run" clause has anything to bite on.

The two course slugs the ask names by *directory* map to:

| demo_content dir | slug |
|---|---|
| `functionality_demo_application_gated` | `functionality-demo-application-gated-course` |
| `functionality_demo_end_with_topic` | `functionality-demo-show-end-with-topic` |

Learner course URL `/courses/<slug>/` 302s to `/courses/<slug>/detail/` for an unregistered
persona; the gated one renders "Apply now" for both personas (checked with `force_login` +
rolled-back `atomic`).

## "No sitting so it reads Start Form" does NOT mean the tester can reach the form

end-with-topic places the form at **item 3** (`Course Feedback Survey`); items 1-2 are Topics.
Sequential unlock is enforced at URL level, so for a freshly-registered persona the outline is
`READY, BLOCKED, BLOCKED, ...` and `/courses/<slug>/3/` 302s back to the detail page. The
start-screen wording and the item's reachability are two different questions — answer both, and
say plainly that the tester must complete items 1-2 first (or ask for the TopicProgress rows),
because a spec that only says "no attempt at the form placement" reads as if the page were one
click away. See [[reference_sequential_item_unlock]].

To prove the wording anyway *without* leaving progress behind: inside `transaction.atomic()`,
`TopicProgressFactory(course_progress=cp, topic=t, collection_item=ci, site=site,
complete_time=now)` for items 1-2, GET item 3, grep the body, then raise to roll back
([[reference_shell_savepoint_does_not_roll_back]] — `atomic()`, never `savepoint()`). Confirmed
`Start Form` present / `Continue Form` absent, and TopicProgress back to 0 afterwards.

## `ContentCollectionItem` GenericFK field names

The placement lookup is `child_id` / `child_type` / `collection_id` / `collection_type`, with the
accessors `ci.child` and `ci.collection`. `filter(object_id=...)` raises `FieldError` — that is
`CohortDeadline`'s naming, not this model's.
