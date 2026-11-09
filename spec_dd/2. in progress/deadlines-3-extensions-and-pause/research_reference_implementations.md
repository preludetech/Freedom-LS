# Research: how reference implementations solve extensions and pause

Topic `reference_implementations` for spec `deadlines-3-extensions-and-pause`. Builds on `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md` sections b and c; does not repeat them. Where a source gave no detail, the gap is stated. Terms are those of each system, not FLS (course time limit, deadline, extension, pause are the FLS words).

Quality note: several Open edX and Canvas details come from mirrors, forks and university help pages, not current official docs. Marked "mirror" or "secondary".

## Summary table

| System | Record shape | End date on resume/extension | Stacking | Audit | Event |
|---|---|---|---|---|---|
| Open edX IDDE (edx-when) | per-user date row, one per (user, block, field) | absolute new date typed by instructor | replace (set a date) | reason + audit planned in design; original IDDE had none | none found |
| Open edX Reset Deadlines | learner action: schedule start set to today | whole schedule shifts | n/a (recompute) | none found | none found |
| Canvas overrides | override row with `student_ids`, `due_at`, `unlock_at`, `lock_at` | absolute dates | most specific target wins, no stacking | none in the model | none found |
| Moodle assign / quiz | per-user flag / override row | absolute date | replace | optional "reason" on overrides | calendar event only found |
| Moodle enrolment | `user_enrolments.status`, `timestart`, `timeend`, `modifierid`, `timemodified` | admin retypes `timeend` | replace | last modifier only | not found |
| Stripe pause_collection | fields on the subscription: `behavior`, `resumes_at` | billing anchor unchanged on collection pause | n/a | none | none for collection pause |
| Stripe full pause | `status=paused`, `status_details.paused` | `billing_cycle_anchor` chosen on resume | n/a | `transitioned_at`, `type` reason | `customer.subscription.paused`, `.resumed`, `.updated` |
| Chargebee | `pause_date`, `resume_date`, `skip_billing_cycles` | `next_billing_at` recomputed | pause extended by remove + re-pause | none public | not confirmed |
| Recurly | `paused_at`, `remaining_pause_cycles`, `resume_at` | pause measured in cycles | length adjustable | `paused_at` | `subscription_paused`, `subscription_resumed` (secondary) |

## 1. Open edX

**Individual Due Date Extensions (IDDE).** An instructor opens Instructor Dashboard, Extensions, enters a learner email or username, picks a graded subsection, types a new deadline (UTC). The same page lists "all extensions for a student" and "all students with due date extensions" for a subsection. The help page does not say whether the new date must be later than the original, whether it replaces or stacks, or how to remove one; no ORA (open response assessment) scope is mentioned on that page. https://help.edtech.ektu.kz/en/prepodavanie-v-open-edx/tekushee-upravlenie-kursom/grant-extensions (secondary)

**Data model.** The original mechanism stored per-student values in a `StudentFieldOverride` table keyed by course, block location, student and field (so any field, not only `due`, can be overridden for one student). https://git.andalsoftware.com/Andal.LND/edx-platform/src/branch/master/lms/djangoapps/courseware/student_field_overrides.py (mirror, search snippet only; fetch failed) and https://code.vt.edu/hsinyu/edx-platform-release/-/commit/3256eb1ff65c3e58e623b927a0bb953830d8fe3d (mirror). It was later superseded by `edx-when`, the central date service. Its design record describes `DatePolicy` (course, absolute date, time delta) and `UserDate` (user, policy, absolute date plus relative date), with an audit trail and a recorded reason as design goals. The same record states the earlier IDDE had no audit trail and no place for a reason. https://github.com/openedx/edx-when , https://git.andalsoftware.com/Andal.LND/edx-platform/commit/39ad3b1dd8f94d29f8d6223d30583323f62ed22f (mirror). I could not confirm an `actor` field in shipped code. Self-paced courses keep dates only in edx-when, so the extension dashboard had to read from it, not just write. https://git.andalsoftware.com/Andal.LND/edx-platform/src/commit/d4506b73f459d407feece6b4eb2fb275fe8670adf (mirror)

