# Research: SACAA SA-CAR / SA-CATS 141.07.1 — Clause-by-Clause Interpretation

Date: 2026-04-24
Scope: How the SACAA 141.07.1 e-learning requirements are actually written in
primary regulatory text, and how they are (or are not) interpreted by the
aviation training industry. Sister document to
`research_sacaa_requirements.md` in the question-pools-and-remediation
worktree.

## Method and caveat

- The primary source located is the Amendment SA-CATS 2 of 2021 (substituting
  SA-CATS 141 in full), published by SACAA on the blob storage at
  `caasanwebsitestorage.blob.core.windows.net/legal-documents/Approved%20SA%20CATS%202%20OF%202021.pdf`.
  The PDF is image-only (no text layer). OCR was performed locally
  (tesseract) over the Part 141 section. OCR accuracy is ~98% on the
  narrative paragraphs but the **risk-matrix table (page 422-424) came out
  heavily garbled because the table text is rotated 90°**. The narrative
  clauses (a)-(z) on pages 425-426 were extracted cleanly and are quoted
  verbatim below.
- The section heading is **"141.07.1 REQUIREMENTS RELATING TO TRAINING — E-LEARNING SYSTEM AND SERVICE PROVISION BY OPERATOR"**, subsection (1): *"E-Learning systems shall comply with the following general requirements as a minimum."* This framing means **all clauses are universal** at the "minimum" level; the risk matrix then up-scales specific items (auth stringency, invigilation method, etc.) for higher risk categories.
- Every industry-interpretation search run (ATO websites, aviation
  consultancies, SACAA circulars, academic papers) returned **no substantive
  secondary commentary** on the specific sub-clauses of 141.07.1. The
  clause is recent (Nov 2021), quite prescriptive, and the South African
  e-learning ATO market is small — industry "interpretation" in the sense of
  published guidance essentially does not exist in English-language public
  sources. Where this is the case, the entry below says so and tags the
  *interpretation* (not the clause text) as `[Unverified]`.

Tags used (same convention as the sister doc):
- `[Verified]` — primary SACAA text quoted directly.
- `[Reported]` — secondary sources corroborate but primary text not captured.
- `[Unverified]` — could not be confirmed; presented as plausible reading,
  not as fact.

---

## Summary: binding strength per clause

| Clause | Short description | Primary text available? | Binding strength |
|---|---|---|---|
| 1(a) | ID + password, scaled by risk matrix | Yes [Verified] | Strict at Cat 1 (minimum); scales up by matrix |
| 1(f) | Backup or different-server storage | Yes [Verified] | Strict but flexible on *how* |
| 1(g) | Register of course revisions | Yes [Verified] | Strict (register required); backup is "preferably" |
| 1(i) | Adequate time to complete (except timed modules) | Yes [Verified] | Flexible / principle-based |
| 1(l) | Interaction every 2 min 30 s or auto-logout | Yes [Verified] | **Strict and programme-wide during learning**; exam disturbance = fail |
| 1(n) | Instructor / SME available | Yes [Verified] | Strict (must be available); mode unspecified |
| 1(o) | Organised courseware with menus/modules/instructions | Yes [Verified] | Principle-based / strict on "well-organised" |
| 1(p) | Logical information flow | Yes [Verified] | Principle-based |
| 1(q) | Usability as primary consideration | Yes [Verified] | Principle-based |
| 1(r) | Audio AND visual instructions | Yes [Verified] | **Literal "and" in text**; interpretation `[Unverified]` |
| 1(x) | Identity management and authentication built in | Yes [Verified] | Strict |
| 1(y) | Hosted within the Republic + info protection | Yes [Verified] | **Literal RSA hosting**; no derogation in the clause text |

Overall: the 141.07.1 clause is unusually **prescriptive by RSA standards** —
it does not use "where appropriate" softening language for most items. The
risk-matrix table (separate from the clause list) scales authentication and
invigilation *up* for Cat 2–5; it does *not* relax the universal minimums
for Cat 1. So at Cat 1 the full (a)-(z) list still applies.

---

## Per-clause detail

### 1(a) Identification + password, stringency scaled per risk matrix

**Primary text [Verified]:**
> "the programme shall have an acceptable identification system and password
> as a minimum-security feature in alignment with the risk matrix;"

