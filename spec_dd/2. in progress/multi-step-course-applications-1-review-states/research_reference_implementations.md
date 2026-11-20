# Research: reference implementations for application states, rejection, withdraw and re-apply

Input to `multi-step-course-applications-1-review-states`. It does not repeat `research_review_foundations.md`
(FLS code, audit log, roles). It looks only at how other systems model the same four things. Web search
snippets were thin: several vendor pages returned an empty shell or a 403, so each claim says how firm it is.
No FLS personal or project data went into any query.

## Short version

- Every system that was checked keeps application state as one small field with a handful of values and
  puts "closed" values (rejected, withdrawn) beside "open" ones. None needs `under_review` for the model to
  work. This matches the idea's five states.
- Two patterns for re-applying exist. **New record** (Frappe, ATS tools that attach a new application to the
  same person) and **un-reject the same record** (Greenhouse "Unreject", staff-only). The idea's choice (new
  row, partial unique index over active states) is the common one. A reviewer-side undo is a separate,
  later feature.
- A rejection reason is usually two things: a **structured reason** for reporting (ATS tools) and a
  **candidate-facing message**. The idea already splits these (message on the application, ids and labels in
  the audit log). Nothing found argues against a required message.
- Withdraw is almost always a distinct state from reject and has its own reason list, so reports can tell
  "we said no" from "they left". The idea has this.
- Systems that keep the applicant's identity apart from the decision (Canvas `rejected` enrolment, Moodle
  approval plugins) show that the closed application and the registration are separate records. FLS already
  has that split (application vs `LearnerCourseRegistration`).

## 1. Frappe Education (ERPNext) Student Applicant

Source: https://docs.frappe.io/education/student-applicant (also https://docs.frappe.io/education/program-enrollment).

- Statuses named by the docs: `Applied` (default on web-form submit or manual entry), `Approved`, `Rejected`,
  `Admitted`. The docs name Approve and Reject as actions but do not spell out a "Rejected" status page.
- Transitions: Applied -> Approved or Rejected. Approved shows an **Enroll** button that creates the Student
  and opens Program Enrollment. Creating the student sets the applicant to `Admitted`. The docs state the
  status then cannot be changed unless the student record is deleted.
- No withdraw state is documented, no rejection reason field is described, and re-applying is not described.
- Lessons for the spec:
  - Approval and "the person is now enrolled" are two steps with two records, and the second sets a final
    status on the first. This supports keeping `approved` as a state that only changes state in spec 1 and
    leaving registration to spec 3. A later `registered`/`admitted` outcome is a spec 3 question, not spec 1.
  - Locking the application once the downstream record exists is a pattern worth noting for spec 3. It is not
    needed in spec 1.
  - A bare `Rejected` with no message is what the idea is moving away from.

## 2. Moodle: core self enrolment and the approval plugins

Sources: core docs https://docs.moodle.org/en/Self_enrolment; plugin directory entries
https://moodle.org/plugins/enrol_apply ("Enrolment upon approval"), https://moodle.org/plugins/enrol_gapply
("Enrollment Application"), https://moodle.org/plugins/enrol_gapplya ("Enrolment Request"). The plugin pages
could not be fetched in full (403), so this rests on search summaries and should be read as medium
confidence.

- Core Moodle has **no approval step**: self enrolment is key-based and instant. Approval-before-enrolment is
  only offered by third-party enrolment plugins, which confirms that a first-class application state is
  something LMSs usually lack. FLS building it is not unusual, only uncommon.
- `enrol_apply`: adds an approval step, and the applicant is emailed when approved or rejected. Its
  listed support stops at Moodle 4.1 and users report email not being sent on newer versions. The lesson is
  the same as in the idea: no email in spec 1, and a decision the applicant cannot see on screen is fragile
  when it relies on a mail.
- `enrol_gapply`: the applicant supplies text or files, teachers are notified of new applications, and it
  supports Moodle 4.1 to 5.1. A fork (`enrol_gapplya`) describes itself as "majorly extended and completely
  refactored", which hints that the simple model needed rework once reviewers and notifications grew. The
  detailed state list was not retrievable, so do not treat this as a source for state names.
