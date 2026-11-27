# Research: best practices for question bank confidentiality and access logging

Scope: brief, aimed at the idea's decisions (new permission and role, one audit entry per view, PDF export, report cache). Findings come from web searches (standard mode); search snippets were the main evidence, so primary documents were not read in full. Gaps are marked.

## 1. Least-privilege roles for item-bank access

- Vendor guidance on item banks (Janison, ExamStudio) is consistent: strict role-based access, so people see only the items their role needs; access updated or revoked when staff change role or leave; export formats restrictable by role; version control with rollback for review.
  - https://www.janison.com/resources/post/does-your-item-bank-have-these-10-critical-safeguards/
  - https://examstudio.com/5-critical-security-questions-you-should-ask-your-item-banking-platform-provider/
- Regulators treat the bank as need-to-know. EASA: everyone involved in the ECQB process must keep it confidential, and reporting of suspected violations is provided for. The UK CAA says only a limited number of its staff can access the ECQB, under a confidentiality agreement. Germany's LBA allows inspection of questions only within an official objection proceeding.
  - https://www.easa.europa.eu/en/faq/19190
  - https://www.easa.europa.eu/domains/aircrew-and-medical/european-central-question-bank-ecqb
  - https://www.lba.de/EN/AviationPersonnel/TheoExamination/FCL_examinations/Information_ECQB.html
  - https://www.caa.co.uk/media/0syndlmr/f0001769replyletter.pdf
- Fit with the idea: a dedicated organisation role that no existing role holds by default, named for what it grants (`question_bank_viewer`), matches the need-to-know pattern. Granting it to other roles is an explicit site decision. Revocation must take effect on every path (preview, report, stored PDF), which is why section 4 matters.
- Layered defence (no single control sufficient) is the stated posture of exam vendors (Elsevier HESI, Prometric). Closing the admin back door alongside the educator surfaces is the same idea.
  - https://prometric.com/Test-Owners/Resources/Blog/Prevent-Exam-Content-Exposure

## 2. Access logging: what to record, when, volume

- OWASP Logging Cheat Sheet: log access to sensitive data, privileged and administrative actions; do not log too much or too little, guided by purpose. Record identifiers and metadata, not the sensitive content itself (ASVS, CWE-532).
  - https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
  - https://owasp.org/Top10/2025/A09_2025-Security_Logging_Alerting_Failures/
- NIST SP 800-92 (2006, revision 1 still draft) gives the baseline fields: timestamp, event/status, source application; add actor, target and outcome. No prescribed read-audit volume or dedupe rule found; it is a purpose-driven judgement.
  - https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-92.pdf
  - https://csrc.nist.gov/pubs/sp/800/92/r1/ipd
- Applied to the idea:
  - Write the entry in the same request that renders the content (so no render without a record), only on the request that actually renders it. Matches the idea's rule.
  - Record: actor, time, organisation, target (course), surface, form, page, ids and labels. Never question text or answers. Matches the idea's recommended `details`.
  - Volume: viewing the question bank is rare and high-value, so one entry per view with no dedupe is affordable and gives the cleanest trail. Dedupe and throttling are the usual relief valve if it grows, and reducing rows for pagination (log the open, not each page-through) is the common compromise; the idea logs each rendering request but not a continuing paging request.
  - Log superuser access too (privileged access is explicitly in OWASP's list).
  - Log denied attempts is common practice (security events), but the idea does not ask for it; flag as a possible follow-up, not a requirement.
  - Log retention and tamper resistance (append-only, no admin edit) matter for audit credibility; check the audit log already provides this.

## 3. Aviation and regulated-exam expectations

- EASA ECQB: confidential, copyright-protected, intellectual property of EASA and Member States, not published; violations investigated and enforcement possible. Questions are not released, even to candidates, other than via formal objection process.
  - https://www.easa.europa.eu/en/faq/19190
  - https://www.iaa.ie/personnel-licensing/pilot-licences-(eu-regulations)/examination-dates---multiple-choice-questions-(mcq)/information-on-the-european-central-question-bank
- FAA: does not publish all test questions; continuous revision partly protects integrity and security. Test security procedures sit in FAA Order 8080.6 (Conduct of Airman Knowledge Tests; check the current revision, 8080.6H appeared in results). Not read in detail.
  - https://www.faa.gov/training_testing/testing/Frequently_Asked_Questions.pdf
  - https://www.faa.gov/documentLibrary/media/Order/FAA_Order_8080.6H.pdf
- SACAA: found only that approved test centres must ensure the security and integrity of examinations under an SLA/NDA, and that SACAA uses Questionmark Perception. No published rule on question bank confidentiality or access logging was found. The audit expectation in the idea therefore rests on general authority audit practice, not a citable SACAA clause.
  - https://caasanwebsitestorage.blob.core.windows.net/examination-information/TGM%20for%20Examinations%20at%20Test%20Centres%20061217.pdf
  - https://www.caa.co.za/industry-information/personnel-licensing/examinations/
- ICAO: nothing found on question bank access logging (Doc 9379 not located). Treat as a gap; do not cite ICAO in the spec without further reading.
- Common thread across authorities: confidentiality agreements plus named, limited access; no formal published requirement for read-audit logs was found, but a traceable trail is the natural evidence of limited access.

## 4. Stored exports that outlive permission changes

- Vendor guidance flags that content leaving the platform is harder to monitor or revoke, hence export restrictable by role (Janison / ExamStudio links above). No standard prescribes handling for stored files; the principle is that access to a file is checked at download time against current permissions, not only at creation.
- Applied to the idea (consistent with its answers):
  - Decide at generation time whether the PDF carries the detail, by the generator's permission, and record that on the file.
  - Check the current permission on each download of a detail-carrying file, and write an audit entry per download. This keeps a later revocation effective for existing files. The generation itself is also a disclosure to the generator; decide whether it needs its own entry.
  - Legacy files with no record are treated as carrying the detail (fail closed), per the answers.
  - Residual risk: once downloaded, the file is outside control; a holder can still share it. The log shows who downloaded it, which is the control available.
- Cache: the same principle applies. Key the cached report by whether it includes the detail (or cache only the non-detail parts) so a holder's rendering is never served to a non-holder; fail closed on a key miss.

## Takeaways for the spec

1. Dedicated, non-default organisation role plus a single permission check on every path is standard least-privilege practice.
2. One entry per rendering request with identifiers only (no question or answer text) matches OWASP; no dedupe is acceptable at expected volume.
3. Check permission at download time for stored PDFs, and audit each download.
4. No SACAA or ICAO clause on question bank access logging was found; do not claim one. EASA ECQB confidentiality and the FAA non-publication policy are the citable analogues.

status: ok