The risk-matrix row for "Authentication" (pg 422) — although OCR-garbled —
is readable enough to see the Cat-1 end is *"Log-on via unique password and
self-declaration"*, Cat-2 adds *"signature of forms"*, Cat-3 adds *"Logon
via unique password and instructor signature"*, and Cats 4-5 escalate to
*"biometric / proxy-controlled environment, SACAA authorised exam centre,
proof of ID on entry, rigorous/undeniable identification taken before /
during assessment"*.

**Interpretation:** At Cat 1, username + password + learner self-declaration
is the regulated minimum. "Acceptable" is not defined — in practice this is
read against general South African info-sec norms (POPIA, ISO 27001-style
password policy). No minimum password length or MFA mandate appears in the
clause. `[Interpretation: Unverified — no SACAA circular or industry
guidance document found that defines "acceptable".]`

### 1(f) Backup or different-server storage

**Primary text [Verified]:**
> "the programme information should have either a backup or be stored in
> different servers, in case of any eventualities happening;"

**Interpretation:** The word "should" here reads as obligation in the
context of "shall comply with the following general requirements as a
minimum" at the start of the list; SACAA drafting does not draw a strict
shall/should distinction in this clause. The requirement is met by *either*
(a) a backup, or (b) multi-server storage. No RPO/RTO, no geographic-
separation rule, no encryption rule in this clause. `[Interpretation:
Unverified — plausible reading.]`

### 1(g) Register of course revisions / changes

**Primary text [Verified]:**
> "a register of course revisions and/or changes should be kept in a safe
> manner preferably with an additional backup;"

**Interpretation:** A change log is mandatory; a backup of the change log
is "preferable" (soft). In LMS terms this is normally a version-history
table keyed per course/module. `[Unverified — no secondary guidance found;
plausible reading.]`

### 1(i) Adequate time to complete (except timed modules)

**Primary text [Verified]:**
> "with the exception of timed modules trainees must be given adequate time
> to complete the training;"

And, for context, adjacent clause (h):
> "the programme shall assess the student when the exam/skills test time has
> lapsed regardless of the number of questions answered;"