**Pacing and Reset Deadlines.** In self-paced courses there are no due dates other than the course end date unless a Personalized Learning Schedule (PLS) is active; graded assignments inherit default pacing. https://docs.openedx.org/en/open-release-sumac.master/educators/references/setting_course_pacing.html . The learner "Reset deadlines" view sets the schedule start date to today, which moves every due date of the self-paced sequentials; `reset_course_deadlines_for_user(user, course_key)` returns False when gated content blocks the reset. An earlier commit allowed the reset only when a sequential was past due and incomplete. https://docs.openedx.org/projects/edx-platform/en/ulmo/references/docstrings/openedx/openedx.features.course_experience.api.v1.html , https://git.andalsoftware.com/Andal.LND/edx-platform/commit/fd5fc29dd6fd211bf9c85d68f860fc7ca990f12d (mirror). I could not retrieve the exact shift computation or `CourseEnrollment`/`RelativeDateHighlights` field use. What is clear: the shift is "rebase the schedule start to now", not "add the time missed", and dates are stored as offsets from a start so one field change moves them all.

**Stacking and audit.** IDDE sets an absolute date, so a second extension replaces the first. The date list is the only audit view found.

**Events.** Open edX Events has enrolment and certificate signals; I found none for due-date extensions. https://docs.openedx.org/projects/openedx-events/en/ulmo/reference/events-data.html

**Borrow:** a per-learner list view of all extensions (spec 6 will want it); one place for dates (matches "shift inside the one resolver"); a reason field from the start. **Avoid:** absolute-date-only extensions (cannot stack, cannot survive a base date change); reset that rebases the schedule with no record of why.

## 2. Canvas

**Model.** An assignment override has `id`, `title`, `due_at`, `unlock_at`, `lock_at`, and one target: `student_ids` (ad hoc), `group_id` or `course_section_id`. If several targets are sent, the most specific wins (students, then group, then section). Ad hoc overrides need a `title`; a student can be in only one ad hoc override per assignment; `unlock_at` must be before `due_at` and `lock_at` after it. Sending `assignment_overrides` on update deletes any existing override left out of the list. https://developerdocs.instructure.com/services/canvas/resources/assignments , https://canvas.iastate.edu/doc/api/assignments.html (the ad hoc rules come from a mirror, https://www.withone.ai/knowledge/canvas-lms/conn_mod_def%3A%3AGM1NDVOhQ58%3A%3AQmJBp7YgQ2WvpqmIkZwqww). Because due, unlock and lock live in one row and are validated together, the "closed while not overdue" half-extended state is rejected at write time. This is exactly the spec's "move due and close together". The landscape file already notes extending "Until" alone leaves the late flag.

**Pause, term, conclude.** No pause exists. Enrolment states are active, inactive (no access, roster visible), concluded (read-only) and deleted. Concluding stamps the course participation end date with now, and "Restrict students from viewing course after end date" turns read-only into no access. Inactive is the workaround for a temporary hold. https://community.canvaslms.com/t5/Resource-Documents/Canvas-Enrollment-Status-Comparison-PDF/ta-p/387055 , https://www.celt.iastate.edu/course-conclusion-in-canvas/ . Course and section dates (term, course, section participation dates) are the only way to move an end for a group.

**Stacking/audit/events.** One override per student per assignment, so replace not stack. The override model keeps no reason or actor; Canvas keeps a general audit log elsewhere (not verified here). Canvas Live Events exist, but I did not confirm an override event.

**Borrow:** due/unlock/lock validated together in one record; a precedence rule stated plainly (most specific wins). **Avoid:** "update replaces the list", a destructive write; a model where an extension has no reason or actor.

## 3. Moodle

**Assign extensions.** Granting an extension needs the capability `mod/assign:grantextension`. The date must be after the due date and on or before the cut-off ("final date") if set. Storage began as `extensionduedate` on `assign_grades`, later moved to a per-user `assign_user_flags` table (assignment, userid, extensionduedate, mailed, locked). A granted extension also creates a calendar event of type extension. https://docs.moodle.org/dev/Assignment_Submission_Date_Extensions , https://tracker-old.moodle.org/browse/MDL-46506 (secondary). Known bugs include saving an extension where a grade row existed already, which is why it moved to its own table. Note the cap: an extension cannot go past the cut-off, so the cut-off is a separate, harder date. The Moodle Activity Extensions Spec proposes unifying this across activities. https://docs.moodle.org/dev/Moodle_Activity_Extensions_Spec

**Overrides (assign and quiz).** User overrides set open ("Allow submissions from"), due and cut-off, each enabled independently, plus an optional "Reason for override" visible to teachers in the override list. User beats group; several groups give the most lenient date. https://docs.moodle.org/en/Assignment_overrides . Quiz user overrides also cover time limit and attempts (secondary: https://answers.uillinois.edu/71244 ). Replace semantics; no stacking.

