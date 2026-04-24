# Phase 2 — Risk Category 4: Regulated Knowledge Exams

**Goal:** Deliver SACAA-regulated training with a knowledge test on FLS. Typical subjects: Dangerous Goods, Flight Test theory components.

**Depends on:** [Phase 1](./Phase1.md) — Cat 2 enrichment training. Everything in Phase 1 is a prerequisite for Phase 2.

**Reference:** see [implementation.md](./implementation.md).

---

## What Cat 4 adds on top of Cat 2

From the SACAA risk matrix:

| Dimension | Cat 4 rule (delta vs Cat 2) |
|---|---|
| Authentication | Logon via unique password **+ rigorous/undeniable identification (biometrics, proxy-controlled, or controlled exam environment) recorded before and during the exam + examiner signature** |
| Standards | As per regulations *(not "internally defined")* |
| Record keeping | **All data kept for 5 years** |
| Moderation | Internal moderation **+ SACAA auditing** |
| Assessment | Online knowledge test with random questions **and random answers** from a master list |
| Remediation | Any incorrect answer immediately remediated |
| Security | **Secure database of questions**, annual audit of access to that database |

The generic (a)–(z) clauses now bite harder. In particular, clause 1(b) (15 random photos / continuous video / invigilator / auto-fail on face change) becomes a hard requirement at this risk level.

---

## SACAA clauses that matter in Phase 2 (on top of Phase 1)

| Clause | Summary | Current status |
|---|---|---|
| 1(b) | Rigorous exam-time identification (photos / video / invigilator / face-match auto-fail) | 📋 Partial in `00. exam-proctering` — spec covers a single selfie only |
| 1(j) | Minimum tutorial-hours gate before the knowledge test | ❌ Gap |
| 1(m) | Any disturbance / logout during the exam = fail | 📋 Planned-partial in `00. exam-proctering` |
| 1(t) | Pass mark ≥ regulated minimum (SACAA reference 75%) | ⚠️ Partial — configurable but not enforced |
| 1(u) | Max 2 rewrites, then redo the course | ❌ Gap |
| 1(z) | Retain all data ≥ 5 years | 📋 Planned in `00. privacy-compliance` — needs aviation defaults |

Plus the Phase 1 "should-build" items become genuine **must-build** at Cat 4:

| Phase 1 item | Cat 4 reason it becomes blocking |
|---|---|
| Active remediation loop (1v) | The regulator now audits remediation, not just the operator |
| Course-revision register (1g) | Accredited content must be traceable to the approved version |
| SME contact channel (1n) | SACAA audit will check the learner support route |
| Declarative prerequisites (1k) | A positional bypass of the knowledge-test gate is an audit finding |

Clauses **still** not required at Cat 4:
- 2(*) virtual-training clauses — only if we deliver live classes.
- The physical-exam-centre controls — those are Cat 5.

---

## The two big shifts in Phase 2

### Shift 1: Exam integrity during the exam

Cat 2 cared about *what the student submitted*. Cat 4 cares about *who was at the keyboard when they submitted it and whether anyone else was helping*.

Clause 1(b) mandates **at least one** of:
- **15 random identifiable photos** taken during the exam
- **Continuous video** recording
- **Live invigilator** monitoring
- **Automated exit + fail** on face change / out-of-frame / extra person / voice detected

Random-photo capture is the cheapest mode to ship because it's browser-side with `getUserMedia()`; invigilator mode is heaviest because it needs a live dashboard and real people.

Clause 1(m) becomes teeth: a mid-exam disconnect or tab-switch is no longer "log and continue" — it is a fail, unless the operator has a configured grace-period policy.

### Shift 2: Records become regulatory, not operational

Cat 2's "audit trail" becomes Cat 4's "all data kept for 5 years." This means:

- Every exam attempt, including failures and abandoned sessions, must survive for five years.
- Question edits must keep history (already covered by 1e in Phase 1, but now the retention window is five years, not "forever is nice").
- Moderation decisions must survive for five years with moderator identity attached.
- Course versions shown to students must be recoverable five years later — which the Phase 1 course-revision register must now enforce as the source of truth for which version a student actually saw.

The CASCADE-delete problem noted in 1(c) becomes a real liability at this level — a single unreviewed migration could destroy regulated evidence.

---

## What we must build for Phase 2

Ranked by how much they block Cat 4 delivery.

### Must-build (Phase 2 blockers)

1. **Random-photo capture during Cat 4 exams — 1(b)**
   Extend `00. exam-proctering` to capture at least 15 random photos per attempt, stored with the submission record. Include consent handling at exam start, and a fallback to require a re-consent or a live invigilator if the camera is unavailable.
   *Cheapest compliant mode. Video and invigilator modes can come later if customers demand them.*

2. **Auto-fail on disturbance — 1(m)**
   Build on the tab/focus logging already in `00. exam-proctering`. For Cat 4 exams, make auto-fail the configured default: disconnection or tab-switch ends the attempt and records a failure, with an optional short grace window for network blips.

