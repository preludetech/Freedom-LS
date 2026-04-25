# SACAA SA-CATS 141.07.1 — Risk Category 1 coordination

## Purpose

Shipping this idea (once it becomes a spec and the spec ships) must be
sufficient to claim SACAA Risk-Category-1 e-learning compliance under
SA-CATS 141.07.1(1) (a)–(z). Nothing more, nothing less.

Primary clause text was OCR'd from the SACAA-hosted PDF and is quoted
verbatim in `research_clause_interpretation.md`.

## Combine rule (how this idea relates to sibling specs)

- If a clause is **already covered by work in `3. done/` or `2. in progress/`**
  → reference that work; do not duplicate here.
- If a clause is **covered by a sibling idea still in `1. next/` or `0. drafts/`**
  → pull the Cat-1-necessary parts into this idea directly. Once this idea
  becomes a spec, the absorbed siblings are superseded and should be retired.
- If a sibling idea has **scope beyond Cat 1**, only the Cat-1-necessary
  subset comes across. The broader sibling may still ship on its own
  roadmap later, but this idea's scope is strictly Cat 1.
- If a clause has **no sibling**, the Cat-1-necessary work is specified
  here.

**IMPORTANT: do not scope-creep.** Every feature described here must be
traceable to a SA-CATS 141.07.1 clause.

## Clause status matrix

| Clause | Short gloss | Status | Pointer |
|---|---|---|---|
| 1(a) | ID + password (minimum auth) | **Done** | `accounts/` + allauth login. Cat 1 = self-declaration; MFA is out of scope here (sibling `MFA/` — for higher Cats only) |
| 1(f) | Backup or multi-server storage | **Ops concern** | `docs/deployment-security-checklist.md` backup section |
| 1(g) | Register of course revisions | **Done** | Content repo Git history + remote = register + backup |
| 1(i) | Adequate time to complete (except timed modules) | **Done** | Untimed is the default (`00. exam-timeouts/` is for optional timed modules, not Cat-1-required) |
| 1(l) | Interaction every 2 min 30 s or auto-logout | **Absorbed from `00. sacaa exit-on-idle/`; exam-scoped only** | §1(l) below |
| 1(m) | Exam disturbance/logout = fail | **Absorbed from `00. sacaa auto fail on logout or disturbance/`** | §1(m) below |
| 1(n) | Instructor/SME available to assist | **Included here** | §1(n) below |
| 1(o) | Organised courseware (menus, modules, instructions) | **Done** | Course/CoursePart/Topic structure in `content_engine` |
| 1(p) | Logical information flow | **Done** | Authoring responsibility; content_engine sequencing supports it |
| 1(q) | Usability as primary consideration | **Done/Ongoing, not a feature** | Existing mobile-responsiveness, accessibility, brand-guidelines work |
| 1(r) | Audio AND visual instructions | **Done** | Existing `youtube` cotton component delivers audio + visual together; satisfies the clause for Cat 1. Inline audio-only player tracked separately in `0. drafts/audio-player cotton component/` (not Cat-1 blocking) |
| 1(x) | Identity mgmt + auth built in | **Done** | `accounts/` app |
| 1(y) | Hosted in Republic + info protection | **Included here (narrow subset)** | §1(y) below. Broader info-protection ships via sibling `encryption-at-rest/`; hosting is a deployment-doc line |
| 1(z) | 5-year data retention | **Included here (narrow subset)** | §1(z) below. Broader privacy work ships via sibling `01. privacy-compliance/` |

Higher-Cat clauses (1(b), 1(c), 1(d), 1(e), 1(h), 1(j), 1(k), 1(s), 1(t),
1(u), 1(v), 1(w)) are out of scope.

## Work to do

### 1(g) Course revision register

**Clause:** "a register of course revisions and/or changes should be kept in
a safe manner preferably with an additional backup."

**Already covered.** Course content is in Git. Git is the register; remotes
are the backup. Nothing to build. If an auditor asks for a specific
presentation, address it then.

### 1(l) Exam idle auto-submit (absorbed from `00. sacaa exit-on-idle/`)

**Clause:** "the programme must regulate interaction during learning every
2 min and 30 seconds or logout the student automatically."

**Product decision — exam-scoped, not programme-wide:** a 150 s idle
logout applied everywhere would kick learners out while watching a
3-minute explainer video, reading a dense regulation excerpt, or working
a calculation on paper. The usability damage outweighs the compliance
upside, and clause 1(q) (usability as a primary consideration) pulls the
other way at this threshold. The literal "programme-wide during learning"
reading is preserved in `research_clause_interpretation.md` §1(l) so the
tradeoff stays visible to reviewers.

**Direction:**