- Moodle's enrolment model is "an enrolment row per user per course with a status (active or suspended)".
  Approval plugins sit in front of that row. Same split as the Frappe case: application record first,
  enrolment record second.

## 3. Canvas

Sources: Canvas Data docs on enrollment `workflow_state`
(https://canvas.wisc.edu/doc/api/file.data_service_canvas_enrollment.html) and the Unizin mapping
(https://resources.unizin.org/products/data-and-analytics/unizin-data-platform/miscellaneous/course-section-enrollment-role-status-mappings).

- Enrollment `workflow_state` values documented: `active`, `completed`, `creation_pending`, `deleted`,
  `inactive`, `invited`. Unizin's mapping also lists `rejected`, which it treats as "not enrolled", and
  `deleted` as "withdrawn". (Canvas's own API docs for `rejected` were not found, so this comes from the
  Unizin mapping.)
- Canvas's `invited` / `rejected` pair is the **invitee's** accept or decline, not a reviewer's decision, and
  `deleted` is how a person drops. So Canvas is not a model of reviewed applications. It is only evidence that
  an enrolment row carrying closed values (`rejected`, `deleted`) is the usual shape, and that "withdrawn"
  often exists only as reporting vocabulary over a deleted or inactive row.
- Not a source for rejection reasons or re-applying.

## 4. Open edX

Sources: forum thread https://discuss.openedx.org/t/if-a-course-is-invitation-only-can-i-still-enroll-users-via-api/6283;
edx-enterprise change about invite-only handling
https://www.github.com/open-craft/edx-enterprise/pull/14; edX course-enrolment docs
https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-cypress/running_course/course_enrollment.html.

- Open edX has no application or review model. Courses are open, or "invitation only" where staff enrol
  people from the instructor dashboard.
- The pre-approval record is `CourseEnrollmentAllowed` (CEA): a row keyed by email and course. When the person
  signs up or enrols, the CEA is linked to that user so it cannot be reused by another account.
- Lesson: this is the closest match to the **unclaimed application** problem. A decision attached to an
  email, linked to an account only at claim time, and made single-use. For spec 1 the idea's rule (approve is
  refused when `user` is null) is the safe version. Open edX's CEA shows the opposite design (decide first,
  attach the account later), which is what spec 3 may want if approval before claim is ever allowed. Note it
  but do not adopt it here.
- No source retrieved on enrolment `is_active` and re-enrolment, so no claim is made about it.

## 5. Applicant tracking and admissions systems (the closest match for states)

Sources: Greenhouse unreject
https://support.greenhouse.io/hc/en-us/articles/360025520131-Unreject-candidate-or-prospect and
https://support.greenhouse.io/hc/en-us/articles/204342969; Lever repeat-application blocking
https://help.lever.co/hc/en-us/articles/20087458260893 (page itself would not load; the summary came from
search); Sourcegraph handbook rejection-reason list
https://handbook.sourcegraph.com/departments/people-talent/talent/process/candidate-rejection-reasons;
Oracle HCM "Allow Candidates with Withdrawn Job Applications to Reapply"
https://docs.oracle.com/en/cloud/saas/talent-management/24b/faimh/allow-candidates-with-withdrawn-job-applications-to-reapply.html
(the page body could not be retrieved, only its title); SchoolSpring/PowerSchool
https://help.powerschool.com/t5/Unified-Talent-SchoolSpring/Can-I-Reapply-for-the-Same-Job-Posting-After-Withdrawing/ta-p/544415
(title only). Treat everything here as medium or low confidence.

- **Greenhouse**: a rejected candidate is "rejected" on the application, and a staff member with permission
  can **Unreject**, which returns it to the active pipeline. So Greenhouse allows reopening the same
  application. It is a staff action with a permission, not an applicant action.
- **Lever**: repeat applications to the same job are controlled by a company setting. A waiting period can
  be set, and a candidate who tries inside it sees a message that they have already applied and when they
  may try again. The block applies whether the earlier application is active or archived. That is a
  **cool-off after a closed application**, enforced at apply time.
- **Oracle HCM and SchoolSpring**: both ship a documented option or FAQ on whether a withdrawn application
  may be re-submitted. The existence of an option shows that "withdrawn, may re-apply" versus "withdrawn,
  may not" is a policy that employers want to set per site. The detail was not retrievable.
