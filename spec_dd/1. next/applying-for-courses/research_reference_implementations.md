# Reference Implementations: Course Application & Approval Flows

Research notes for the FLS "Apply for a course" feature (see `0. idea.md`). Focus: per-course application + admin approval, then *manual* enrolment via existing cohort flow.

## 1. Coursera (Specializations & Degrees)

Two distinct models:
- **Specializations / individual courses**: no application — pay/audit and enrol.
- **Degree programs**: range from "performance-based admission" (no transcripts/essays/fee — admission earned by pathway course grades, e.g. CU Boulder MS-CS) to traditional admissions handled mostly off-platform.

Notable patterns:
- **Performance-based admission** turns the LMS itself into the application — completing N pathway courses with grade ≥ X auto-admits. No reviewer involved.
- Transcript handling for traditional degrees is *out of platform* (sent direct from issuing institution to a program email). PDF "course descriptions" upload supported for transfer credit only.
- Coursera has no in-platform application form builder — they hand off to partner admissions systems.

Takeaway: For many courses, "application" is the wrong primitive — gating on prerequisite course completion can be cleaner. Worth keeping the door open for a "prerequisite course" eligibility check in v2.

## 2. Open edX

No first-class application-based enrolment. Workarounds:
- `custom_reg_form` extends *registration* with extra fields stored separately. Not per-course, not approval-gated. (https://github.com/open-craft/custom-form-app)
- Manual enrolment requests via the e-commerce / WordPress sync plugin: admins create enrolments by hand.
- Long-running community discussion about pluggable access control for enrolment, but no shipped solution.

Takeaway: A mature LMS not having this built-in is signal — most Open edX deployments doing applications wire it up as a separate Django app that creates an `Enrollment` once approved. Same shape we're proposing.

## 3. Moodle — `enrol_apply` and `enrol_gapply` (closest direct analogs)

### `enrol_apply` ("Enrolment upon approval") — https://moodle.org/plugins/enrol_apply
- Adds an "approval" enrolment method alongside self-enrol/manual.
- Application form = standard/additional **user profile fields** (no per-course schema).
- States: `pending`, `approved`, `rejected`. No waitlist, no draft, no request-changes.
- Reviewer UX: Course → Participants → Enrolment methods → "Manage application" — flat list with approve/reject buttons.
- Email notifications on state change.
- Pain points from user comments:
  - Notifications fail when course start date is in the future
  - No "defer" status notifications
  - Enrolment-request emails don't include a course link
  - Notification text not customisable
  - No file uploads
  - Plugin unmaintained for 3+ years

### `enrol_gapply` ("Enrollment Application") — https://moodle.org/plugins/enrol_gapply
- Improves on apply: per-course application text, **file uploads** (configurable count/size/MIME), `Waitlisted` outcome.
- States: `Approved`, `Rejected`, `Waitlisted`, `Deleted`.
- Still single-step.
- **No global cross-course review dashboard** — reviewers go course-by-course (frequent complaint).
- Structured question types (dropdowns, radios, dates) requested but not implemented.
- No first/second choice prioritisation.

Takeaways:
- A **per-course form schema** (not just user profile fields) is essential — `enrol_apply`'s biggest miss.
- A **global "applications inbox"** across all courses is a clear unmet need.
- File uploads must be configurable (count, size, MIME).
- Have at minimum: `draft`, `submitted`, `under_review`, `changes_requested`, `approved`, `rejected`. Waitlist optional.
- Customisable notification copy + always include course link.

## 4. University admissions (Slate, Common App, UCAS) — brief

### Slate by Technolutions — https://technolutions.com/admissions
Dominant higher-ed admissions CRM. Patterns worth borrowing:
- **Reader review forms**: configurable per-program rubric (rating + comments) on each application. Multi-reviewer with score aggregation.
- **Reader queues**: each reviewer sees only what they're assigned; bins/folders by program/round/status.
- **Decision releases**: decisions staged (drafted → approved internally → released to applicants individually or in batch). Prerequisites prevent releasing incomplete decisions.
- **Identity verification** integrated as an optional step that can be inserted anywhere (https://knowledge.technolutions.net/docs/identity-verification).

### Common App / UCAS — https://www.ucas.com/applying/after-you-apply/clearing-and-results-day/results-day/what-your-application-status-means
- Applicant-visible states: `In progress` (draft), `Submitted`, `Decision pending`, `Offer (conditional/unconditional)`, `Unsuccessful`, `Withdrawn`.
- Edit allowed *until* submitted; after, requires explicit "request changes" from admissions.
- Long-running drafts (months) — auto-save non-negotiable.

Takeaway: For v1, skip multi-reviewer rubrics and decision-release workflows. But this **state vocabulary** is well-tested — use it.

## 5. MOOC cohort applications

### MIT MicroMasters → on-campus master's
- Application is mostly *outside* edX, in MIT's main admissions system.
- MicroMasters grades *are* the admission criterion (performance-based).
- Decisions released in **rounds** tied to a calendar — not rolling.

### Minerva
- Heavily structured multi-step application with cognitive assessments built in. Fully custom platform.
- Explicitly de-emphasises traditional credentials (no transcripts as primary signal).

Takeaway: Cohort programs need **application windows** (open/close per cohort intake). Model as a property of the application *configuration*, not the course.

## 6. Bootcamps & accelerators

### Y Combinator — https://www.ycombinator.com/howtoapply
- **Single long form** — no wizard — but with strong autosave and explicit "edit until submit" semantics. **No edits after submission.**
- Required short **video upload** (structured file field).
- **Automated screening** first (completeness, duplicate-cofounder detection), then human reviewers spending 60-90s per app.
- Reviewers work a queue; rolling review.
- Outcomes: invited to interview, rejected. Interview is a separate stage.
- Decision: email (rejection) or phone call (acceptance).

### Andela — https://ophyai.com/blog/company-guides/andela-interview-guide
- 4 stages: application + aptitude → home study + skill test → interview → 2-week bootcamp (also a filter).
- Each stage is a separate gate, not one big form. ~1% acceptance.

### BloomTech / Lambda School — https://www.bloomtech.com/article/how-to-apply-to-bloomtech-guide
- Multi-step: account → goals/background → state-specific eligibility (CA/TX require proof of education + entrance assessment) → tuition selection → financing partner application (off-platform).
- Demonstrates the **branching** problem: different attributes → different steps.

### ALX — https://www.alxafrica.com/selection-process/
- 6-section form (45-60 min): personal info, vulnerability/inclusion, assessments, essays, ALX challenge, financial aid.
- Decision in 24 hours.
- Stage 2 = 1-month "selection period" — the applicant auditions during a real cohort.

Takeaways:
- **Multi-step beats one long form** above ~6 fields. Sweet spot is 3-5 steps.
- **Sensitive fields go later** — users invested in earlier steps abandon less.
- **Branching** is real but adds enormous complexity. Defer to v2.
- **Autosave + resume** non-negotiable for anything > 1 step.
- **Lock-on-submit** is a clear mental model. "Request changes" is the only re-edit path.

## 7. Document upload & verification

From Slate, Stripe Identity, federal financial aid verification:
- **In-app verification is hard and expensive.** Most platforms either accept files at face value and verify manually (Moodle, most LMSs) or hand off to a third party (Stripe Identity, ID.me, Persona).
- File constraints universally include: max size, MIME allowlist, max count.
- **Sensitive documents (IDs, transcripts) shouldn't be downloadable by all admins** — needs role-gating.
- Storage: PII uploads typically separated from regular media (different bucket/prefix, retention policy, access log).
- Anti-pattern: storing upload paths in a generic "response" field — breaks GDPR deletion later.

Takeaway for FLS v1: accept files, validate MIME/size, role-gate downloads. No in-app verification. Plan separate storage path + explicit retention/deletion when application is rejected/withdrawn.

## 8. Application states — synthesis

| State | Meaning | Used by |
|---|---|---|
| `draft` | Applicant filling in, autosave only | UCAS, Common App, YC, Slate |
| `submitted` | Locked from edits, awaiting review | Universal |
| `under_review` | Reviewer picked it up | Slate, YC |
| `changes_requested` | Reviewer kicked it back to applicant | Slate, common in Moodle community asks |
| `approved` | Decision made | Universal |
| `rejected` | Decision made | Universal |
| `waitlisted` | Approved-pending-capacity | enrol_gapply, most universities |
| `withdrawn` | Applicant cancelled | UCAS |
| `expired` | Window closed before submission | Cohort programs |

**FLS v1 minimum**: `draft`, `submitted`, `changes_requested`, `approved`, `rejected`, `withdrawn`. `under_review` and `waitlisted` skippable.

## 9. Reviewer / admin UX — synthesis

What good review tooling does (Slate, TargetX, Kissflow):
- **Inbox/queue view** (not per-course list) — filter by course/cohort/intake/status/date.
- **Bulk actions**: bulk reject/approve/export.
- **Side-by-side**: form responses + uploaded documents in one screen.
- **Internal notes vs applicant-facing comments** kept separate.
- **Audit trail**: who decisioned, when, what they wrote.
- Decision-release as separate step from "internally decisioned" (skip v1).
- Rubric scoring (skip v1).

Common complaints to avoid:
- No global inbox (Moodle gapply) → applications missed in low-traffic courses
- Notifications without course links (Moodle apply) → applicants confused
- No way to ask for clarification → forces reject + re-apply, losing context
- Admin actions not logged → no audit when learner disputes a rejection

## 10. Post-approval flows

| Platform | After approval |
|---|---|
| Moodle `enrol_apply` | Auto-enrols |
| Moodle `enrol_gapply` | Auto-enrols |
| YC | Manual interview invite (separate stage) |
| BloomTech | Routes to financing partner; enrolment downstream |
| MIT MicroMasters | Manual offer letter; matriculation off-platform |
| Coursera degrees | Manual offer letter via partner university |
| Slate | Generates offer letter; enrolment in SIS, not Slate |

Pattern: the more selective / higher-stakes, the more likely approval is **decoupled** from enrolment. The idea file's design is consistent with serious admissions systems. Auto-enrolment on approval is the lightweight path.

Takeaway: Idea file is correct — keep approval and enrolment separate. But provide an **"Approve and enrol now"** convenience action so admins don't have to context-switch when they want both.

## Key takeaways for FLS

Opinionated, given the constraints in `0. idea.md`:

1. **Per-course form schema is the core primitive.** Don't piggyback on user profile fields (Moodle's mistake). Model: `ApplicationConfig` (per course) → has many `ApplicationQuestion`s with type, order, required, validation.
2. **Multi-step support from day 1**, single-step is the default. `ApplicationConfig` has ordered "steps", each with N questions. A 1-step config *is* a single-page form. Avoids painting into a corner later.
3. **Autosave drafts.** Hardest UX requirement to bolt on later. HTMX makes per-field autosave cheap.
4. **Lock on submit, "request changes" to unlock.** Mirrors UCAS/Slate. No free editing after submission.
5. **States v1**: `draft`, `submitted`, `changes_requested`, `approved`, `rejected`, `withdrawn`. Defer `under_review`, `waitlisted`, `expired`.
6. **Global applications inbox per site**, filterable by course/cohort/status/date. Don't make admins go course-by-course.
7. **File uploads are a question type**, not a separate concept. Per-question: max size, MIME allowlist, max count. Dedicated path with role-gated download.
8. **Notification templates must include course name + link.** Hard-learned from Moodle complaints.
9. **Audit trail on every state transition** (who, when, optional reviewer note + optional applicant-facing message). Cheap now, painful to retrofit.
10. **Approval ≠ enrolment** (per idea file). Add one-click "Approve and enrol in cohort X" convenience for the common case.
11. **Skip v1 (but don't architect them out)**: rubric scoring, multi-reviewer assignment, waitlist, cohort intake windows, branching/conditional questions, in-app identity verification, payment integration, decision-release batching.
12. **Multi-tenancy**: `ApplicationConfig`, `Application`, `ApplicationResponse`, uploaded files all need `SiteAwareModel`. Reviewers see only their site. Standard FLS pattern.

## Sources

- https://moodle.org/plugins/enrol_apply
- https://github.com/emeneo/moodle-enrol_apply
- https://moodle.org/plugins/enrol_gapply
- https://moodledev.io/docs/4.5/apis/plugintypes/enrol
- https://docs.openedx.org/projects/wordpress-ecommerce-plugin/en/latest/how-tos/create_enrollment_requests_manually.html
- https://edx.readthedocs.io/projects/edx-installing-configuring-and-running/en/open-release-koa.master/configuration/customize_registration_page.html
- https://github.com/open-craft/custom-form-app
- https://discuss.openedx.org/t/pluggable-access-control-both-viewing-and-enrolling-in-a-course/803
- https://www.coursera.org/degrees/omie/admissions
- https://www.coursera.org/degrees/bachelor-of-science-computer-science-london/admissions
- https://www.colorado.edu/cs/academics/online-programs/mscs-coursera/faq
- https://www.iit.edu/registrar/coursera/coursera-faqs/coursera-pathway-transfer-credit-evaluation-process-bachelor-information-technology
- https://mitx-micromasters.zendesk.com/hc/en-us/articles/360037703611-What-is-the-application-timeline-for-the-MIT-Economics-DEDP-Master-s-program
- https://news.mit.edu/2017/first-micromasters-learners-earn-credentials-0620
- https://www.ycombinator.com/howtoapply
- https://zyner.io/blog/yc-application-review-process
- https://ophyai.com/blog/company-guides/andela-interview-guide
- https://help.andela.com/hc/en-us/articles/48808870236307-AI-Engineering-Bootcamp-timeline-and-milestones
- https://www.bloomtech.com/article/how-to-apply-to-bloomtech-guide
- https://www.bloomtech.com/admissions
- https://www.coursereport.com/blog/lambda-school-isa-income-share-agreement
- https://www.alxafrica.com/selection-process/
- https://www.alxafrica.com/alx-selection-policy/
- https://technolutions.com/admissions
- https://knowledge.technolutions.net/docs/identity-verification
- https://www.targetx.com/solutions/increase-enrollment-with-recruitment-suite/application-review/
- https://trailhead.salesforce.com/content/learn/modules/recruitment-and-admissions-with-education-cloud/manage-application-reviews
- https://kissflow.com/solutions/education/student-application-review-workflow/
- https://www.ucas.com/applying/after-you-apply/clearing-and-results-day/results-day/what-your-application-status-means
- https://www.formassembly.com/blog/multi-step-form-best-practices/
- https://designlab.com/blog/design-multi-step-forms-enhance-user-experience
- https://ventureharbour.com/form-design-best-practices/
- https://financialaid.nd.edu/contact/resources/policies/federal-verification/
- https://plaid.com/docs/identity-verification/
