# Phase 3 — Risk Category 5: Final Exams (Initial Licences / Ratings)

**Goal:** Deliver initial-licence and rating knowledge exams on FLS, in partnership with a SACAA-authorised exam centre. Typical subjects: Flight Test final theory for initial licences.

**Depends on:** [Phase 1](./Phase1.md) and [Phase 2](./Phase2.md). Everything in those phases is a prerequisite.

**Reference:** see [implementation.md](./implementation.md).

---

## What Cat 5 adds on top of Cat 4

From the SACAA risk matrix:

| Dimension | Cat 5 rule (delta vs Cat 4) |
|---|---|
| Authentication | **SACAA-authorised exam centre**, proof of ID on entry |
| Standards | As per regulations |
| Record keeping | All data kept for 5 years |
| Moderation | Internal moderation + SACAA auditing |
| Assessment | **As per regulations** |
| Remediation | **As per regulations** |
| Security | **As per standard operating procedures** |

The shift at Cat 5 is different from the shift from Cat 2 → Cat 4. Cat 5 is mostly **operational** — a physical exam centre, human invigilators, and a Standard Operating Procedure signed off by SACAA. The system's job is to support that operational envelope without compromising the Phase 1 / Phase 2 controls that already exist.

---

## Reframe: Cat 5 is a delivery mode, not a new control set

At Cat 4, the LMS is the integrity envelope — its proctoring, records, and question-bank security carry the compliance weight. At Cat 5, the **physical exam centre** is the integrity envelope, and the LMS becomes the system the centre uses to deliver the exam securely.

Practically that means four things:

1. The exam is taken on a terminal inside a SACAA-authorised centre, not on the candidate's personal device.
2. A human invigilator has already verified the candidate's ID at the door.
3. The integrity controls from Cat 4 (photos, auto-fail-on-disconnect, etc.) may be relaxed or replaced by physical controls — per the operator's SOP — but the **records** controls (immutability, retention, versioning, moderation) stay at full strength.
4. Certificates issued at Cat 5 tend to feed directly into licence issuance, so verifiable certificates (§2 clause 2(o)) become a real business-critical deliverable even though 2(o) is technically a §2 clause.

---

## SACAA clauses that matter in Phase 3

| Clause | Summary | Current status | Notes |
|---|---|---|---|
| 1(a) / 1(x) | Password login + ID management | ✅ / ⚠️ | Candidate still logs in, but the primary identity gate is the physical centre |
| 1(b) | Exam-time rigorous identification | 📋 | Can be satisfied by the physical invigilator; system controls become supplementary |
| 1(c) | Exam records immutable | Phase 1 blocker | Unchanged — still required |
| 1(d) / 1(e) | Moderation + question versioning | Phase 1 blockers | Unchanged |
| 1(m) | Disturbance = fail | Phase 2 blocker | May be softened if SOP says the invigilator handles disturbances |
| 1(t) | Pass mark at regulated minimum | Phase 2 blocker | Unchanged |
| 1(u) | Max 2 rewrites + course redo | Phase 2 blocker | Unchanged |
| 1(v) | Remediation to 100% if competent | Phase 1/2 work | "As per regulations" — must match the specific rating's rules |
| 1(z) | 5-year retention | Phase 2 blocker | Unchanged |
| 2(o) | PDF certificate with numbering + public verification | ❌ | **Cat 5 promotes this to must-build.** The certificate is often the evidence fed into licence issuance. |

New, Cat-5-specific needs (not a single clause, but derivable from the matrix):

- **Exam-centre / kiosk mode.** The LMS must be launchable in a locked-down mode on centre terminals: no side-navigation to other courses, no tab-switch to personal email, exam only.
- **Centre staff as a distinct role.** Invigilators and exam-centre administrators need their own RBAC role, separate from educators — they unlock the exam for a candidate, observe, and sign off. They do not edit questions or view other candidates' results.
- **ID capture at centre entry.** Even though the physical invigilator has verified ID, the system should record that verification — the invigilator attests in the system that candidate X's ID matched their registration.
- **SOP-backed configuration.** Each Cat 5 exam is delivered under a SOP. The system's per-exam proctoring / disturbance / remediation settings must be bound to a named SOP and versioned so that changes to the SOP are tracked.

---

## What we must build for Phase 3

### Must-build (Phase 3 blockers)

1. **PDF certificate with verifiable numbering — 2(o)**
   A `Certificate` model with collision-resistant random numbers, PDF generation with training-organisation branding, optional digital signature, and a public `/verify/<certificate-number>` endpoint that confirms authenticity and shows the holder, course, date, and examiner. Employers and licensing authorities will actually use this endpoint.

