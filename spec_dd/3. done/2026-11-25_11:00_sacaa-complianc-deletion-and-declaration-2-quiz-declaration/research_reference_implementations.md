# Research: reference implementations of a pre-attempt declaration

Scope: how other LMSs gate a quiz attempt behind an honour/attestation statement. Web sources only; I did not clone any repository. Where a point could not be verified it says so.

## Summary

- Only Moodle has a real, built-in gate. It is a quiz access rule, and it is a gate only: it does not store evidence.
- Canvas, Blackboard, Brightspace and Open edX have no first-class "sign before the attempt" feature. Institutions work around it with a required pledge question or pledge quiz.
- None of the systems I found stores verbatim text, typed name, time and IP against the attempt. FLS's design (immutable per-attempt record) goes beyond every reference here.
- The useful borrowed ideas are all from Moodle's structure: an off-by-default per-quiz setting, a check that runs only when a new attempt starts, and a hook that fires after the check passes.

## Moodle: `quizaccess_honestycheck` ("Acknowledge plagiarism statement")

Sources:
- https://moodle.org/plugins/quizaccess_honestycheck (the fetch returned 403; the search snippet gave the description)
- https://github.com/moodleou/moodle-quizaccess_honestycheck
- https://raw.githubusercontent.com/moodleou/moodle-quizaccess_honestycheck/master/rule.php
- https://docs.moodle.org/dev/Quiz_access_rules