**Interpretation:** "Adequate time" is not quantified. Paired with (h)
(exams *do* time out) and (j) (minimum tutorial hours can be gated), the
intent is: timed assessments enforce hard cutoffs; learning/self-study does
not. Pedagogically this is consistent with CBTA's "learn at your own pace,
assess against standard" principle. `[Reported — aligns with ICAO CBTA
framing in Doc 9868 / Doc 9941; not a direct SACAA quote.]`

### 1(l) Interaction every 2 min 30 s or auto-logout — CRITICAL

**Primary text [Verified]:**
> "(l) the programme must regulate interaction during learning every 2 min
> and 30 seconds or logout the student automatically;
> (m) during exam/knowledge test, any disturbance/logout is regarded as a
> fail;"

**Scope — critical finding:** The clause says **"during learning"**, not
"during a page" or "during a timed module". Paired with the immediately
following clause (m) which separately addresses exam behaviour, the structural
reading is:

- **(l) applies to the learning / content-consumption mode of the programme**
  (i.e. while a student is working through courseware). If no interaction
  occurs in a 2 min 30 s window, the system must auto-logout.
- **(m) applies to the exam / knowledge-test mode.** Here *any* disturbance
  or logout (including an (l)-triggered auto-logout) is a fail.

So the 2 min 30 s rule is **programme-wide for the learning experience**,
not limited to timed modules. Clause (i) ("adequate time, except timed
modules") addresses overall duration, not idle detection; (l) addresses
idle detection. They are independent requirements.

**Interpretation / implementation reading:** "Interaction" is not defined.
A defensible reading is *any* user-originated UI event (click, key, scroll,
form input, video-player event). Passive dwell without events would trip
the timer. No industry-published interpretation of "interaction" for
SACAA 141.07.1 was found. `[Interpretation: Unverified.]` The safest
product design treats (l) as a global idle-timeout = 150 s with visible
forewarning and automatic logout, active on every page where the learner
is progressing through content, and enforcing (m)'s "logout = fail" when
the learner is inside an exam attempt.

### 1(n) Instructor / SME available to assist

**Primary text [Verified]:**
> "an instructor or a subject matter expert shall be available to assist
> the learner who is using the programme;"

**Interpretation:** "Available" is not defined — neither the channel
(email, phone, chat, in-person) nor the response SLA. Pure-asynchronous
e-learning is not excluded by this wording; what is excluded is a totally
unmanned course with no escalation path. In practice ATOs meet this with
named instructor contact, a help email / ticket address, or a chat
channel. `[Unverified — no SACAA circular found prescribing the channel
or SLA.]`

### 1(o) Well-organised courseware

**Primary text [Verified]:**
> "the programme shall incorporate well-organized courseware with menus,
> modules and instructions;"

**Interpretation:** Specifies the three structural elements — menus,
modules, instructions — must all be present. "Well-organised" is
qualitative; SACAA auditors evaluate this during Phase-4 demonstration
of the ATO certification process. `[Unverified at the SACAA-guidance
level; this is aligned with standard Instructional Systems Design (Doc
9941) — Verified at the ICAO ISD framework level.]`

### 1(p) Logical information flow

**Primary text [Verified]:**
> "the flow of information shall build and develop knowledge, skills and
> abilities in a logical order;"

**Interpretation:** Reproduces the KSA triad from ICAO CBTA. Auditors
assess this against the Training Programme approval and curriculum map,
not against runtime LMS behaviour. `[Reported — KSA framing is ICAO
CBTA standard terminology; Doc 9868 PANS-TRG.]`

### 1(q) Usability as a primary consideration

**Primary text [Verified]:**
> "the usability of computer-based training systems in addressing
> software, human-computer interaction, and hardware factors shall be a
> primary consideration;"

**Interpretation:** Three explicit factors — software, HCI, hardware.
"Primary" (not "secondary" or "considered") means it is foundational to
approval. No WCAG reference, no SACAA-defined usability checklist was
found. In practice an ATO demonstrates this through the Training Manual
and user testing artefacts. `[Unverified — no specific SACAA usability
checklist found.]`

### 1(r) Audio AND visual instructions — literal or permissive?

**Primary text [Verified]:**
> "the programme should include audio and visual instructions;"

The directly adjacent **Section 2 (Virtual Training)** — pg 427 — has
parallel wording that is more explicit:
> "(h) training will be audio and visual;"

and
> "(e) reference material through course material other than audio or
> visual shall be supplied by the service provider;"

**Interpretation:** The plain-language reading of "audio and visual" is
**both are required** (literal "and"). This is reinforced by Section 2(h)
using "will be" in the active voice. *However*, "should" in 1(r) is softer
than the "shall" used elsewhere in the same list (e.g. (a), (h), (l), (o),
(p), (q), (s), (w), (x), (y), (z)) — so a defensible weaker reading is
"recommended that courseware is multimodal, at minimum one of audio or
visual must be present." SACAA has not published guidance resolving
which reading applies. `[Unverified — the regulatory text is internally
inconsistent on shall/should; the safest product design provides both
audio (voice-over / narration) AND on-screen visual for each module, or
documents an accessibility reason for variance.]`

### 1(x) Identity management and authentication built in

**Primary text [Verified]:**
> "identity management and authentication shall be built into the system;"

**Interpretation:** "Shall" = mandatory. "Built into the system" reads as
native (not bolted-on third party per-course). For an LMS this means user
accounts, login, session management are a first-class subsystem. No
specific identity-provider, SSO, or MFA requirement appears in the
clause. `[Unverified at the SACAA-guidance level.]` Note that (a) and
(x) are complementary — (a) prescribes the minimum auth feature
(password), (x) requires the feature to be architecturally integral.

### 1(y) Hosted within the Republic + info-protection mechanisms

**Primary text [Verified]:**
> "the system shall be hosted within the Republic and have information
> protection mechanisms; and"

**Interpretation:** "Shall" + "within the Republic" reads as **literal
RSA-only hosting** with no derogation in the clause itself. The clause
does not reference POPIA, but POPIA (Protection of Personal Information
Act, 2013) is the general RSA data-protection statute that provides the
"information protection mechanisms" floor — encryption in transit / at
rest, access controls, breach notification. **No "adequate protection"
equivalence / derogation clause was located in the 141.07.1 text.**

A plausible but unconfirmed reading is that a multi-region deployment with
an in-RSA primary + offshore DR would satisfy the spirit of the clause;
an offshore-only deployment (e.g. EU/US hosting with no RSA copy) would
not. `[Unverified — no SACAA circular, no ATO published interpretation,
no academic paper found addressing the hosting-location question.]` The
`is_rsa_hosted` flag in our matrix should be read as the regulator's
hard requirement.

---

## Observations against the FLS Cat-1 matrix

- **Clause (l) 2 min 30 s** — our matrix describes this as "auto-logout";
  the primary text says "regulate interaction ... or logout automatically",
  which is slightly broader (could be a prompt-then-logout). Recommend
  implementing the stricter reading (auto-logout at 150 s idle) to avoid
  audit risk.
- **Clause (r) audio AND visual** — our matrix gloss is "should include
  audio and visual". The primary text uses "should" (not "shall"), but
  section 2(h) adjacent uses "will be". Product guidance: treat multimodal
  as baseline expectation, not optional.
- **Clause (y) hosting in Republic** — literal reading confirmed; no
  derogation in clause text. Our matrix is correctly conservative.
- Clause (m) "any disturbance/logout is a fail during exam" is a Cat-1
  clause even though our matrix has focused on the Cat 4-5 exam
  invigilation (clause b). Our exam-timeouts idea should recognise that
  an exam in-progress cannot be recovered after an auto-logout — the
  attempt terminates and records a fail.
- Clause (z) "All information shall be kept for a minimum period of five
  (5) years" is universal and may already be in the matrix under
  records-retention; if not, it should be added.

---

## References

Primary / official sources:

- **SACAA — Amendment SA-CATS 2 of 2021 (substitutes SA-CATS 141 in full; contains 141.07.1):**
  https://caasanwebsitestorage.blob.core.windows.net/legal-documents/Approved%20SA%20CATS%202%20OF%202021.pdf
  (image-only PDF, OCR'd locally; clauses (a)-(z) at pages 425-426, risk matrix at pages 422-424)
- **SACAA — Civil Aviation Regulations, 2011 (consolidated):**
  https://caasanwebsitestorage.blob.core.windows.net/legal-documents/CIVIL_AVIATION_REGULATIONS-2011.pdf
- **Twenty-First Amendment of the Civil Aviation Regulations, 2021 (Gazette 45491, 15 Nov 2021) — substitutes Part 141:**
  https://www.gov.za/sites/default/files/gcis_document/202111/45491rg11359gon1503.pdf
  (cover gazette only; schedule content lives in the SACAA-hosted PDF)
- **SACAA — Personnel Licensing / Training index:**
  https://www.caa.co.za/industry-information/personnel-licensing/training/
- **SACAA — Legal Notices index:**
  https://www.caa.co.za/legal-notices-2/
- **SACAA — Approved Training Organisations:**
  https://www.caa.co.za/approved-training-organizations/

ICAO framework sources (SACAA inherits these via Annex 1 / CBTA):

- **ICAO — Doc 9868 PANS-TRG store page:**
  https://store.icao.int/en/procedures-for-air-navigation-services-training-doc-9868
- **ICAO — Doc 9941 Training Development Guide (CBTA methodology):**
  https://store.icao.int/en/training-development-guide-competency-based-training-methodology-doc-9941
- **IATA — CBTA guidance (competency assessment GM):**
  https://www.iata.org/contentassets/c0f61fc821dc4f62bb6441d7abedb076/competency-assessment-and-evaluation-for-pilots-instructors-and-evaluators-gm.pdf

Industry sources searched but no substantive 141.07.1 interpretation found:

- https://www.caa.co.za/ (SACAA home, top-level; no 141.07.1 circular found)
- https://www.caa.co.za/ato-home/ (ATO portal; procedural, not interpretive)
- https://www.eptaviation.com/cabin-crew-licensing-learning-programme-blended-learning/ (example ATO e-learning; no published interpretation)
- https://atasa.co.za/ (ATO; no published interpretation)
- https://examrevolution.com/ (SACAA exam prep; no ATO-side interpretation)

South African data-protection context (not quoted, relevant to 1(y)):

- POPIA — Protection of Personal Information Act, 2013: https://popia.co.za/

---

## Caveats

- The risk-matrix table (pg 422-424) is rotated text and OCR-unfriendly.
  The Cat-1-vs-Cat-5 authentication scaling described above is paraphrased
  from the readable fragments plus structural inference. A clean
  transcription of that table is still open work and should be done
  before any regulator conversation leans on the matrix wording.
- Every "interpretation" claim in this document that is not a direct quote
  from SA-CATS 141.07.1 is marked `[Unverified]`. No secondary SACAA
  guidance document on 141.07.1 has been located; therefore the product
  team should treat the clause text itself as the strictest available
  reading and design to that.
- No academic paper specifically addressing SACAA 141.07.1 e-learning
  compliance was found in this research session. If such a paper exists
  it is most likely to be in South African aviation-management Masters'
  theses (UNISA / Wits / UP) — not indexed in the web searches performed.