2. **Exam-centre kiosk mode**
   A locked-down delivery path (separate URL / deployment profile / or per-session flag) that hides non-exam navigation, prevents the candidate opening other courses, and sends the candidate back to a neutral "attempt complete" page on submission. Optionally integrates with a kiosk browser if the centre chooses.

3. **Invigilator role + candidate unlock flow**
   RBAC role for centre staff. Flow: candidate arrives, invigilator authenticates, confirms the candidate's ID against the registered profile, unlocks the exam session, observes, and signs off. Every unlock and every sign-off recorded immutably against the attempt.

4. **SOP binding per regulated exam**
   Each Cat 5 exam record must carry the identifier and version of the SOP under which it was delivered. A change to the SOP is a version bump. The moderation and retention records inherit the SOP version.

### Should-build (Phase 3 polish)

5. **Centre administration UI**
   Exam-centre admins manage their invigilators, their terminals, their scheduled exams. Not blocking — can be done via the Django admin initially — but becomes painful above a few centres.

6. **Licence-authority export**
   For common Cat 5 ratings, an export bundle (PDF certificate + attempt record + examiner signature + SOP version) formatted for submission to the licensing authority. Saves clerical work for the training organisation.

### Promoted from Phase 2 → Phase 3 "must"

Already compliance blockers from Phase 2, but Cat 5 raises the stakes:

- Immutable exam records (1c) — a failed Cat 5 challenge can end a candidate's licence pathway; the records must hold up in dispute.
- Question versioning (1e) — the exact version each candidate saw must be reproducible years later.
- Five-year retention (1z) — licence authorities may request records late.

---

## What Cat 5 does **not** require us to build

Cat 5 is deliberately lighter on platform-side proctoring controls because the physical centre takes that load. Specifically:

- **1(b) in-browser proctoring** can be relaxed by SOP — the invigilator is in the room. We do not need continuous video if the SOP names live observation.
- **1(m) auto-fail on disturbance** can be relaxed by SOP — the invigilator decides.
- **2(a)–(p) virtual-training clauses** remain out of scope unless we are also delivering live virtual training.

These relaxations are **SOP-mediated**, which is why item (4) above — SOP binding per exam — matters: the relaxations must be traceable to an approved SOP, not a per-exam config someone forgot to lock down.

---

## Suggested spec order for Phase 3

1. **New spec:** `Certificate` model + PDF generation + verification endpoint (2o).
2. **Extension:** RBAC — invigilator and exam-centre-admin roles.
3. **New spec:** candidate unlock flow at the centre (ID attestation, examiner sign-off).
4. **New spec:** kiosk / exam-centre delivery mode.
5. **New spec:** SOP binding — version the per-exam integrity configuration and attach the SOP version to each attempt.
6. **Extension:** licence-authority export bundle (if a specific rating calls for it).

---

## Operational delta vs Phase 2

- **SACAA-authorised exam centre** — physical premises, centre certification, and physical invigilators are the training organisation's responsibility.
- **Proof of ID on entry** — an operational step handled by the invigilator; the system records only the attestation.
- **SOP per Cat 5 exam** — the training organisation writes and maintains an SOP with SACAA approval. The system merely tracks which SOP version was in force for any given attempt.
- **Physical security of centre terminals** — infrastructure concern; document in the centre runbook.

---

## Exit criteria for Phase 3

Phase 3 is done when, for a representative Cat 5 final exam (e.g. a PPL theory final delivered at an authorised centre):

- The candidate arrives at an authorised centre; the invigilator authenticates, locates the candidate's registration, attests their ID, and unlocks the exam session on a centre terminal.
- The terminal runs FLS in kiosk mode: only the exam is reachable; there is no way to navigate to other courses, personal accounts, or the wider web.
- The exam is delivered under the integrity settings pinned to an approved, versioned SOP. The SOP version is stamped onto the attempt record.
- On submission, the invigilator reviews and signs off the attempt; the sign-off is recorded immutably.
- Where the candidate is declared competent, a PDF certificate is generated with a random verifiable number, downloadable to the candidate and attached to the attempt record.
- A third party (employer, licensing authority) can query the public verification endpoint with the certificate number and confirm its authenticity.
- All records — attempt, answers, examiner signature, invigilator attestation, SOP version, certificate number — persist for ≥5 years under the retention policy from Phase 2.
- The licensing-authority export bundle for the rating can be produced on demand from the attempt record.
