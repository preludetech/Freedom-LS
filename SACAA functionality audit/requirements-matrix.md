# SACAA 141.07.1 — Requirements Matrix

One row per requirement. Source: [`sacaa-requirements.md`](./sacaa-requirements.md).

**Minimum risk category** = lowest Cat (1–5) at which the rule applies.
- `N/A` = Section 2 (virtual training) — the Cat 1–5 matrix in the source doc is scoped to e-learning, not virtual training.
- `TBD — <rationale>` = minimum category genuinely ambiguous; flagged for human adjudication.

## Section 1 — E-Learning systems (1(a)–1(z))

| ID | Requirement (plain-language gloss) | Min risk cat | Notes |
|---|---|---|---|
| 1(a) | Identification + password as a minimum security feature, with stringency scaled per the risk matrix. | 1 | Rule says "as a minimum" and "in alignment with the risk matrix" → applies universally; higher Cats require stronger auth. |
| 1(b) | During Cat 4–5 knowledge tests: 15 random identifiable photos, OR continuous video, OR invigilator monitoring, OR automatic exit/fail on face change, candidate leaving view, additional person in view, or audible voices. | 4 | Explicit in rule text. |
| 1(c) | Exam records must be maintained and cannot be deleted or manipulated. | 2 | Matrix: record-keeping (audit trail) starts at Cat 2. |
| 1(d) | Where applicable, demonstrate acceptable moderation. If a moderator awards marks for a defective question, keep that record with the results — but system marks must not be manipulated. | 2 | Matrix: internal moderation starts at Cat 2. Rule is conditional ("where applicable"). |
| 1(e) | When a question is revised, block it from the random pool but keep it in the system for audit. | 2 | Applies wherever a randomised question pool exists (matrix: Cat 2+). |
| 1(f) | Programme information must have a backup or be stored on different servers. | 1 | Universal — no Cat restriction in text. |
| 1(g) | Keep a register of course revisions/changes safely, preferably with an additional backup. | 1 | Universal. |
| 1(h) | When exam/skills-test time lapses, the programme must assess the student regardless of how many questions were answered. | 2 | Applies wherever timed exams exist (matrix: assessment starts at Cat 2). |
| 1(i) | Trainees must be given adequate time to complete training (except for timed modules). | 1 | Universal. |
| 1(j) | Where a minimum tutorial time applies, the programme must not let the student write the knowledge test until those hours are met and modules are complete. | 2 | Conditional on minimum-tutorial-time existing. |
| 1(k) | The programme must not allow fast-forwarding to the knowledge test; self-assessments must be completed first. | 2 | Applies wherever a knowledge test / self-assessment exists. |
| 1(l) | The programme must require learner interaction every 2 min 30 s, or auto-logout the student. | 1 | Universal. |
| 1(m) | During an exam/knowledge test, any disturbance or logout is a fail. | 2 | Applies wherever formal exams exist. |
| 1(n) | An instructor or subject-matter expert must be available to assist the learner. | 1 | Universal. |
| 1(o) | Well-organised courseware with menus, modules, and instructions. | 1 | Universal. |
| 1(p) | Information flow must build knowledge, skills, and abilities in a logical order. | 1 | Universal. |
| 1(q) | Usability (software, human-computer interaction, hardware) must be a primary consideration. | 1 | Universal. |
| 1(r) | The programme should include audio and visual instructions. | 1 | Universal. |
| 1(s) | Where applicable, the e-learning system must administer formative and/or summative tests to judge learner achievement. | 2 | Conditional ("where applicable"); applies wherever tests are used. |
| 1(t) | Pass mark for knowledge tests and exams must be no less than the regulated/prescribed pass mark. | 2 | Applies wherever pass marks apply (matrix: assessment starts at Cat 2). |
| 1(u) | A learner is allowed a maximum of two re-writes; thereafter they must redo the course for readmission to the exam. | 2 | Applies wherever formal exams exist. |
| 1(v) | Candidate receives their results after completing the exam; where declared competent, the system must remediate to 100%. | 2 | Applies wherever exams + remediation apply. |
| 1(w) | The training programme and system must be approved by the Director, as per the risk matrix. | TBD — approval requirement is "as per the risk matrix", deliberately category-dependent. Plausibly Cat 1 (SACAA can approve at any level) but Cat 3+ is where formal regulated approval kicks in. | Rule explicitly defers to the risk matrix. |
| 1(x) | Identity management and authentication must be built into the system. | 1 | Universal — even Cat 1 (self-declaration) is a form of identity claim. |
| 1(y) | The system must be hosted within the Republic (of South Africa) and have information-protection mechanisms. | 1 | Universal. |
| 1(z) | All information must be kept for a minimum of 5 years. | TBD — rule text says "all information" universally (→ Cat 1), but the matrix restricts 5-year retention to Cat 3+. Rule text vs matrix disagree. | Flag for user adjudication. |

## Section 2 — Virtual training systems (2(a)–2(p))

Risk category is `N/A` for all Section 2 rows — the Cat 1–5 matrix in the source doc is scoped to Section 1 (e-learning).

| ID | Requirement (plain-language gloss) | Min risk cat |
|---|---|---|
| 2(a) | Online-classroom-capable learning management platform. | N/A |
| 2(b) | Stable and suitable candidate-facing interface. | N/A |
| 2(c) | Full control of user data; confidential management of candidate details, interactions, and results. | N/A |
| 2(d) | Digital candidate training file that cannot be manipulated by any third party viewing results of knowledge/progress assessments. Webinar recordings kept 2 years for audit. | N/A |
| 2(e) | Reference material (beyond audio/visual) supplied by the service provider. | N/A |
| 2(f) | Well-established matrix of tutorials mapped to pre-set accomplishment levels toward the total required exposure. | N/A |
| 2(g) | Database of knowledge-progress questions and tasks as applicable. | N/A |
| 2(h) | Training delivered with both audio and visual. | N/A |
| 2(i) | Tasks handled through the chat function of the virtual training system and assessed by an SME. | N/A |
| 2(j) | Adhere to digital-verification validity processes and lock others from joining — must be a closed system. | N/A |
| 2(k) | Random manual audits every month to assess system security. | N/A |
| 2(l) | All information under the operator's full control and protected. | N/A |
| 2(m) | Provide a suitably qualified subject-matter expert, assessor, and moderator. | N/A |
| 2(n) | Proof of moderation must be available. | N/A |
| 2(o) | Digital, randomly numbered PDF certificate provided to the candidate, referenced and verifiable via a system quick-search function. | N/A |
| 2(p) | Accredited courses must strictly follow the approved content and flow. | N/A |