Findings:
- **Where the setting lives.** It is a per-quiz option on the quiz settings form, added by the access rule plugin. It is stored in its own table, `quizaccess_honestycheck`, with `quizid` and `honestycheckrequired`. A row exists only when the option is on. Turning it off deletes the row, and deleting the quiz deletes it too. It is off by default.
- **Statement text.** The text is a Moodle language string, shared by every quiz. Admins change it through language customisation. There is no per-quiz text. FLS's per-quiz text with an app-setting default is richer.
- **Per attempt or not.** It is asked once per new attempt. `is_preflight_check_required($attemptid)` returns true only when there is no attempt id, so a resumed attempt is not asked again. There is no "once per learner" mode.
- **UI.** The rule adds a heading, the statement and a checkbox to Moodle's "preflight" form, a modal or page shown when a student clicks "Attempt quiz now". `validate_preflight_check()` returns an error if the box is unticked.
- **What is stored.** Nothing. In `rule.php` the checkbox is only validated, never persisted. No name, time or IP is recorded, and teachers cannot see who agreed. Moodle's own attempt log shows only that an attempt began.
- **Extension points** (from the dev docs): `is_preflight_check_required`, `add_preflight_check_form_fields`, `validate_preflight_check`, `notify_preflight_check_passed` and `current_attempt_finished`. `notify_preflight_check_passed` is the hook where a rule could write an evidence record. Whether it also fires on resume is not stated in the docs I read.
- **Resume and direct links.** Moodle guards the attempt page by validating the attempt server-side. Web-service tracker MDL-53976 shows that `view_attempt` and `view_attempt_summary` had to take `preflightdata` so the rule is re-validated there (https://tracker-old.moodle.org/browse/MDL-53976). Lesson: every entry point has to run the same check, not just the start button.

Lessons for FLS:
1. A rule-style check with a single "is it required" decision, called from every route into the pages, matches the "every route is guarded" decision in idea.md.
2. A per-quiz row or field for the setting is normal. FLS's front matter equivalent is fine.
3. The gap Moodle leaves open (no persisted evidence) is what this spec fills. The `notify_preflight_check_passed` pattern suggests writing the record in the same step that creates the attempt.

## Canvas (Classic and New Quizzes)

Sources:
- https://edtech.unc.edu/2022/11/adding-the-honor-pledge-in-canvas/
- https://community.canvaslms.com/t5/Canvas-LMS-Blog/Adding-Academic-Integrity-to-Quizzes/ba-p/271293
- https://lts-help.its.virginia.edu/m/116292/l/1662615-revise-quizzes-and-surveys-settings-in-copied-canvas-quizzes
- https://services.stthomas.edu/TDClient/1898/ClientPortal/KB/ArticleDet?ID=108231

Findings:
- There is no built-in pledge setting. UVA's help page says so directly.
- Workarounds:
  - Put a pledge question in the quiz. Students can skip it, because Canvas cannot make one question required before the others.
  - Run a separate one-question pledge quiz. The Modules "score at least 1 point" requirement then gates the real exam.
  - Put the statement in the quiz instructions.
- The "require an access code" restriction is a different control, not a pledge.
- Stored evidence: only the pledge quiz's submission (timestamp and answer). No typed name or IP is stored specifically for the pledge. Canvas does keep per-submission IP in its quiz logs, but that is unrelated to the pledge.

## Blackboard (Ultra and Original)

Sources:
- https://stearnscenter.gmu.edu/wp-content/uploads/20-Proctoring_Guide_for_Faculty.pdf
- https://tips.uark.edu/?p=39989

Findings:
- There is no built-in feature. Instructors add an unscored first question (assignment-style or true/false) carrying the pledge text, and ask students to agree or type their name.
- The attestation is therefore an ordinary answer, part of the attempt's submission data, and it is not guarded. The student can navigate past it unless the question is made required.

## Brightspace / Vanderbilt honor code quiz

Sources:
- https://www.vanderbilt.edu/brightspace/creating-an-honor-code-quiz/
- https://cdn.vanderbilt.edu/vu-URL/wp-content/uploads/sites/156/2021/10/19191816/Create-an-Honor-Code-Quiz.pdf

- This is the same pattern as Canvas: a one-question honour quiz, and a conditional release that unlocks the real exam only after it is completed. The statement and answer are held as an ordinary quiz attempt. There is one gate per student per course item, not per exam attempt.

## Open edX

Sources:
- https://pypi.org/project/edx-proctoring/

- A search of edx-proctoring (PyPI changelog pages) found no honour-code attestation step before an attempt. Its proctored-exam flow has a separate acceptance step for the proctoring rules, which creates a per-attempt record with a status. I could not verify the fields it stores, so treat any further claim about it as unconfirmed. Open edX's course-level "honor code" is a sign-up or verification-time agreement, not a quiz-attempt one. I did not verify this either.

## TalentLMS, Google Forms, DocuSign-style flows, open-source Django LMSs

- TalentLMS: nothing relevant found in search, so no claim is made.
- Google Forms and DocuSign: not searched. This is my general knowledge, not sourced. DocuSign-style flows keep a signed-event record (signer name, timestamp, IP, document hash) that cannot be changed, and an audit certificate. This is the closest industry model to the evidence record FLS wants. Treat it as background only, since it was not verified in this pass.
- No open-source Django LMS with a quiz declaration was found in the search results. I did not run a dedicated search of GitHub.

## Comparison

| System | Where the setting lives | Per attempt | Stored | Shown to teachers | Resume or deep link |
|---|---|---|---|---|---|
| Moodle honestycheck | Per-quiz row in own table | New attempts only, not on resume | Nothing | No | Rule re-validated on every attempt entry point (MDL-53976) |
| Canvas | None built in | n/a | Pledge quiz or question answer | As an ordinary submission | Skippable inside a quiz; gated only by module prerequisite |
| Blackboard | None built in | Per test if the question is copied | An ordinary answer | As an ordinary answer | Not guarded |
| Brightspace and Vanderbilt | Conditional release | Once per course item | A quiz attempt | As an ordinary quiz result | Release condition |
| Open edX | None found | n/a | n/a | n/a | n/a |

## Design implications for the spec

1. **Own append-only record is the safer choice for "never updated".** Moodle keeps the setting separate from the attempt. Fields on `FormProgress` can be edited by any code that saves the progress. A separate model, written once and tied to the `FormProgress`, also lets "once per learner" be one existence query. This answers the first open question in idea.md. It is a design judgment from these references, not something one of them proves.
2. **Guard all routes with one shared check.** Moodle's MDL-53976 shows that a deep link or API route left out of the check becomes a bypass. FLS should call one function from start, resume and fill-page views.
3. **Write the record in the same transaction that creates or confirms the attempt.** This follows `notify_preflight_check_passed`. It also fits the `START_REUSE_WINDOW` rule, so a reused start does not sign twice.
4. **Gate on new attempts, as Moodle does, but FLS must also guard resume.** Moodle skips the check on resume because the attempt exists only after the check passed. FLS must still refuse to show the fill pages for any attempt that has no signed declaration (for example, one created before the setting was turned on). This is the point where FLS has to differ from Moodle.
5. **Text snapshot.** Moodle's language string can change after the fact and nothing is stored. FLS must copy the text as shown into the record.
6. **Per-quiz text with a default.** Moodle has only a global string. The FLS design (author text, app-setting default) is a superset.
7. **"Once per learner".** No reference implements it. The Canvas and Brightspace module gate is the nearest, and it is scoped to the course item. That supports scoping the earlier-signature lookup to the same form and user. Whether to scope it to the same course as well is not answered by any source.

## Reference URLs

- https://moodle.org/plugins/quizaccess_honestycheck
- https://github.com/moodleou/moodle-quizaccess_honestycheck
- https://raw.githubusercontent.com/moodleou/moodle-quizaccess_honestycheck/master/rule.php
- https://docs.moodle.org/dev/Quiz_access_rules
- https://tracker-old.moodle.org/browse/MDL-53976
- https://edtech.unc.edu/2022/11/adding-the-honor-pledge-in-canvas/
- https://community.canvaslms.com/t5/Canvas-LMS-Blog/Adding-Academic-Integrity-to-Quizzes/ba-p/271293
- https://lts-help.its.virginia.edu/m/116292/l/1662615-revise-quizzes-and-surveys-settings-in-copied-canvas-quizzes
- https://services.stthomas.edu/TDClient/1898/ClientPortal/KB/ArticleDet?ID=108231
- https://stearnscenter.gmu.edu/wp-content/uploads/20-Proctoring_Guide_for_Faculty.pdf
- https://tips.uark.edu/?p=39989
- https://www.vanderbilt.edu/brightspace/creating-an-honor-code-quiz/
- https://cdn.vanderbilt.edu/vu-URL/wp-content/uploads/sites/156/2021/10/19191816/Create-an-Honor-Code-Quiz.pdf
- https://pypi.org/project/edx-proctoring/

status: ok · reason: Moodle, Canvas, Blackboard and Brightspace covered from sources. Open edX, TalentLMS, Google Forms, DocuSign and Django LMSs have little or no verified evidence, and the file says so.