**Enrolment suspension (closest to pause).** `user_enrolments` keeps `status` (0 active, 1 suspended), `timestart`, `timeend`, `modifierid`, `timemodified` (and `timecreated`). Suspended users cannot enter the course and are mostly hidden, unless they hold `moodle/course:view` or guest access applies. `update_user_enrol()` changes status and dates together. https://docs.moodle.org/dev/Database_schema_introduction , https://moodledev.io/docs/apis/subsystems/enrol , https://docs.moodle.org/dev/New_enrolments_in_2.0 . A suspended enrolment hides the course; it does not show past results and does not shift `timeend`. Reactivation is a manual new end date (landscape file). The `modifierid` plus `timemodified` pair is the only audit and keeps just the last change. I did not confirm event names for enrolment updates.

**Borrow:** per-field "enabled" overrides; an optional reason; a hard-cap date an extension cannot pass (FLS: decide whether extensions may pass the course time limit end). **Avoid:** suspension that hides past results; last-modifier-only audit.

## 4. Course-access expiry products (additions only)

- **LearnDash.** Extend access replaces the end date (already in landscape file). Nothing further found.
- **TalentLMS.** Per-user expiration date change; no pause. Nothing beyond the landscape file.
- **Thinkific.** Expiry date set at enrolment; manual, bulk and coupon enrolments need the date updated by hand; on bulk enrolment "whichever date gives the longest access wins" (a lenient-wins rule like Moodle groups). Progress is kept when access expires and the learner re-enrols. https://support.thinkific.com/hc/en-us/articles/360058882973 , https://support.thinkific.com/hc/articles/360030351374
- **Teachable.** A source states the time limit cannot be extended after it expires; the enrolments API only exposes `expires_at` read-only. https://intercom.help/teachableknowledgebase/en/articles/11682480-product-access-duration , https://docs.teachable.com/changelog/march-14-2023-get-coursescourse_idenrollments-expires_at-added-to-response (limitation is secondary and unverified).

**Borrow:** Thinkific's "progress kept across expiry". **Avoid:** Teachable's one-way expiry (an expired learner cannot be helped).

## 5. Non-LMS pause

**Stripe pause_collection.** Fields on the subscription: `pause_collection.behavior` (`keep_as_draft`, `mark_uncollectible`, `void`) and optional `resumes_at`. Status stays `active`, the customer keeps access, invoices keep generating. Without `resumes_at` the pause lasts until unset. Resume is "unset the field"; it affects only future invoices. No dedicated events (status unchanged). https://docs.stripe.com/billing/subscriptions/pause-payment

**Stripe full pause (flexible billing mode).** Separate feature that suspends service and invoice generation. `status` becomes `paused`; `current_period_end` is truncated to the pause time; `status_details.paused` holds `transitioned_at` and a `type` reason (`pause_requested`, `trial_end_without_payment_method`, `system`). Resume takes a `billing_cycle_anchor` (`now` starts a fresh period) and proration; if resuming creates an invoice, status stays `paused` until it is paid and a failed or voided invoice leaves it paused. A coupon's validity keeps running through the pause. Events: `customer.subscription.paused`, `customer.subscription.resumed`, `customer.subscription.updated`, and an entitlement summary event for de-provisioning access. A scheduled pause and resume lives in a separate "pause schedules" page (not read). Worked example: pause day 15 of 30, resume day 45, new 30 day cycle begins at resume, next renewal day 75. https://docs.stripe.com/billing/subscriptions/pause

**Chargebee.** `pause_option`: `immediately`, `end_of_term`, `specific_date`, `billing_cycles`; fields `pause_date`, `resume_date` (omitted for indefinite), `skip_billing_cycles` (min 1). Only active or non-renewing subscriptions can pause; for non-renewing, both dates must fall before the cancellation date. Resume takes `immediately` or `specific_date`. A scheduled resume date cannot be edited: support says use "Remove Scheduled Resumption" (the pause stays) then set a new one. `next_billing_at` is updated from the inputs (exact rule not stated). https://apidocs.chargebee.com/docs/api/subscriptions/pause-a-subscription.md , https://apidocs.chargebee.com/docs/api/subscriptions/resume-a-subscription , https://support.chargebee.com/support/solutions/articles/254847-how-to-extend-the-pause-date-for-a-subscription- . Event names not confirmed.