- Configurable idle-timeout on exam-type forms. Default 150 s (2 min 30 s)
  per the clause. Configurable per deployment; all exam forms on a site
  share the same limit.
- Idle detection runs only while an exam attempt is in progress.
- Interaction signals are **user-initiated events only**: pointer input
  (click, tap, mousemove), keypress, scroll, form input, and HTMX
  requests that originate from a user event (e.g. `hx-trigger="click"`).
  Any one resets the timer.
- Programmatic / non-user HTMX traffic must NOT reset the timer —
  specifically polling (`hx-trigger="every Ns"`), `load`, `revealed`,
  `intersect`, and any server-initiated SSE/WS updates. Otherwise a
  polling widget on the exam page would defeat the idle detector.
- Learner is told on the pre-start screen that the exam auto-submits after
  N seconds of inactivity, so nobody is surprised.
- **Pre-exam re-auth.** Before an exam attempt actually starts, the
  learner re-enters their password (allauth re-authentication flow). This
  serves two purposes: (a) it confirms the person at the keyboard is
  still the account-holder at the moment of attempt start, and (b) it
  resets the session lifetime so a session that was about to expire
  doesn't kill the attempt mid-way. Combined with a session lifetime
  configured to comfortably exceed the longest exam duration, ordinary
  session expiry should never cause a disturbance-fail — only the
  learner's own actions (logout, idle, leaving the attempt) do.
- On expiry: a visible "You have been idle — your exam has been submitted"
  message, then auto-submit through the existing exam submission path.
- **Interlocks with §1(m) — configurable:** whether an idle auto-submit
  records a disturbance-fail per clause (m) is a per-deployment setting.
  Default ON for SACAA-serving sites (literal clause reading: idle =
  disturbance = fail). Operators running FLS outside SACAA contexts can
  disable it so an idle timeout just submits the attempt silently. The
  setting lives alongside the idle-timeout duration so both knobs are
  configured together.
- **Scoring is independent of the disturbance flag.** The auto-submitted
  attempt is marked using the normal scoring path regardless of whether
  the disturbance-fail interlock is on. The disturbance-fail (when
  recorded) is a separate, overridable flag on the attempt — see §1(m).
  This keeps the learner's actual performance visible to educators even
  when a clause-(m) fail is in force, and gives an authorised reviewer
  something concrete to evaluate when deciding whether to override.

### 1(m) Exam disturbance → auto-fail (absorbed from `00. sacaa auto fail on logout or disturbance/`)

**Clause:** "during exam/knowledge test, any disturbance/logout is regarded
as a fail."

**Direction:**

- During an in-progress exam attempt, any of the following terminate the
  attempt, submit it through the normal scoring path, **and** record a
  separate disturbance-fail flag against the attempt:
  - Explicit logout.
  - Auth loss caused by the learner or by something attributable to them
    (password change, forced logout from another device, account
    deactivation). A session that simply *expires* mid-exam due to its
    normal lifetime is **not** in this list — see "Pre-exam re-auth"
    below; the platform must remove that failure mode rather than punish
    learners for it.
  - Idle auto-submit (§1(l)), when the §1(l) interlock setting is enabled
    (default ON for SACAA sites).
  - Server-observed interruption when the learner's session state is
    lost between page loads.
- **Score and disturbance-fail are independent.** The attempt is always
  marked using the normal scoring path so the learner's actual
  performance is visible. The disturbance-fail is a separate flag on the
  attempt with the cause recorded (logout / auth loss / idle /
  interruption). For audit and reporting, an attempt that has the flag
  set is treated as a fail regardless of score; if the flag is cleared,
  the score stands on its own.
- **Override path.** A user with sufficient rights (e.g. exam
  administrator / authorised educator role — exact permission to be
  pinned in the spec) can clear or reinstate the disturbance-fail flag
  on a specific attempt, with a required reason. Every change to the
  flag is logged (who, when, previous value, reason) so the audit trail
  shows both that a clause-(m) fail was triggered and any subsequent
  override. The score itself is never edited via this path.
- The exam result page and any educator view must show both the score
  *and* the disturbance-fail state with cause, so it is obvious *why* an
  attempt is failing (disturbance vs. score vs. both) and whether an
  override has been applied.
- The student is warned at exam start that any disturbance is an automatic
  fail, so the rule is never a surprise.
- What constitutes a "disturbance" is bounded to things the server can
  reliably observe. Client-only events (tab switch, window blur) may be
  logged but are not in scope for the Cat-1 auto-fail — those live in the
  higher-Cat `02. exam-proctering/` work.

### 1(n) Instructor/SME contact surface

**Clause:** "an instructor or a subject matter expert shall be available to
assist the learner who is using the programme."