- **Rejection reasons**: ATS tools keep a **reason list** for reporting (Sourcegraph publishes theirs and
  lists withdrawal reasons apart from rejection reasons), plus optional free text, plus an optional
  templated message to the candidate. The reason list and the candidate message are separate things in all of
  them.
- **Withdrawn as a separate state** from rejected is the norm, with its own reasons (for example, took
  another offer).

## 6. How this lines up with the idea's decisions

| Idea decision | Reference evidence | Verdict |
| --- | --- | --- |
| Five states, no `under_review`, no `changes_requested` | Frappe has Applied/Approved/Rejected/Admitted; no system checked needs a mid state for the model to work | Fits |
| Reject carries an applicant-visible message; audit log holds ids only | ATS tools split structured reason from candidate message; Moodle `enrol_apply` leans on email and breaks when mail fails | Fits; message on the application is right |
| Reject message required (answers.md) | Frappe has no message at all; ATS tools often make the reason optional. Required is stricter than the references | Valid product call, no reference conflict. Say in the spec that it is stricter on purpose |
| Re-apply makes a new application; partial unique index over active states | Frappe, Moodle approval plugins and the ATS "attach a new application to the same person" model all keep the closed record and add a new one. Greenhouse alone reopens the same record, via staff Unreject | Fits; mention Unreject as a possible later reviewer action, not spec 1 |
| Withdraw allowed from draft and submitted only | Frappe locks the applicant once the downstream record exists; ATS tools generally allow withdraw while open. Nothing about withdrawing after approval was found in the references | Fits; approved is a decision, so withdraw after it is a spec 3 question once registration exists |
| Applicant's submit and withdraw not audited | No reference compares to FLS's audit-log privacy rule | Neutral; this is an FLS rule, not a reference pattern |
| Unclaimed application cannot be approved | Open edX allows a decision keyed to an email and links the account later (CEA) | Reference shows an alternative; the idea's refusal is the cautious one and fits spec 1 |
| Dashboard keeps closed applications visible | Canvas and Moodle keep closed enrolment rows visible to admins; no reference found on applicant-facing history | Neutral |

## 7. Questions the references raise for the spec (not answered by the idea or answers.md)

1. **Re-apply policy.** Lever and Oracle expose a cool-off or a per-site toggle. The idea says re-applying is
   always allowed. State plainly that there is no cool-off and no limit on how many closed applications a person
   can stack up per course. This is simple, but a reviewer could be asked to see a person apply again straight
   after a reject. Whether to show the applicant that history (the earlier reject message) at the "apply
   again" step is open.
2. **Which application the course CTA and panel show** when there is one active and several closed. The idea
   says "prefer the active one". After a reject with no new application, show the latest closed one. Define
   "latest" (by decision time or `updated_at`), since two closed rows can exist.
3. **Un-reject.** Greenhouse shows reviewers asking for it. The idea has no way to undo a reject, a withdraw
   or an approve. That is acceptable for spec 1 because there is no reviewer screen yet, but it should be a
   recorded decision, because the partial index means undoing a reject while a new active application exists
   would collide.
4. **Approved then withdrawn.** Not allowed in spec 1 by the idea. Name it as deferred to spec 3.
5. **Reason codes.** The references split reason code and message. The idea has only the message. Say that no
   structured reason code is stored in spec 1, so reporting by reason is not possible until one is added.
6. **Reject message editing.** None of the references treat the message as editable after sending. The idea
   does not say either. Treat it as write-once with the state change.

## Confidence and gaps

- Firm: Frappe Student Applicant statuses and transitions (fetched from the docs); Open edX invitation-only
  behaviour and CEA linking; Canvas enrolment state list.
- Medium: Moodle plugin behaviour, Greenhouse Unreject, Lever repeat blocking (search summaries; the pages
  would not open or returned only a shell).
- Not found: whether Frappe allows re-applying; Canvas's own definition of `rejected`; Oracle and SchoolSpring
  withdrawn-reapply detail; any LMS that has a withdraw state for a pre-enrolment application.

status: ok
