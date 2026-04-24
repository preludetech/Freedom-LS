# SACAA Functionality Audit — Implementation Status

**Scope:** SACAA 141.07.1 §1 (E-Learning) and §2 (Virtual Training)
**Date:** 2026-04-24
**Source regulation:** [`sacaa-requirements.md`](./sacaa-requirements.md)

## How to read this document

For every software requirement in SACAA 141.07.1, this audit says:

- **What the regulation requires** — in plain English, with the risk category it applies to where relevant.
- **Where we stand today** — what FLS already does, or which `spec_dd/` spec plans to do it.
- **What's missing and why it matters** — the concrete gap and the regulator's reason for caring.

### Status legend

- ✅ **Implemented** — feature is live in code and meets the clause.
- ⚠️ **Partial** — some of the requirement is in place; specific gaps noted.
- 📋 **Spec planned** — documented in `spec_dd/` but not yet implemented.
- ❌ **Gap** — no spec and no implementation.

### About the SACAA risk matrix

SACAA scales controls by the consequence of a training failure:

| Cat | Example | Authentication required | Extra exam controls |
|---|---|---|---|
| 1 | Logging flight experience | Self-declaration | None |
| 2 | Lithium-battery training, CRM | Username + password | None |
| 3 | Welding, RNAV | Username + password + signed forms | Instructor verification during practical |
| 4 | Dangerous Goods knowledge test | Username + password + **rigorous identity check during the exam** (biometrics / proxy / controlled environment) + examiner signature | 15 photos / continuous video / invigilator / auto-fail on face change |
| 5 | Initial licence / rating | SACAA-authorised exam centre, physical ID on entry | Per SOP |

This matters because several requirements only activate at Cat 3, Cat 4, or Cat 5 — the system does not need to apply the strictest controls to, say, a self-study CRM module.

---

## §1 — E-Learning System

### 1(a) — Identification system and password

**What the regulation requires:**
"An acceptable identification system and password as a minimum-security feature in alignment with the risk matrix." Reading the matrix: self-declaration at Cat 1, unique-password login at Cat 2–4, and a physical SACAA exam centre at Cat 5. **MFA is not specified at any level.** The rigorous identification at Cat 4–5 is about the *exam moment*, not the login — that requirement is handled by clause 1(b).