**Status for MVP:** Out of scope — do not build. Instructors and students
already communicate directly via email, text, and phone calls, and those
exchanges are logged outside the platform. The humans already know how to
talk to each other; no in-platform contact surface is required for Cat 1
sign-off. Revisit once the broader `messages/` work is on the table.

### 1(r) Audio AND visual instructions

**Clause:** "the programme should include audio and visual instructions."

**Already covered.** The existing `youtube` cotton component embeds video
that carries audio and visual together, which is what the clause asks for.
No new work is required for Cat-1 sign-off.

A separate, non-Cat-1-blocking inline audio-only player (for `File.file_type
== AUDIO` uploads, currently rendered as a download link) is tracked in
`0. drafts/audio-player cotton component/` and will ship on its own
roadmap.

### 1(y) Info-protection minimum + RSA hosting

**Clause:** "the system shall be hosted within the Republic and have
information protection mechanisms."

**Direction (Cat-1 minimum only):**

- **Hosting.** Add an explicit line to `docs/deployment-security-checklist.md`
  stating that production for SACAA-serving sites must be hosted within
  the Republic of South Africa. Operators deploying FLS outside RSA for
  non-SACAA use are unaffected.
- **Info-protection.** Enforce TLS for the DB connection
  (`OPTIONS: {'sslmode': 'require'}`). The security-audit (already in
  `3. done/`) covered in-transit TLS, password hashing, session security,
  and general hardening. Field-level encryption of sensitive model fields
  (API keys, webhook secrets, sensitive PII) is the Cat-1-adjacent part
  of the sibling `encryption-at-rest/`; include it here as a hard Cat-1
  dependency.

Nothing beyond these items is Cat-1-required. The broader
`01. privacy-compliance/` work (consent flows, data export, cookie banner,
etc.) is outside 141.07.1 and stays on its own roadmap.

### 1(z) 5-year data retention

**Clause:** "All information shall be kept for a minimum period of five (5)
years."

**Direction (Cat-1 minimum only):**

- A management command that enforces data retention, defaulting to a
  5-year minimum for SACAA-relevant records (student profile, enrolments,
  progress records, exam attempts, course revisions).
- Retention period configurable per model via settings so deployers can
  extend (but not reduce below 5 years for SACAA sites).
- "Keep" means records remain retrievable by staff and auditors — not
  that they remain visible to students after their learning relationship
  ends.

This overlaps with the retention piece of sibling `01. privacy-compliance/`.
Whichever ships first carries the Cat-1 requirement; the other becomes a
no-op.

## What is explicitly NOT in scope

- Higher-risk-category requirements (biometric auth, in-person proctor
  centres, invigilation). See sibling `02. exam-proctering/` and `MFA/`.
- Programme-wide idle detection (deliberate deviation — see §1(l)).
- Full messaging / chat — sibling `messages/` draft, independent roadmap.
- Retake policies, question randomisation, adaptive remediation — sibling
  `xx. sacaa question-pools-and-remediation/`.
- Broader privacy compliance (data export, consent flows, cookie banner)
  beyond the 5-year retention floor in §1(z) — sibling
  `01. privacy-compliance/`.
- Accessibility / WCAG 2.2 AA conformance programme beyond the incidental
  accessibility picked up via the §1(r) audio component.

## Siblings superseded by this idea (retire after spec)

- `00. sacaa exit-on-idle/` — absorbed into §1(l).
- `00. sacaa auto fail on logout or disturbance/` — absorbed into §1(m).

Siblings that remain independent but intersect with this idea:

- `encryption-at-rest/` — §1(y) depends on its sensitive-field encryption.
- `01. privacy-compliance/` — §1(z) depends on its retention command.

## Open questions to resolve before the spec phase

1. **1(m) fail semantics.** Is a disturbance-fail a separate attempt-state
   flag, or is the score forced to 0 with a reason note? Affects retake-
   policy behaviour (out-of-scope here but worth flagging).
2. **1(r) transcript requirement.** Mandatory transcript alongside every
   audio file, or optional with a warning at authoring time?
3. **1(y) encryption-at-rest dependency.** Is the sibling spec close enough
   to shipping that this idea can hard-depend on it, or do we need to
   inline the encryption scope here?
4. **1(z) retention dependency.** Same question for the retention command
   in `01. privacy-compliance/`.

## Research

- `research_clause_interpretation.md` — primary SA-CATS 141.07.1(1) text,
  OCR'd and quoted verbatim; per-clause interpretation and binding-strength
  summary.
- `research_gap_patterns.md` — how Moodle / Canvas / Articulate / aviation
  CBTs handle each gap; lightest-weight compliant patterns.

## Anti-goals

- No features beyond what 141.07.1 literally requires.
- No merging-in of sibling-spec scope creep.
- No compliance claim stronger than the clause text and research support.