**Recurly.** Fields `paused_at`, `remaining_pause_cycles`, `resume_at`. A pause is scheduled to start at the next bill date for N cycles; sending 0 on a scheduled pause cancels it, on a paused one it resumes at next bill date, other values change the length of a running pause. Expired, cancelled, failed and trial subscriptions cannot pause. Webhooks `subscription_paused`, `subscription_resumed` come from a search summary only. https://docs.recurly.com/recurly-subscriptions/v2021-02-25/reference/pause_subscription , https://docs.recurly.com/recurly-subscriptions/docs/navigate-retain-subscription-pause-tracking . How the next bill date moves on resume is not described in what I read.

**Gym freezes (landscape file has the rules).** Nothing new on data models; the shared pattern is count and total-length limits per rolling period, reason gating, and "term extended by the frozen months". Gymbox rounds to whole months and starts on the 1st, a rounding choice comparable to the settled whole-days-rounded-up rule.

**Borrow:**
- Stripe full pause: a `type`/reason on the record plus `transitioned_at`; paired `paused`/`resumed` events plus a generic `updated`; `resumes_at` evaluated by time rather than by a job (Stripe's collection pause unsets only on request or by `resumes_at` and keeps status; FLS matches this with "evaluated when read").
- Chargebee: planned resume date and a distinct way to cancel or change it; a hard bound (resume before cancellation date maps to resume date before course end is not needed since the end moves).
- Recurly: separate "scheduled" and "active" states with explicit fields for each.
- Stripe: a pause that leaves the entitlement untouched until a resume succeeds is a billing concern and does not apply to FLS.

**Avoid:** Chargebee's non-editable scheduled resume (FLS should let staff edit a planned resume date); Stripe's billing-anchor choice on resume (FLS has no equivalent and the settled rule is a fixed shift by whole days); Stripe keeping the subscription `active` during the pause (FLS must show paused state, so it needs its own state, not an overloaded `active`).

## 6. Cross-cutting answers

- **How the end date moves on resume.** Only Gymbox ("term extended by frozen months") and Stripe full pause (new period from resume) compute it from the pause. Stripe resets the cycle at resume; gyms add the frozen duration. No LMS does either. FLS's settled rule (add whole days, rounded up, to the time limit and unmet deadlines) matches the gym model and is novel for LMSs.
- **Stacking.** Every system found uses absolute dates and replaces: Open edX IDDE, Canvas (one override per student per assignment), Moodle (one flag or override per user), LearnDash. The only stackable design seen is relative ("N more days"), which FLS has chosen; a second extension applied to the current resolved date needs no stored previous date. Recording each extension as its own row (delta plus reason plus actor) would give the stack for free and keep audit; this is inference, not seen in a source.
- **Audit fields.** Best seen: Moodle "Reason for override" (override list), Moodle enrolment `modifierid` and `timemodified` (last change only), Stripe `status_details.paused.transitioned_at` and `type`, edx-when design (audit trail and reason, unconfirmed in shipped code). None keeps a full history of every change except by event logs.
- **Events.** Only the billing systems emit paired pause and resume events (Stripe confirmed, Recurly secondary, Chargebee not confirmed). The LMSs found emit none for extensions (Moodle makes a calendar event only). FLS firing a webhook for pause, resume and extension is ahead of the LMS norm; Stripe's paired `paused` / `resumed` names plus a generic updated event is the template, with the user, organisation, learner, course payload convention FLS already has.
- **Pause and access.** Stripe collection pause keeps access; Stripe full pause, Canvas inactive and Moodle suspension remove it. Of those, Canvas concluded is the only state that keeps past results visible (read-only); this is the model for "nothing can be opened, past results stay".

## What this suggests for the open questions

1. **One model or two** (inference): billing systems keep pause as state on the subscription; LMSs keep extension as an override row. Keeping them as two records (pause: start, planned resume, reason, actor, status, resumed-at; extension: delta days or target date, reason, actor, scope) fits both patterns, and spec 1's resolver then sums stored extension deltas and pause shifts.
2. **Extension vs spec 1 override:** relative, additive rows win on stacking and audit; a single absolute override row cannot show who extended when.
3. **Validate together:** Canvas's due/unlock/lock validation and Moodle's cap rule show how to keep due and close consistent; apply in one function that writes all dates.
4. **Resume shift:** compute from stored start and actual resume time, rounded up to whole days, store the days applied on the record, so a later audit does not need to recompute. (Stripe stores `transitioned_at`; gyms store counted months.)
5. **Planned resume:** treat as editable until it passes (against Chargebee).

status: ok