**Where we stand:** ✅ Implemented for Cat 1–4 login needs.
- Email + password login via custom `User` model at `freedom_ls/accounts/models.py:62`.
- Argon2 + PBKDF2 + BCrypt password hashing at `config/settings_base.py:161-166`.
- Mandatory email verification: `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (`config/settings_base.py:252`).
- Brute-force lockout via django-axes: 5 failed attempts / 1 hour cool-off (`config/settings_base.py:224-230`, delivered by the done security-audit spec).

**What's missing and why it matters:** Nothing for baseline SACAA compliance. The planned `spec_dd/1. next/MFA/` is security *hardening* for educator and admin accounts — it guards against account takeover and reduces lateral-movement risk after a phishing incident, but it is not required by SACAA. **Do not treat MFA as a compliance blocker.** We should still build it because the specs that do matter for compliance (moderation, exam records, certificates) all depend on educator accounts being trustworthy, and an unprotected admin password is the weakest link in that chain.

---

### 1(b) — Rigorous identification during Cat 4–5 exams

**What the regulation requires:**
For Risk Cat 4–5 evaluations the system must take **at least one** of: 15 random identifiable photos, continuous video, live invigilator monitoring, or automated exit + failure if the testee's face changes, the testee leaves camera view, another person enters frame, or any voice is detected. This is how SACAA prevents impersonation and collusion in high-stakes theory exams.

**Where we stand:** 📋 Spec planned, but incomplete.
- `spec_dd/1. next/00. exam-proctering/` covers a single selfie at exam start, tab/focus-loss logging, and concurrent-session prevention.

**What's missing and why it matters:**
The proctoring spec does not yet capture any of the four mandated monitoring modes:
- Periodic random photo capture (≥15 shots).
- Continuous webcam video recording.
- Live invigilator dashboard.
- Automatic fail triggers on face-mismatch, out-of-frame, multi-person, or voice detection.

**Why SACAA cares:** a selfie at the start of the exam does not stop a qualified friend from taking over the keyboard at minute five. Without mid-exam monitoring, exam results for Cat 4–5 subjects are not defensible in an audit. **Action:** extend `00. exam-proctering` with at least the "random photos" option (cheapest to implement browser-side) before any Cat 4–5 course is offered.

---

### 1(c) — Exam records must be immutable

**What the regulation requires:**
"Exam records shall be maintained and shall not be able to be deleted or manipulated." The regulator's concern is retrospective auditing — if a student's result is later contested, the original record must still be exactly what was written at exam time. An inspector must be able to verify no one has tampered with scores after the fact.

**Where we stand:** ❌ Gap.
- `FormProgress` and `QuestionAnswer` (`freedom_ls/student_progress/models.py:123, 503`) are ordinary Django models with CASCADE deletes. If the parent `Form` is removed, the students' attempts go with it.
- A management command `freedom_ls/content_engine/management/commands/danger_content_delete.py` permits hard deletion.
- No audit trail, no soft-delete, no append-only store, no signed records.

**What's missing and why it matters:**
We need an append-only record of every exam submission that cannot be altered by an educator, an admin, or even a developer with database access (short of physically tampering with the database). **Why it matters:** the current architecture means a single `DELETE` statement, or an unreviewed migration, could erase years of Cat 4–5 exam evidence. That is an audit-failing risk for any organisation accredited to deliver regulated aviation training.

**Suggested fix:** a new spec for an immutable exam audit log — e.g. an append-only table that mirrors `FormProgress` submissions, signed with a site-level key, with deletes blocked at the DB permission level.

---

### 1(d) — Moderation workflow and proof of moderation

**What the regulation requires:**
An acceptable form of moderation must be demonstrated. If a moderator finds a question was defective and awards the student the mark anyway, the moderator's decision and the awarded mark must be recorded alongside the original result. The regulator's point is that marks on the system cannot simply be edited — moderation must be *visible* as a recorded decision, not an invisible override.

**Where we stand:** ❌ Gap.
- `spec_dd/1. next/00. exam-proctering/` mentions a grader dashboard but no moderation approval / sign-off workflow.
- No code.

**What's missing and why it matters:**
We need a moderation model where (1) a moderator reviews an exam attempt, (2) can flag a question as defective, (3) can record a mark override with reason, and (4) the override is stored immutably alongside the original score rather than replacing it. **Why it matters:** without this, educators must "fix" exam results by editing scores directly, which violates 1(c) as well. A compliant moderation flow is how the regulator distinguishes legitimate mark adjustments from quiet grade inflation.

---

### 1(e) — Revised questions blocked from random pool, retained for audit

**What the regulation requires:**
When a question is changed (reworded, re-answered, re-categorised), it must be removed from the pool of randomly selected questions going forward, but must remain in the database so auditors can see what version each historical student saw. This prevents a provider from silently "correcting" a question mid-course and erasing the evidence of the old version.

**Where we stand:** ❌ Gap.
- `FormQuestion` / `QuestionOption` at `freedom_ls/content_engine/models.py:323, 372` have no version history and no `is_retired` / `superseded_by` fields.

**What's missing and why it matters:**
We need question versioning — every edit becomes a new version; the old version is frozen and kept; random-selection queries only draw from the latest active versions; historical attempts remember which version they answered. **Why it matters:** after a student complaint, the regulator will ask "show me the exact question they saw on day X". We currently cannot answer that honestly if the question has since been edited.

---

### 1(f) — Backups or geographically-diverse storage

**What the regulation requires:**
Training information must have backups or be stored on multiple servers, so that a single failure cannot destroy records.

**Where we stand:** ⚠️ Partial — infrastructure responsibility.
- `spec_dd/3. done/2026-03-13_21:21_security-audit/` §7 prescribes encrypted database backups, offsite storage, and tested restore procedure.

**What's missing and why it matters:**
This is largely operational — an application can't enforce its own backups. The gap is in documenting and evidencing the backup regime (frequency, retention, last successful restore test) so it can be shown to an auditor. Tracked in the deployment/runbook, not in the codebase.

---

### 1(g) — Register of course revisions

**What the regulation requires:**
A register of course changes must be kept safely, preferably with its own backup. SACAA wants to see a traceable list of what changed in a course, when, and why — so they can tell whether a student was trained on the accredited version.

**Where we stand:** ❌ Gap.
- Course content lives in `demo_content/` and is git-versioned, which is a technical change trail but not an in-app register a compliance officer can scan.
- No in-app table of course changes, no approval log, no change-authorship tracking surfaced in the admin.

**What's missing and why it matters:**
We need an in-app course-change register that records: course, change summary, author, timestamp, approver, version ID. **Why it matters:** git log is not acceptable evidence to a non-technical auditor, and it doesn't record *approval* — only what was committed. A proper register ties every content change to an approving person, which is what the regulator actually wants to see.

---

### 1(h) — Auto-assess when exam timer expires

**What the regulation requires:**
When the exam time runs out, the system must submit whatever answers the student has given and grade them — even if the student hasn't finished. Students cannot "escape" a failing attempt by simply closing the tab before submitting.

**Where we stand:** 📋 Spec planned.
- `spec_dd/1. next/00. exam-proctering/` §2 specifies a countdown timer with auto-submit on expiry.

**What's missing and why it matters:**
Implementation work on the planned spec. `FormProgress` currently has no time-limit or auto-submit fields. Until the spec lands, any timed exam can be escaped by closing the tab. **Why it matters:** without forced submission, the pass/fail decision depends on student voluntariness, which is meaningless for compliance.

---

### 1(i) — Adequate time to complete training

**What the regulation requires:**
Outside of explicitly timed modules, students must be given enough time to complete the training — you can't set an unreasonable deadline that effectively forces students to rush through.

**Where we stand:** ✅ Implemented by default.
- Learning content has no forced time limit. Deadlines are opt-in through `CohortDeadline` / `StudentDeadline` in `freedom_ls/student_management/models.py` (around lines 143 and 190), and educators choose whether they are hard or soft.

**What's missing:** Nothing. Setting "adequate time" is a pedagogical call for the course author; the system does not impose hidden timeouts.

---

### 1(j) — Minimum tutorial hours before the knowledge test

**What the regulation requires:**
For courses that have a minimum tutorial-time requirement, the system must prevent the student from writing the knowledge test until they have actually spent those hours on the course and completed all its modules.

**Where we stand:** ❌ Gap.
- No time-on-content tracking at all.
- No gate that checks "has the student logged X hours in this course" before the knowledge test becomes available.

**What's missing and why it matters:**
We need: (a) per-module expected-duration configuration, (b) live time-on-content tracking for each student, (c) a gate on the knowledge-test page that checks the accumulated time. **Why it matters:** several aviation subjects specify minimum study hours by regulation — skipping those hours undermines the entire reason for accreditation, and a provider that can't prove study hours can't defend the accreditation.

---

### 1(k) — No fast-forwarding to the knowledge test

**What the regulation requires:**
The programme must be built so that a student cannot jump straight to the knowledge test; they must complete the self-assessments and content that lead up to it.

**Where we stand:** ⚠️ Partial.
- `freedom_ls/student_interface/utils.py:49-131` runs a state machine that marks items BLOCKED / READY / IN_PROGRESS / COMPLETE based on the order of their siblings. Topic completion uses `TopicProgress.complete_time`; form completion uses `FormProgress.completed_time`.

**What's missing and why it matters:**
The guard is *positional* — the gate depends on siblings appearing in a particular order. A course author who accidentally places the knowledge test ahead of a prerequisite tutorial opens a bypass. **Why it matters:** declarative prerequisites ("this content requires completing X, Y, Z first") would make the guard robust to authoring mistakes, which a regulator will eventually find. This is a model extension rather than a new concept.

---

### 1(l) — Interaction check or auto-logout every 2 min 30 s

**What the regulation requires:**
During learning the programme must regulate interaction every 2 minutes 30 seconds — i.e., if the student hasn't interacted within that window, log them out automatically. The intent is to prevent a student from "parking" a training session running in the background while they do other things, and to make sure the person at the keyboard is actually learning.

**Where we stand:** ❌ Gap.
- `spec_dd/1. next/session-timeout-strategy/` is at idea stage and explores several options but does not specify a 2m30s idle timeout.
- `SESSION_COOKIE_AGE = 1209600` in `config/settings_prod.py:40` — the current absolute cap is two weeks.
- No idle-detection middleware, no client-side activity ping.

**What's missing and why it matters:**
Two pieces are needed: server-side middleware that expires a session after 2m30s of no activity, and client-side JavaScript that pings the server on genuine interaction (clicks, scrolls, key presses — not mere cursor movement). **Why it matters:** without this, a student can clock up study-hour credit simply by leaving a tab open overnight, which invalidates the 1(j) minimum-tutorial-hours gate even if we build it.

---

### 1(m) — Disturbance or logout during exam = fail

**What the regulation requires:**
During an exam or knowledge test, any disturbance or logout counts as a fail. The regulator's logic: mid-exam disconnections are frequently attempts to consult notes or collaborate; if the rule is "disconnect = fail", the incentive to try disappears.

**Where we stand:** 📋 Spec planned, partial.
- `spec_dd/1. next/00. exam-proctering/` logs tab/focus changes and allows a grace period for reconnection, but it does not automatically fail on disruption.

**What's missing and why it matters:**
A per-exam "auto-fail on disturbance" policy, enforced automatically for Cat 4–5 exams. **Why it matters:** without this the proctoring telemetry is only observational, and the operator ends up making manual judgement calls on "was this disconnection bad enough to fail them?" — which is exactly the discretion the regulator wants the system to remove.

---

### 1(n) — Instructor or SME available to assist the learner

**What the regulation requires:**
The learner must be able to reach an instructor or subject matter expert for help while using the programme.

**Where we stand:** ❌ Gap.
- `spec_dd/0. drafts/messages/` is at draft stage. It sketches educator↔student messaging but is not yet a finished spec.
- The educator interface has cohort and progress views but no direct-contact channel.

**What's missing and why it matters:**
A supported channel for a student to reach a named SME — email thread, in-app messaging, or similar. **Why it matters:** without this, the programme relies on informal contact (calls, personal email) which cannot be audited. Promote the draft messaging spec and use it as the one official channel.

---

### 1(o) — Well-organised courseware with menus, modules, instructions

**Where we stand:** ✅ Implemented.
- Content hierarchy Course → CoursePart → Topics/Forms/Activities in `freedom_ls/content_engine/models.py:148-207`.
- Ordered children via `ContentCollectionItem.order` (around line 234).
- Student navigation in `freedom_ls/student_interface/templates/` (`course_home.html`, `course_topic.html`) — table of contents, breadcrumbs, prev/next.

---

### 1(p) — Logical flow / knowledge building order

**Where we stand:** ⚠️ Partial.
- `order` fields on `ContentCollectionItem` and `FormPage` define sequence, and the state machine described in 1(k) enforces it.
- What's missing is shared with 1(k): prerequisites are positional, not declarative. For most content this is fine; for regulated courses it needs hardening.

---

### 1(q) — Usability / HCI

**Where we stand:** ✅ Implemented, with more planned.
- TailwindCSS responsive layout, HTMX progressive enhancement, Alpine.js for lightweight interactivity.
- Semantic HTML and viewport meta in `freedom_ls/base/templates/_base.html`.
- Playwright end-to-end tests cover the main flows.
- `spec_dd/1. next/03. make-accessable/` schedules further accessibility work (WCAG coverage).

---

### 1(r) — Audio and visual instructions

**Where we stand:** ✅ Implemented.
- `File` model supports IMAGE / DOCUMENT / VIDEO / AUDIO (`freedom_ls/content_engine/models.py:403-407`).
- Cotton markdown components registered in `config/settings_base.py:231-236`: `c-youtube`, `c-picture`, `c-pdf-embed`, `c-file-download`, `c-callout`, `c-content-link`.

The regulation is phrased as "should include" — it's a courseware-author responsibility, and the platform supports everything the author needs.

---

### 1(s) — Formative and summative tests

**Where we stand:** ✅ Implemented.
- `FormStrategy.QUIZ` (summative with pass %) and `FormStrategy.CATEGORY_VALUE_SUM` (formative/diagnostic) at `freedom_ls/content_engine/models.py:24-29`.
- Question types: multiple choice, checkboxes, short text, long text.
- Scoring logic in `freedom_ls/student_progress/models.py:123-501`.

---

### 1(t) — Pass mark must be at least the regulated minimum (reference: 75%)

**What the regulation requires:**
Pass marks must not be set below the prescribed minimum for the subject. SACAA's reference minimum is 75% for most knowledge tests.

**Where we stand:** ⚠️ Partial.
- `Form.quiz_pass_percentage` is a configurable positive-small-integer field at `freedom_ls/content_engine/models.py:263-267`.
- `FormProgress.passed()` compares the score against the configured value at `freedom_ls/student_progress/models.py:162`.

**What's missing and why it matters:**
Nothing stops an educator entering a pass mark of 50% on a SACAA-regulated knowledge test. **Why it matters:** one misconfiguration and students can be marked as competent without meeting the regulated bar.

**Suggested fix:** a per-course "SACAA-regulated" flag that clamps the pass-mark floor to a configured minimum (e.g. 75%), with admin-level validation that refuses to save a lower value.

---

### 1(u) — Maximum of two rewrites, then redo the course

**What the regulation requires:**
After two failed rewrites of a knowledge test (i.e. three attempts total), the student must redo the course before they can attempt the exam again.

**Where we stand:** ❌ Gap.
- `spec_dd/1. next/00. exam-proctering/` supports configurable retake limits but does not automate "force course restart after N failures".
- `FormProgress.get_or_create_incomplete()` at `freedom_ls/student_progress/models.py:173-185` currently permits unlimited retries with no attempt counter.

**What's missing and why it matters:**
An attempt counter on exam attempts, plus logic that: disables further exam access after attempt 3, requires course progress to be reset, and re-gates the exam behind the full course flow. **Why it matters:** the rule exists to stop a student from grinding through the same exam 15 times and passing by memorisation alone — the third failure is supposed to force real learning.

---

### 1(v) — Post-exam results and remediation to 100%

**What the regulation requires:**
The student receives their results after the exam, and where they are declared competent the system must remediate them to 100% — i.e. walk them through every question they got wrong until they understand the correct answer.

**Where we stand:** ⚠️ Partial.
- `Form.quiz_show_incorrect` (`freedom_ls/content_engine/models.py:259-261`) optionally reveals the correct answers after submission.
- `FormProgress.get_incorrect_quiz_answers()` at `freedom_ls/student_progress/models.py:448-500` returns the incorrect answers with the correct options; `freedom_ls/student_interface/views.py:434` displays them.

**What's missing and why it matters:**
Today the student *sees* which answers were wrong. The regulation wants an active remediation loop — the student must re-engage with each wrong answer until they confirm understanding, not just scroll past them. **Why it matters:** passing at 75% means a quarter of the material is still wrong in the student's head; SACAA requires the system to close that gap before the student leaves.

---

### 1(w) — Director approval of the programme

Operational / non-software — see appendix.

---

### 1(x) — Identity management and authentication built into the system

**What the regulation requires:**
Proper identity management and authentication — knowing who is using the system and controlling what they can do.

**Where we stand:** ⚠️ Partial, and substantially covered by multiple planned/done specs.
- Login basics: see 1(a).
- Role-based access control from the done spec `spec_dd/3. done/2026-03-09_11:26_role_based_permission_system_foundations/` (django-guardian).
- Planned work on authorization and data protection:
  - `spec_dd/1. next/educator-idor-fixes/` — IDOR vulnerability fixes in the educator interface.
  - `spec_dd/1. next/educator-interface-permission-checks/` and `educator-interface-permission-config/`.
  - `spec_dd/1. next/student_content_access_control/`.
  - `spec_dd/1. next/encryption-at-rest/`.
  - `spec_dd/1. next/MFA/` — admin/educator MFA (hardening, not compliance).
- Multi-tenant scoping via `freedom_ls/site_aware_models/` auto-filters all queries by site so users cannot even see other tenants' records.

**What's missing and why it matters:**
The individual planned specs address real security findings (IDOR, field encryption, etc.). The compliance blocker is that those specs need to land — the current production branch has the foundations but not the full set of fixes.

---

### 1(y) — Hosted within the Republic + information protection mechanisms

**What the regulation requires:**
Two things: (1) the system must be hosted within South Africa, and (2) there must be information-protection mechanisms in place.

**Where we stand:** ⚠️ Partial.
- Information protection (specs planned): `spec_dd/1. next/00. privacy-compliance/` (POPIA/GDPR), `encryption-at-rest/`, `CSP-rollout/`, `CORS-configuration/`, `DAST-scanning/`, `cookie-banner/`; plus the done `spec_dd/3. done/2026-03-13_21:21_security-audit/`.
- Code: HTTPS enforcement, HSTS, secure cookies, frame-deny, referrer policy in `config/settings_prod.py:15-37`.
- Hosting: `DB_HOST` is env-configurable (`config/settings_prod.py:54`), so hosting location is whatever the deployment chooses.

**What's missing and why it matters:**
"Within the Republic" is a deployment decision that must be enforced by contract and runbook, not by code. **Why it matters:** choosing a non-SA cloud region in AWS/GCP/Azure would make the system non-compliant without any code change. The runbook should name the allowed regions and the infra-team should treat that as a control.

---

### 1(z) — Retain all information for at least 5 years

**What the regulation requires:**
Every record — exam results, attendance, moderator notes, content history — must be kept for a minimum of five years.

**Where we stand:** 📋 Spec planned.
- `spec_dd/1. next/00. privacy-compliance/` defines an `enforce_retention` management command with configurable per-model retention periods, supporting both hard delete and anonymisation.

**What's missing and why it matters:**
The spec exists, but the aviation-specific defaults aren't yet baked in. Today, the CASCADE-delete problem described in 1(c) means records can be destroyed well before five years. **Why it matters:** an audit two years from now will ask for today's records. The privacy-compliance spec must pin minimum retention at 5y for SACAA-regulated models (exam records, attendance, moderator notes), and the immutability fix from 1(c) must land so retention isn't silently defeated by a DELETE.

---

## §2 — Virtual Training System

### 2(a) — Online classroom-capable learning management platform

**What the regulation requires:**
A platform capable of delivering online classroom training — i.e. real-time, instructor-led sessions.

**Where we stand:** ⚠️ Partial.
- FLS is strictly asynchronous today: the apps `content_engine`, `student_interface`, `educator_interface`, `student_management`, `student_progress` cover pre-recorded or self-paced learning. No webinar, video-conferencing, or live-session features exist.

**What's missing and why it matters:**
If the business wants to deliver virtual training (as opposed to just e-learning), we need a live-session feature — either a first-party implementation or a managed integration with Zoom/Jitsi/BigBlueButton. **Why it matters:** many §2 clauses (recording retention, chat-based tasks, closed sessions) are meaningless without a synchronous session to be recorded, chatted in, or closed. If we never offer virtual training, §2 as a whole is out of scope — but that is a business decision, not an implementation one.

---

### 2(b) — Stable, suitable interface with the candidate

**Where we stand:** ✅ Implemented — shared assessment with 1(q).

---

### 2(c) — Full operator control and confidentiality of candidate data

**Where we stand:** 📋 Spec planned, with strong foundations.
- Specs: `spec_dd/1. next/00. privacy-compliance/`, `encryption-at-rest/`, plus done `spec_dd/3. done/2026-03-09_11:26_role_based_permission_system_foundations/`.
- Code: multi-tenant site isolation via `SiteAwareModel` / `SiteAwareManager` (`freedom_ls/site_aware_models/models.py`) auto-filters every query by site. Enrollment-gated views in `freedom_ls/student_interface/` confirm registration before rendering content.

**What's missing and why it matters:**
Encryption-at-rest and the privacy-compliance work need to land. Until then, operator-level controls over data exist but evidence of those controls (audit logs, export, deletion on request) is weaker than POPIA expects.

---

### 2(d) — Unmanipulable candidate training file + keep webinar recordings for 2 years

**What the regulation requires:**
Two distinct things: (1) the candidate's digital training file must be tamper-proof to third parties, and (2) webinar recordings must be retained for two years for audit.

**Where we stand:** ❌ Gap on both counts.
- Progress records (`TopicProgress`, `FormProgress`, `CourseProgress` at `freedom_ls/student_progress/models.py:123, 523, 547`) carry timestamps but nothing prevents tampering.
- No webinar capture or retention because there are no webinars (see 2(a)).

**What's missing and why it matters:**
Part (1) is the same problem as 1(c), and the same immutable-audit-log fix will close both.
Part (2) depends on 2(a). **Why it matters:** the two-year retention isn't arbitrary — it's the typical timeframe for a student to contest a training outcome. Without recordings, disputes become he-said/she-said.

---

### 2(e) — Written reference material other than audio/visual

**Where we stand:** ✅ Implemented.
- Markdown content on Topics / Activities / FormContent with cotton components `c-pdf-embed` and `c-file-download` for downloadable resources.

---

### 2(f) — A matrix of tutorials mapped to accomplishment levels

**What the regulation requires:**
A structured map of tutorials to skill levels, so that students' progression can be measured against pre-set levels of accomplishment.

**Where we stand:** ❌ Gap.
- No competency mapping, no learning-path or level concept in the models.

**What's missing and why it matters:**
A competency / level model that groups content into explicit skill levels, and tracks a student's position against those levels. **Why it matters:** aviation training often pays in stages of qualification — "basic", "intermediate", "advanced" — and the regulator wants to see that students genuinely move through those levels rather than just completing an arbitrary pile of content.

---

### 2(g) — Database of knowledge progress questions and tasks

**Where we stand:** ✅ Implemented.
- `FormQuestion` + `QuestionOption` at `freedom_ls/content_engine/models.py:323, 372`.
- Learner responses in `QuestionAnswer` at `freedom_ls/student_progress/models.py:503`.
- PostgreSQL-backed, so durable and queryable.

---

### 2(h) — Audio and visual training

**Where we stand:** ✅ Implemented — shared assessment with 1(r).

---

### 2(i) — Tasks handled via chat, assessed by SME

**What the regulation requires:**
Courses that require task submissions should handle them via the chat function, with the SME assessing the task in-channel.

**Where we stand:** ❌ Gap.
- `spec_dd/0. drafts/messages/` is at draft stage.
- No task-submission or task-assessment flow.

**What's missing and why it matters:**
The drafted messaging spec should be promoted and extended to handle (a) task assignment, (b) task submission, (c) SME assessment/feedback, (d) evidence of the assessment attached to the student's record. **Why it matters:** without this channel, task-based assessment happens out-of-band (email, WhatsApp) and leaves no record — which undermines both 2(c) (operator control of data) and 2(d) (immutable candidate file).

---

### 2(j) — Closed system with session locking

**What the regulation requires:**
Live virtual sessions must enforce digital verification so that only enrolled candidates can join, and no one else can slip in.

**Where we stand:** ⚠️ Partial, for exams.
- For exams: `spec_dd/1. next/00. exam-proctering/` specifies concurrent-session prevention and identity verification on start.
- For courses: access is gated by `UserCourseRegistration` / `CohortCourseRegistration` in `freedom_ls/student_management/models.py` (lines ~46–124).

**What's missing and why it matters:**
For live virtual sessions: nothing, because there are no live virtual sessions (see 2(a)). This clause becomes actionable only once 2(a) is on the roadmap.

---

### 2(k) — Random monthly manual security audits

Operational / non-software. Automated scanning via `spec_dd/1. next/DAST-scanning/` and the done security-audit spec produces artefacts that can evidence the monthly reviews, but the reviews themselves are an operational commitment.

---

### 2(l) — All information under operator control and protected

**Where we stand:** 📋 Spec planned — same specs as 2(c).

---

### 2(m) — Provide a subject matter expert, assessor, and moderator, suitably qualified

**What the regulation requires:**
The operator must provide appropriately qualified SMEs, assessors, and moderators — real people with real qualifications.

**Where we stand:** ⚠️ Partial.
- `spec_dd/3. done/2026-03-09_11:26_role_based_permission_system_foundations/` gives us an extensible role system. "Educator" and "admin" exist; "moderator" and "assessor" do not yet.
- No field anywhere to record a person's qualifications.

**What's missing and why it matters:**
Define moderator and assessor roles in the RBAC system, and add optional qualification fields on the educator profile (certification number, issuing body, date, expiry). **Why it matters:** when an auditor asks "who moderated this exam and what authority did they hold", the operator must answer from the system, not from a spreadsheet.

---

### 2(n) — Proof of moderation

**Where we stand:** ❌ Gap — same root cause and fix as 1(d).

---

### 2(o) — Digital PDF certificate, randomly numbered, verifiable by quick-search

**What the regulation requires:**
On completion the candidate receives a PDF certificate that is digitally numbered (random / unpredictable), properly referenced, and verifiable through a system quick-search function — i.e. a third party can check a certificate number and confirm its authenticity.

**Where we stand:** ❌ Gap.
- Completion is tracked via `CourseProgress.completed_time` at `freedom_ls/student_progress/models.py:547-573`.
- No `Certificate` model, no PDF generation, no certificate numbering scheme, no public verification endpoint.

**What's missing and why it matters:**
A new spec covering: a Certificate model with random, collision-resistant numbering; PDF generation with the training organisation's branding; optional digital signature; a public verification endpoint (e.g. `/verify/<certificate-number>`) that confirms the certificate is real and shows who holds it. **Why it matters:** in aviation, certificates are checked by employers, licensing authorities, and other operators. If the certificate can't be verified by an outsider, it isn't trusted, and the training isn't recognised in practice.

---

### 2(p) — Accredited courses must follow approved content and flow

**What the regulation requires:**
Once a course has been accredited, the provider must deliver it as approved — no silent content swaps, no skipped sections.

**Where we stand:** ⚠️ Partial.
- Course content in `demo_content/` is git-versioned and deployed immutably, giving an external change trail.
- There is no in-app publish/approve workflow, no draft-vs-live state, no tamper-evident flow-compliance tracking.

**What's missing and why it matters:**
An in-app content-approval workflow (draft → reviewer → published) and a record of which course version was delivered to which student. **Why it matters:** if content can be edited in place without an approval step, the accredited version and the delivered version can drift silently. The regulator wants to see that any delivered course matches a specific, approved version.

---

## Gaps summary

| Clause | Gap | Suggested action |
|---|---|---|
| 1(b) | No 15-photo / video / voice monitoring for Cat 4–5 | Extend `00. exam-proctering` |
| 1(c) | Exam records deletable via CASCADE | New spec: immutable exam audit log |
| 1(d), 2(n) | No moderation workflow or sign-off | New spec: moderation + sign-off |
| 1(e) | No question versioning | New spec or extend `00. exam-proctering` |
| 1(g) | No in-app course-change register | New spec |
| 1(j) | No minimum-tutorial-time gate | New spec (depends on time-on-content tracking) |
| 1(k) | Prerequisites are positional only | Extend sequencing model to declarative prerequisites |
| 1(l) | No 2m30s idle logout | Extend `session-timeout-strategy` |
| 1(m) | No auto-fail on disturbance | Extend `00. exam-proctering` |
| 1(n), 2(i) | No SME chat / task workflow | Promote `0. drafts/messages` |
| 1(t) | No enforced SACAA-minimum pass mark | Small change: per-course regulated flag |
| 1(u) | No 2-rewrite-then-redo rule | Extend `00. exam-proctering` |
| 1(v) | No active remediation loop to 100% | Extend `00. exam-proctering` |
| 1(z), 2(d) | No 5y / 2y retention defaults | Extend `00. privacy-compliance` |
| 2(a) | No synchronous classroom | New spec (only if virtual training is in scope) |
| 2(d) | No webinar capture & retention | Depends on 2(a) |
| 2(f) | No competency-level matrix | New spec |
| 2(m) | No moderator / assessor role + qualifications | Extend RBAC |
| 2(o) | No PDF certificate with public verification | New spec |
| 2(p) | No in-app content approval workflow | New spec |

---

## Non-software / operational requirements

These clauses depend on people, contracts, or infrastructure rather than on code. They are listed here so they aren't lost in the engineering roadmap:

- **1(f) Backups / multi-server storage** — Infrastructure. The done security-audit spec prescribes encrypted offsite backups and tested restore. Evidence lives in the runbook.
- **1(p) Logical flow** — Course-author's responsibility; the platform supports ordered progression.
- **1(q) Usability** — Ongoing product/UX concern; supported by the codebase.
- **1(r) Audio & visual content** — Course-author's responsibility; the platform supports it.
- **1(w) Director approval of programme and system** — Governance process owned by the training organisation's leadership.
- **1(y) Hosting within the Republic** — Deployment/contract decision. Not enforced by code. Document in the deployment runbook; constrain the infra team to SA regions.
- **2(b) Stability** — Monitoring/SRE concern.
- **2(h) Audio-visual training** — Course-author responsibility.
- **2(k) Random monthly manual security audits** — Operational commitment. Automated scanning (DAST, Bandit, Semgrep, pip-audit, axes logs) provides evidence; the monthly cadence is a process.
- **2(m) Qualifications of SME / assessor / moderator** — Staffing / HR responsibility. The system can assign roles; it cannot validate real-world qualifications.
- **2(p) Adherence to approved content** — Content-governance policy. Technical enforcement gap captured in the main audit.
