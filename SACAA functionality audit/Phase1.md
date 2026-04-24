# Phase 1 — Risk Category 2: Enrichment Training

**Goal:** Deliver development / enrichment training on FLS. Not regulated, but auditable internally and potentially approved by SACAA. Typical subjects: Lithium Battery handling, Thunderstorm avoidance, Crew Resource Management (CRM).

**Reference:** see [implementation.md](./implementation.md) for the full audit this phase draws from.

---

## What Cat 2 requires

From the SACAA risk matrix (`sacaa-requirements.md` row for Cat 2):

| Dimension | Cat 2 rule |
|---|---|
| Authentication | Logon via unique password |
| Standards | Internally defined; potentially approved by SACAA |
| Record keeping | Audit trail |
| Moderation | Internal |
| Assessment | Online knowledge test with random questions from a master list (or randomised question/answer order) |
| Remediation | Any incorrect answer immediately remediated as per online database |
| Security | Internal annual audit of database access + internal audit trail of results |

The matrix is the backbone. The generic (a)–(z) clauses also apply, but at their lightest interpretation — no biometrics, no 5-year retention, no examiner signatures.

---

## SACAA clauses that apply in Phase 1

| Clause | Summary | Current status |
|---|---|---|
| 1(a) | Unique password login | ✅ Implemented |
| 1(c) | Exam records cannot be tampered with (internal audit trail) | ❌ Gap — records are deletable via CASCADE |
| 1(d) | Internal moderation workflow | ❌ Gap |
| 1(e) | Revised questions blocked from random pool, old version retained | ❌ Gap |
| 1(f) | Backups / multi-server storage | ⚠️ Operational — documented in done security audit |
| 1(g) | Course-revision register | ❌ Gap |
| 1(h) | Auto-submit on timer expiry (for any timed knowledge test) | 📋 Planned in `00. exam-proctering` |
| 1(i) | Adequate time for training | ✅ Implemented by default |
| 1(k) | No fast-forwarding to the knowledge test | ⚠️ Partial — positional gating only |
| 1(l) | Interaction check or auto-logout every 2 min 30 s | ❌ Gap |
| 1(n) | Instructor / SME reachable by the learner | ❌ Gap |
| 1(o) | Well-organised courseware | ✅ Implemented |
| 1(p) | Logical flow | ⚠️ Partial |
| 1(q) | Usability | ✅ Implemented |
| 1(r) | Audio + visual content supported | ✅ Implemented |
| 1(s) | Formative + summative tests supported | ✅ Implemented |
| 1(t) | Configurable pass mark | ✅ Implemented |
| 1(u) | Max 2 rewrites then course-redo | ❌ Gap (needed if the enrichment course has a formal knowledge test) |
| 1(v) | Remediation to 100% once declared competent | ⚠️ Partial — incorrect answers surfaced, no active remediation loop |
| 1(x) | Identity and authentication built in | ⚠️ Partial |
| 1(y) | Info-protection mechanisms | ⚠️ Partial — many related specs planned |
| 1(z) | Retain all data ≥ 5 years | 📋 Planned — *not strictly required at Cat 2* (audit trail is enough), but will be needed in Phase 2 |

Clauses **not** required at Cat 2:
- 1(b) rigorous biometric identification during exam — Cat 4–5 only.
- 1(j) minimum tutorial-hours gate — only "where applicable" to regulated courses.
- 1(m) disturbance = fail — only meaningful at Cat 4–5.
- 2(*) virtual-training clauses — only if we are delivering live classes.

---

## What we can ship today

From the implementation audit, FLS already meets the Cat 2 minimum on these fronts:

- **Authentication** — unique email + password login with strong hashing, mandatory email verification, and brute-force lockout (`freedom_ls/accounts/models.py:62`, `config/settings_base.py:161-252`).
- **Courseware structure** — Course → CoursePart → Topics / Forms / Activities (`freedom_ls/content_engine/models.py:148-207`), with a working TOC and prev/next navigation.
- **Assessments** — `FormStrategy.QUIZ` and `CATEGORY_VALUE_SUM` cover summative and formative assessment, with configurable pass marks (`freedom_ls/content_engine/models.py:24-29, 263-267`).
- **Incorrect-answer surfacing** — `FormProgress.get_incorrect_quiz_answers()` (`freedom_ls/student_progress/models.py:448-500`) is already wired into the student view, which is most of the remediation (1v) work.
- **Audio + visual content** — `c-youtube`, `c-picture`, `c-pdf-embed`, `c-file-download` cotton components (`config/settings_base.py:231-236`).
- **Site-level data isolation** — via `SiteAwareModel` / `SiteAwareManager`.
- **Production security hardening** — HTTPS, HSTS, secure cookies, CSP, axes brute-force lockout (from the done `security-audit` spec).

