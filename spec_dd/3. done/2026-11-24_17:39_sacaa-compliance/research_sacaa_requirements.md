# Research: SACAA requirements bearing on randomised assessments

Date: 2026-11-17. Scope: what SACAA regulation, technical standards and practice say about randomisation, exam integrity, records, pass marks/retakes and CBT approval. Complements (does not repeat) `spec_dd/0. paused/compliance-form-randomization/research_question_bank_patterns.md` and `research_randomization_ux_integrity.md`.

Labels: (a) stated in regulation/TS, (b) SACAA guidance/practice, (c) inference, (?) not found.

Caveat on method: this was a time-boxed web pass. Regulation text was read via acts.co.za reproductions, not the official SACAA PDFs. SA-CATS documents (61, 141, 63) were NOT read in full; they are where the detailed rules sit and must be obtained before the spec is finalised.

## 0. Key framing finding (c)

SACAA runs two distinct kinds of theory exam, and the rules differ:

1. SACAA-conducted exams (Part 61 licence/rating theory, e.g. PPL, Night Rating, FI, Radiotelephony). Questions come from a SACAA Central Question Bank, delivered on SACAA's own PEXO online system at approved Online Testing Centres with SACAA-certified invigilators. The ATO does not generate these papers. FLS randomisation is not relevant to them.
2. ATO-internal assessments (progress tests, end-of-phase/stage tests, end-of-course exams, "proof of theoretical knowledge instruction" for Part 61 initial exam entry, recurrent/operator training tests). These are governed by the ATO's own approved Training and Procedures Manual and course syllabus. This is where FLS randomisation applies.

So the "form randomisation" focus is most plausibly about type 2 (a) integrity of ATO internal tests that gate entry to the SACAA exam, and (b) audit evidence. I found no regulation text that mandates specific randomisation mechanics for type 2.

## 1. Randomisation

- Question order, option order, draw counts per subject, minimum bank size, different paper per retake: (?) Not found in any CAR text I could read. No source I found states a required bank-to-paper ratio, a required shuffle, or a distinct paper per retake.
- (b) SACAA itself uses a Central Question Bank: SA-CATS 61.01.10 is reported (Scribd copy, unofficial) as saying "Questions appropriate to the syllabi will be held in a CAA Central Question Bank". The Examinations page says the Radiotelephony bank was compiled from named references (AIP, ICAO Doc 9432) and that the FI exam's "Principles of flight and flight instruction" database is being weighted until "Theory of instruction" is 50% of the paper. This shows SACAA practice is: bank tagged by subject/topic, paper drawn by syllabus weighting. (c) That is the model an auditor will recognise.
- (c) Syllabus-weighted draw per subject is therefore the defensible design; a fixed number of questions per subject/topic per paper mirrors SACAA's own approach.

## 2. Integrity and security

- (a) 61.01.10(1): Director publishes general exam procedures and conditions in an AIC, as contained in SA-CATS 61. Detail lives there. (Not read.)
- (b) Invigilation: SACAA-conducted online exams require SACAA-certified invigilators who sign a Code of Conduct/Practice (revoked if not submitted); candidate ID required, arrive 45 min early. Source: SACAA Examinations page. Governed by the "Procedure Manual for Accredited or Designated Examination Centres" (title only seen, not read).
- (b) Exams run only on the PEXO system, which is off on weekends/public holidays and maintenance days; SACAA gives no support to centres on those days.
- Question bank confidentiality, no identical papers, time limits: (?) no specific text found. (c) General examination-integrity expectation (ICAO Annex 1 / Doc 9379 style) implies bank confidentiality; not verified here.
- (c) For ATO internal tests, integrity expectations would be set in the ATO's own approved manual, which SACAA audits against ("do what your manual says"). FLS must therefore be configurable to match whatever the client's manual states, not hardcode a policy.

## 3. Records

- (a) CAR 141.01.17 (ATO record keeping): (1) ATO must keep "detailed student records" showing the training course requirements, as approved by the Director, have been met; (2) retain for at least 5 years after training is completed; (3) maintain a system recording qualifications and training of instructors and examiners; (4) retain staff records at least 5 years after the person stops performing a function for the ATO. Format (paper/electronic) is not specified in the text.
- (a) DTOs (Part 141 Subpart 8, 141.08.15): same 5-year retention after completion of training (per search summary; text not read directly).
- (b) 141.06.7 (per search summary, not read directly): records to be made available to the Director within 30 days of request; trainee records are kept at the ATO where the training, testing or checking took place.
- (?) No text found enumerating per-attempt fields (questions served, answers, duration). (c) "Detailed student records showing requirements have been met" in an audit means an attempt must be reproducible: the inspector can ask to see the exact paper the student sat and how it was marked.
- Part 121/135/other operators' recurrent training records: not researched; (?).

## 4. Pass marks and retakes