3. **Five-year retention defaults — 1(z)**
   Extend `00. privacy-compliance`'s retention system with SACAA-aviation defaults: exam attempts, question answers, moderation decisions, course versions, and student profiles pinned at ≥5 years. Make the `enforce_retention` job refuse to purge records inside the window even if a higher-priority privacy request asks.

4. **Enforced minimum pass mark — 1(t)**
   Add a "regulated" flag on the course / form that floors the pass percentage at the SACAA reference (75%). Admin validation refuses a lower value on a regulated course.

5. **Attempt counter + redo-the-course rule — 1(u)**
   Add an attempt counter on `FormProgress`. After the third failure on a regulated knowledge test, disable further attempts until course progress has been reset and the full course flow re-completed.

6. **Minimum-tutorial-hours gate — 1(j)**
   A two-part build: time-on-content tracking (leveraging the Phase 1 2m30s idle signal to distinguish genuine engagement from idle time), plus a gate on regulated-course knowledge tests that checks accumulated time against a per-course minimum before allowing the attempt.

7. **Tamper-proof question bank access — Cat 4 security row**
   The matrix requires a "secure database of questions, annual audit of access." Build on the immutable audit log from Phase 1 with an access log for the question bank itself — record who read / exported / edited the question bank, so annual audit has a real artefact.

8. **Examiner signature capture — Cat 4 authentication row**
   Each regulated attempt needs an examiner to sign off. Minimum viable version: a named examiner on the attempt, an examiner-authenticated sign-off action recorded immutably alongside the attempt, and a report surfacing unsigned attempts.

### Should-build (Phase 2 polish)

9. **Video-recording proctoring mode — 1(b) alternative**
   Continuous webcam recording, stored with the attempt. More evidence-heavy than random photos; useful for customers that want higher assurance.

10. **Live invigilator dashboard — 1(b) alternative**
    Real-time viewer showing photos/feeds for in-progress Cat 4 attempts, with flag/terminate actions. Heaviest mode; defer until customer pull-through justifies it.

### Promoted from Phase 1 "should" → Phase 2 "must"

Make sure these Phase 1 items are in place before claiming Cat 4:

- Active remediation loop (1v).
- Course-revision register (1g).
- SME contact channel (1n).
- Declarative prerequisites (1k / 1p).

---

## Suggested spec order for Phase 2

Builds on Phase 1's work:

1. Five-year retention defaults in `00. privacy-compliance` (1z).
2. Enforced minimum pass mark on regulated forms (1t) — small change, quick win.
3. Auto-fail on disturbance in `00. exam-proctering` (1m).
4. Attempt counter + redo-the-course rule (1u).
5. Random-photo proctoring in `00. exam-proctering` (1b).
6. Time-on-content tracking + minimum-tutorial-hours gate (1j).
7. Examiner-signature workflow (Cat 4 authentication).
8. Question-bank access log (Cat 4 security).
9. Video mode (1b alternative) — only if a customer needs it.
10. Invigilator dashboard (1b alternative) — only if a customer needs it.

Items 1–8 are compliance blockers. Items 9–10 are market-driven.

---

## Operational delta vs Phase 1

- **SACAA-approved standards** — the course content must be built to the regulated standard, not just to internal policy. That is a content and governance decision, not a system feature, but the course-revision register (1g) must be live so the approved version is traceable.
- **SACAA audit cooperation** — the operator must be able to produce, on demand, audit artefacts for any attempt from the last five years. The build list above assumes this and designs for it.
- **Annual question-bank access audit** — an operational commitment supported by the access log from (7).
- **Director / accountable-manager approval** (1w) — per risk matrix; organisational process.

---

## Exit criteria for Phase 2

Phase 2 is done when, for a representative Cat 4 course (e.g. Dangerous Goods):

- A registered learner cannot open the knowledge test until they have spent the required tutorial hours on the course modules.
- At the start of the test they consent to camera access; the test aborts or falls back to invigilator mode if they refuse or the camera is unavailable.
- During the test, at least 15 random photos are captured and stored with the attempt.
- A disconnection or tab-switch during the test records an automatic fail per the configured policy.
- The test uses randomised questions and randomised answer order drawn from the secure question bank.
- After submission the system walks the student through every incorrect answer as a mandatory remediation loop.
- The pass mark is fixed at the regulated minimum (75% for SACAA); the admin will not save a lower value.
- After a third failure, the learner cannot retry until a named educator resets their course progress; the reset itself is logged.
- An examiner reviews and signs off the attempt; the sign-off is recorded immutably against the attempt.
- The attempt record, the captured photos, the question versions seen, the moderator decisions, and the examiner signature are all retained for ≥5 years and cannot be removed by a CASCADE delete or a privacy-purge job inside the window.
- The question bank produces an access log that can be reviewed annually.