---

## What we must build for Phase 1

Ranked by how much they block Cat 2 delivery. "Must" = cannot sign off Cat 2 without. "Should" = will be asked about in an internal audit but can be mitigated operationally.

### Must-build (Phase 1 blockers)

1. **Exam-record immutability — 1(c)**
   Today `FormProgress` and `QuestionAnswer` use CASCADE and can be deleted. Cat 2 requires an audit trail of results. Build an append-only audit log of exam submissions so that even if the underlying Form is removed, the record survives.
   *Source clause motivation:* Cat 2 matrix row — "Record keeping: Audit trail"; clause 1(c).

2. **Randomisation + auto-submit on timer expiry — 1(h) + Cat 2 assessment rule**
   The Cat 2 matrix *requires* randomised questions (from a master list) or randomised Q/A order. `00. exam-proctering` already plans this — land it.
   *Source clause motivation:* Cat 2 matrix — "random questions from master list or randomised question/answer order"; clause 1(h).

3. **2 min 30 s idle logout — 1(l)**
   Needs idle middleware + client-side heartbeat. This is mandated generically for learning-time, not only for exams, so it applies to enrichment training.

4. **Internal moderation workflow — 1(d)**
   Cat 2 explicitly calls for "internal" moderation. Minimum viable version: a moderator role, the ability to flag a question as defective, and a record of any mark override tied to the original attempt.

5. **Question revision tracking — 1(e)**
   When an educator edits a question, the old version must stop being drawn from the random pool but stay in the database for audit. This pairs naturally with (1) above and with the moderation work — once questions are moderatable, they need to be versionable.

### Should-build (Phase 1 polish)

6. **Course-revision register — 1(g)**
   An in-app changelog for courses (change, author, timestamp, approver). Cat 2 doesn't *demand* this, but "internally defined standards" without a change log is thin.

7. **Active remediation loop — 1(v)**
   Incorrect answers are surfaced but not forced-through. Cat 2 explicitly says "any incorrect answer immediately remediated." An active loop that walks the student through each wrong answer (and optionally requires them to re-answer correctly) closes this.

8. **SME contact channel — 1(n)**
   Promote the drafted `0. drafts/messages` spec to a concrete messaging feature. Cat 2 doesn't spell out chat, but 1(n) is a universal clause and an internal audit will ask how learners reach the SME.

9. **Declarative prerequisites — 1(k) / 1(p)**
   Replace positional gating with explicit "requires X, Y, Z" prerequisites. Small model extension; removes a class of course-authoring footguns.

### Operational / out of code

- **1(f) Backups** — already specified in the done security audit; evidence lives in the runbook.
- **1(w) Director approval** — organisational process.
- **1(y) Hosting in the Republic** — a deployment/contract decision; document allowed regions in the runbook.

---

## Suggested spec order for Phase 1

Implementation-dependency order (each builds on the previous where it can):

1. `session-timeout-strategy` — extended to specify 2m30s idle logout (1l).
2. `00. exam-proctering` — ship the core: randomisation, timer, auto-submit, attempt audit log (1h + parts of 1c).
3. **New spec:** immutable exam audit log (1c hardened).
4. **New spec:** question versioning (1e), leaning on the audit log from (3).
5. **New spec:** internal moderation workflow (1d), using the question versioning from (4).
6. **New spec:** active remediation loop (1v).
7. Promote `0. drafts/messages` to a concrete spec (1n).
8. **New spec:** course-revision register (1g).
9. Extend the content sequencing model for declarative prerequisites (1k, 1p).

Items 1–5 are genuine Cat 2 compliance blockers. Items 6–9 strengthen the audit posture without blocking launch.

---

## Exit criteria for Phase 1

Phase 1 is done when, for a representative enrichment course (e.g. CRM):

- A student logs in with unique credentials and is auto-logged-out after 2m30s idle.
- They work through the course with ordered content and a clearly navigable TOC.
- They take a knowledge test that randomises questions and auto-submits when the timer hits zero.
- Incorrect answers are walked through as a remediation loop after submission.
- Their result is written to an append-only audit log that cannot be CASCADE-deleted.
- A moderator can review the attempt, flag a defective question, and record an override — with the original result intact.
- Editing a question after-the-fact removes the old version from future random pools but keeps it visible for the auditor.
- An internal audit can produce, for any attempt, the version of the question the student saw, the time they took, and the identity of the moderator who reviewed it.
- The learner has a visible, in-app way to reach the SME (messaging feature).