- (a) CAR 61.01.10(4): pass mark for any theoretical knowledge examination under Part 61 is 75%. (Source read directly.)
- (a) CAR 61.01.10(5): an applicant who fails an Authority-conducted exam may apply to the Director for a re-mark, per SA-CATS 61. (Applies to SACAA exams, not ATO tests.)
- (a) CAR 63.01.13: a flight engineer applicant who fails a theory exam may apply for retesting after "the appropriate period specified in Document SA-CATS 63". The retake waiting period is therefore set in the relevant SA-CATS, not the CAR. The period values were not retrieved. Equivalent Part 61 retest provision (likely 61.01.13 style) and its SA-CATS 61 period not read.
- (b) SACAA Examinations page: candidates must track their own attempts ("7 / 60 days" appears on the page, apparently a re-sit interval/limit pattern; exact meaning unconfirmed) and there is an 18-month window for clearing all examinations (as stated on the page; the exact rule not confirmed).
- (c) 75% is the national theory standard. An ATO internal test that serves as a gate toward Part 61 entry would normally use at least 75% (ATO manual may specify more). Pass mark should be per-form configurable, with 75% as the default for this client.
- (?) Whether ATO internal tests must use a distinct paper on retake: not found.

## 5. Computer-based testing approval

- (b) SACAA Examinations page: online exams (PPL, Night Rating, FI) are held at "Approved Online Testing Centres" on PEXO; Part 62 approved examination centres exist; booking via Form CA 61-91 at least 7 calendar days ahead.
- (?) No regulation or SA-CATS text found stating CBT system technical requirements for an ATO's own LMS. (c) The ATO's use of an LMS for internal tests is covered by the Training and Procedures Manual and ATO approval/audit; SACAA does not (as far as found) "approve" an LMS product. An unrelated e-learning platform risk matrix tender document surfaced in search (SACAA procurement, 2024) and may indicate SACAA's own concerns for an e-learning platform; not read.

## Open items to resolve before spec (need real documents)

1. SA-CATS 61 (examination procedures, retake periods, central question bank text), SA-CATS 141 (ATO training/testing standards), SA-CATS 63.
2. The client's own approved ATO Training and Procedures Manual: its statements about tests, question banks and retakes are what the SACAA auditor checks against.
3. Document "Procedure Manual for Accredited or Designated Examination Centres".
4. Ask the client/product owner which exams are in scope (internal ATO tests vs SACAA-conducted) and which SACAA finding or audit comment prompted the work.

## Implications for FLS randomisation

Required by any source found (a): none of the randomisation mechanics. The only hard, citable requirements are 75% pass mark (Part 61 theory) and 5-year retention of detailed student records (CAR 141.01.17).

Good practice / strongly implied by SACAA's own practice (b, c):
- Question bank with subject/topic tags and syllabus-weighted draws (fixed count per subject per paper).
- Different paper per attempt/retake (draw fresh; avoid repeating identical papers).
- Question order and option order shuffling (not mandated; cheap integrity gain).
- Configurable per-form pass mark (default 75%), time limit, and retake waiting period (the period is set in SA-CATS; make it configurable, not hardcoded).
- Bank confidentiality: learners never see questions outside their draw; no bank browsing.
- Enough bank depth that papers differ (no SACAA ratio found; a ratio is a client decision).

Not mentioned in anything found: option-level shuffling rules, minimum bank-to-paper ratio, per-subject minimum draw numbers, CBT software certification for ATO LMSs.

Per-attempt record SACAA would want (c, to satisfy "detailed student records" with 5-year retention):
- Learner identity (incl. licence/ID reference), form and version, course/phase, instructor/examiner or invigilator if any.
- The exact paper served: ordered list of question identifiers (frozen content, not live references), option order shown, and the draw seed or snapshot, so the paper can be reproduced.
- Each answer given, correctness and marks per question, total score, percentage, pass mark applied, pass/fail.
- Start time, submit time, duration, time limit.
- Attempt number and previous attempt dates (to evidence waiting periods).
- Retention at least 5 years after course completion; retrievable within 30 days of an Authority request; exportable (PDF/CSV) for inspectors. Records must survive later edits to the question bank.

## References

- CAR 61.01.10 Theoretical knowledge examinations: https://source.acts.co.za/civil-aviation-act-2009/nr425_61_01_10_theoretica.php
- CAR 141.01.17 Record keeping (ATO): https://source.acts.co.za/civil-aviation-act-2009/nr425_141_01_17_record_keeping.php
- CAR 141.08.15 Record keeping (DTO): https://source.acts.co.za/civil-aviation-act-2009/nr425_141_08_15_record_keeping.php
- CAR 141.06.7 record keeping: https://www.acts.co.za/civil-aviation-act-2009/nr425_141_06_7_record_keeping_.php
- CAR 63.01.13 Retesting after failure: https://api.acts.co.za/civil-aviation-act-2009/nr425_63_01_13_retesting_.php
- SACAA Examinations page: https://www.caa.co.za/industry-information/personnel-licensing/examinations/
- SA-CATS 61.01.10 (unofficial Scribd copy, unverified): https://www.scribd.com/document/707164324/CAA-SA-CATS-61-01-10-Examination-Information
- CA 61-91 booking form (Scribd, unread): https://www.scribd.com/document/510258656/CA-61-91

status: ok
reason: citable requirements found for pass mark and record retention; randomisation, CBT and per-attempt fields not found in accessible sources (SA-CATS not read)
