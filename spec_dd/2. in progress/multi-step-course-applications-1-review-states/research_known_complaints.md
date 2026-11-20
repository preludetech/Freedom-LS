# Research: known complaints about application status tracking

Scope: what applicants and staff complain about with application status tracking, and which of those the
review-states spec (`CourseApplication.state`, withdraw, reject message, re-apply) can address.

Evidence caveat: sources are vendor guidance pages, forums, and self-selected surveys, not controlled studies.
Treat them as a catalogue of recurring complaints, not as prevalence data. Only two web searches were run, and
the pages were read as search summaries, not fetched in full.

## 1. Complaints found

### 1.1 Opaque or unknown status ("black box")
- Applicants often cannot tell where they stand. Greenhouse says the honest answer is frequently "we don't
  really know", and that this lack of communication raises dropout.
- Portals may hide stages or show blank or "Hidden" statuses (iCIMS), which applicants read as a fault on their side.
- Monster's report: uncertainty weighs on candidates more than rejection itself.
- Sources:
  - https://greenhouse.com/guidance/exploring-the-truth-about-candidate-portals
  - https://hiring.monster.com/resources/blog/application-black-box/
  - https://www.monster.com/career-advice/research/application-black-box-report
  - https://www.refer.me/blog/icims-hidden-status-codes-and-blank-updates-explained-calmly
  - https://www.refer.me/blog/candidate-portal-status-missing-fixes-for-greenhouse-workday-more
  - https://www.hrdive.com/news/job-seekers-frustrated-by-opaque-impersonal-hiring-process/819898/

### 1.2 Rejection with no reason, or boilerplate reason
- The reason is usually missing or generic ("We have decided to move forward with other candidates").
- Silence in place of any rejection is a common complaint.
- Sources:
  - https://www.journeyfront.com/blog/what-candidates-want-to-know-when-rejected-bpo-hiring
  - https://www.teamblind.com/post/salesforce-job-portal-application-rejected-always-kuihjk5x
  - https://community.blackbaud.com/discussion/72480/declined-applications (staff-side question: what an applicant sees once declined)

### 1.3 Status that flips or looks stale
- Applicants report statuses that revert (e.g. Amazon status reverting) and portals that lag behind what staff
  did.
- Source: https://www.teamblind.com/post/amazon-application-status-reverting-bgj7ykcf

### 1.4 Accidental withdrawal, and withdrawal being irreversible
- Applicants withdraw by mistake, then ask to undo it. Outcomes vary: some schools have a manual reinstatement
  request; others refuse (AMCAS said no); UCAS says a full withdrawal means no re-apply in the same cycle.
- Some portals cannot process withdrawal at all and need staff contact, so the applicant has no self-service path.
- Sources:
  - https://www.ucas.com/faqs/what-happens-if-i-withdraw-choice-then-change-my-mind-later
  - https://forums.studentdoctor.net/threads/i-withdrew-my-amcas-application-i-want-to-unwithdraw-or-renew-amcas-representative-said-no.1413299
  - https://help.powerschool.com/t5/Unified-Talent-Forum-for/Accidentally-Withdrawn-want-to-Reapply-to-the-same-position/m-p/509345
  - https://services.txst.edu/TDClient/67/Admissions/Requests/Service/937/Graduate-Application-Withdraw-or-Reinstatement-Requests
  - https://www.applytoeducation.com/applicant-tips-and-tutorials-topics/unable-to-reapply-after-withdrawing-your-application
  - https://resources.ripplematch.com/can-i-re-apply-to-a-match-i-withdrew-from
  - https://portalhelp.uceap.universityofcalifornia.edu/portal/en/kb/articles/withdrawing-your-application-or-program

### 1.5 Unable to re-apply, or re-apply loses data
- "Can't re-apply" after withdraw is a recurring forum question (above). Where the system keeps one record per
  person and position, the closed record blocks a new one.
- Re-applying commonly means starting from a blank form. (Inferred from the re-apply threads; no source gave
  hard evidence either way about carried-over answers, so treat this as a risk to check, not a finding.)

### 1.6 Confusing wording for closed states
- "Withdrawn" is ambiguous: applicants ask whether the school or they withdrew it, and whether they can appeal
  or re-apply.
- Sources:
  - https://www.collegevine.com/faq/14108/application-withdrawn
  - https://collegevine.com/faq/16338/what-does-your-application-has-been-withdrawn-mean
  - https://www.collegevine.com/questions/22994/hey-what-does-it-mean-if-an-application-has-been-withdrawn-can-i-appeal-the-decision-or-re-apply

### 1.7 Staff-side complaints
- Staff ask what the applicant sees after a decline and whether a decline is visible or reversible (Blackbaud
  thread above). Internal-only statuses confuse applicants when exposed (1.1).
- Low-signal here: only one staff-side thread was found.

## 2. What this spec can address

| Complaint | Addressed? | How |
|---|---|---|
| 1.1 Opaque status | Yes | Plain-words status page per state; `draft`/`submitted` split replaces the derived "submitted"; no hidden internal state (no `under_review`). |
| 1.2 Rejection with no reason | Yes | Reject requires a non-empty message (answers.md); shown on status page and on the dashboard panel. Boilerplate risk remains: the service only forbids empty, not generic text. Screen wording is spec 2. |
| 1.3 Stale or flipping status | Mostly | State is the one source of truth; every change moves `updated_at`; dashboard keeps closed applications visible. Terminal states cannot flip back (no reopen until spec 4). |
| 1.4 Accidental withdrawal | Partly | Confirm dialog before the POST (answers.md); withdraw only from draft/submitted. Undo is not offered, but re-apply is (below), which covers the common recovery. |
| 1.5 Cannot re-apply | Yes | Partial unique index over active states; new application after reject/withdraw; CTA "apply again". |
| 1.5 Data lost on re-apply | No (open) | Spec says re-apply makes a new application; nothing carries answers forward. Decide in the spec whether this is accepted and note it as a known gap, or add prefill (probably a new feature, outside "don't build what isn't requested"). |
| 1.6 Ambiguous closed wording | Yes | Wording is an open item: make withdrawn read as "You withdrew this application" and distinguish it from rejected; state whether re-apply is allowed on each closed state. |
| 1.7 Staff view | Out of scope | Reviewer screens are spec 2; the admin stays read-only. Audit entries on approve/reject help later. |

## 3. Suggestions for the spec
1. Write per-state status copy that says who acted (you / the reviewer) and what happens next, including whether
   "apply again" is available.
2. Make the confirm dialog text say the application will be closed and can be replaced by a new one.
3. Record a decision on carried-over answers on re-apply (accept the blank start, or defer).
4. Consider that a rejected applicant seeing "apply again" immediately may be a surprise; word the CTA carefully.
5. The reject message is free text; the spec can note that quality of the reason depends on the reviewer screen
   (spec 2), not this one.

status: ok
