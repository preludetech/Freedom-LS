# Active Remediation Loop — UX Pattern Research

Research into how leading LMS and e-learning platforms handle the moment after a learner gets a quiz question wrong. Focus: what counts as "active" remediation vs. passive "here's the right answer" reveals.

## Per-platform patterns

### Khan Academy
- **Inline hint ladder**: multi-step hints revealed one at a time. Clicking "Use a hint" on a practice problem marks the question wrong and exposes only the *next* step — not the final answer.
- **In quizzes/unit tests**, the hint button only appears *after* a wrong answer is submitted, preventing hint-farming.
- **Mastery learning**: progress gated on streaks of correct answers on *different* questions sampled from the skill. Failure demotes the learner's mastery level and forces re-practice.
- Links out to the associated video/article as a remediation step before further attempts.
- No modal; remediation is inline under the question.

### Duolingo
- **Wrong answer immediately shows the correct answer inline** with red banner; user must tap "Continue" to acknowledge.
- **Missed items re-appear at the end of the same lesson** until answered correctly — cannot finish lesson without eventually getting them right.
- **"Explain My Answer"** (AI-generated) gives a plain-language *why* the answer was wrong, not just what the right answer is.
- **Mistakes Review / Practice Hub**: logs every mistake across sessions and resurfaces them in dedicated review lessons.
- **Hearts system** caps wrong answers per session — forces either a break, a review exercise, or premium purchase. Widely disliked (see complaints).

### Coursera / edX
- Quiz feedback is mostly **end-of-attempt**, not per-question. Most graded quizzes allow multiple attempts (often 3, sometimes unlimited with a cooldown of 8–24 hours between attempts on Coursera).
- Explanations appear after submission alongside correct answers; instructors optionally hide correct answers until the due date passes.
- No forced remediation loop — retry is learner-initiated.
- edX instructors can set per-problem attempt counts; "Show Answer" can be locked until attempts exhausted or deadline passed.

### Articulate Storyline / Rise / Adobe Captivate
- Standard SCORM pattern: **Try Again / Review / Submit** layers. Default feedback layer is modal.
- Storyline supports **branching remediation**: wrong answer triggers a jump to a remediation slide, then back to the question (or a sibling question). Variables track attempts, enabling "escalating" feedback ("try again", then "hint", then "forced review of content slide").
- Rise is more template-driven: typically shows correct answer + feedback after each question, with quiz-level retry.
- Common scenario-based pattern: *each wrong choice* has a distinct consequence branch — contextual feedback instead of generic "wrong".

### Moodle
- **Interactive with multiple tries** is the canonical adaptive behaviour: after a wrong answer, learner sees a hint, retries the *same* question, with a configurable per-attempt penalty (e.g. −0.33 per retry).
- **Adaptive mode** and **Adaptive mode (no penalties)** are similar but hints don't reliably display.
- **Hints are ordered** — one per retry — and authored per question. Supports "Clear incorrect responses" between tries.
- Final "overall feedback" bracketed by grade band (e.g. different messages for <50%, 50–80%, >80%).

### Canvas / Blackboard / Absorb / Cornerstone
- Per-answer feedback is authored per option (including per wrong option). Delivery is configurable: immediately, after submission, after due date, or never.
- **Canvas New Quizzes**: "Let Students See Their Quiz Responses" toggles feedback visibility; typical flow is quiz-level retry with instructor-capped attempts.
- **Cornerstone**: no native retry cap — retries managed by course design.
- **Absorb**: quiz-level retry + completion thresholds common for compliance.
- In aviation/compliance LMSs the dominant pattern is still **"pass the quiz at X%, otherwise retake the whole module"** — block-level, not question-level remediation.

### Aviation-specific CBTs (King, Sporty's, Gleim, Redbird)
- **Gleim**: large question banks; wrong answers trigger a full written explanation referencing the FAR/AIM source, then the missed question is tagged for a "study session" that re-drills weak areas.
- **King Schools**: video-driven; wrong answers in the embedded quiz play a short explanatory clip (John & Martha King on-camera) before re-asking or moving on.
- **Sporty's**: explanation + reference citation after each question; "missed questions" bucket for later review.
- **Redbird (GIFT)**: adaptive — wrong answers downshift difficulty and surface prerequisite content.
- **Common aviation pattern**: explicit *citation* of the regulatory source in remediation text. Learners expect to see "§91.205" not just "you got it wrong".

## Cross-cutting UX patterns that recur
1. **Immediate, inline, specific feedback** — not just red/green. The "why" matters more than the "what".
2. **Hint ladder / graduated scaffolding** — reveal progressively; don't dump the answer.
3. **Forced acknowledgement** — user must click "Continue" / "I understand" before proceeding. Creates micro-commitment.
4. **Missed items re-queued within the session** (Duolingo, Khan mastery) — question-level, not module-level retry.
5. **Separate "mistakes review"** surface — persistent log of wrong answers for later practice.
6. **Content linkage** — remediation points to the source content (video, section, regulation).
7. **Escalation on repeat failure** — more content, easier variants, or forced re-view of the source material.
8. **Authorable per-option feedback** — every wrong choice has its own explanation addressing *that* misconception.
9. **Adaptive difficulty / item variation** — retry uses a *different* question testing the same skill, not the same question.
10. **Penalty or mastery threshold** — some cost for getting it wrong (partial credit decay, streak reset) to discourage guessing.

## Common learner complaints
- **"Click-next fatigue"**: PPRuNe pilots describe CBT as "mind-bendingly awful", "sleep-clicked through" — narration paced slower than reading, no skip.
- **Patronising tone**: "Wrong, try again!" style feedback identified as one of the most annoying traits of e-learning (Cavendish).
- **Same question repeated verbatim**: no variation, so learners memorise the right click rather than the concept.
- **"Doesn't explain WHY"**: generic "incorrect" with no rationale. Duolingo's *Explain My Answer* was specifically launched to address this.
- **Can't skip known content**: compliance learners just mash Next; the quiz is the only real signal, which they brute-force.
- **Forced replay of whole module** to retake a short quiz — "endurance test, not learning" (Emergent Learning).
- **Hearts / attempt caps** feel punitive, especially when the wrong answer was a typo or a known-ambiguous translation (Duolingo Hearts backlash on duoplanet, Class Central).
- **Feedback hidden until end**: learners lose the connection between their specific reasoning and the correction.
- **No citation**: aviation learners specifically gripe when remediation doesn't point to the regulation/source.

## Recommendations synthesis (for FLS active-remediation-loop)
1. **Always show a "why"**, not just the correct answer. Authorable per-option explanation (Canvas/Moodle pattern).
2. **Graduated hints before full reveal** (Khan ladder). At minimum: first wrong → hint/explanation, second wrong → correct answer + link to source.
3. **Re-queue missed questions at end of the quiz/topic** until answered correctly (Duolingo). Use *variants* where possible so it's not rote memorisation.
4. **Force acknowledgement** of the explanation (click "I understand" or brief self-check) — cheap, effective, and visible to assessors.
5. **Link remediation to source content** — for SACAA/aviation, cite the regulation or the specific topic section.
6. **Escalate on repeat failure**: after N wrong attempts, force a return to the source content before the question re-appears.
7. **Separate "review my mistakes" surface** — persistent across sessions, supports spaced repetition.
8. **Avoid heart-style punishment**. Use mastery thresholds and streaks instead.
9. **Don't block progress on a single question** — block on mastery of the topic. Lets learners move within a topic but gates the next topic on overall correctness.
10. **Author-time per-option feedback** is the single highest-leverage feature — it turns "red X" into teaching.

## References
- [Khan Academy Mastery Learning](https://www.khanacademy.org/khan-for-educators/resources/teacher-essentials/safety-privacy-and-additional-resources/a/mastery-challenges-course-mastery)
- [Khan Academy Hint Option Help](https://support.khanacademy.org/hc/en-us/community/posts/360054875972-HInt-Option-telling-answer)
- [How Khan Academy is Bringing Mastery Learning to the Masses — Cult of Pedagogy](https://www.cultofpedagogy.com/khan-mastery-learning/)
- [Duolingo Explain My Answer](https://blog.duolingo.com/explain-my-answer-now-free/)
- [Duolingo Review Exercises](https://blog.duolingo.com/review-exercises-help-measure-learner-recall/)
- [Duolingo Hearts Backlash — duoplanet](https://duoplanet.com/its-time-for-duolingo-to-ditch-the-heart-system/)
- [Duolingo Breaks Hearts for Energy — Class Central](https://www.classcentral.com/report/duolingo-breaks-hearts-for-energy/)
- [Coursera Quiz Help](https://www.coursera.support/s/article/209818703-Take-quizzes)
- [edX Timed Exams Documentation](https://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/course_features/timed_exams.html)
- [Open edX Retries Discussion](https://discuss.openedx.org/t/enable-retries-attempts-on-exams/1143)
- [Articulate — Assessment Branching & Remediation](https://community.articulate.com/discussions/articulate-storyline/assessment-branching-remediation)
- [Rise 360 Branching Scenarios](https://community.articulate.com/blog/articles/how-to-easily-create-branching-scenarios-in-rise-360/1086052)
- [Scenario-Based Branching in Storyline — CommLab](https://www.commlabindia.com/blog/scenario-based-learning-branching-articulate-storyline)
- [Moodle Question Behaviours](https://docs.moodle.org/501/en/Question_behaviours)
- [Moodle Adaptive Mode discussion](https://moodle.org/mod/forum/discuss.php?d=439433)
- [Adaptive Mode in Moodle Quizzes — Nottingham](https://blogs.nottingham.ac.uk/learningtechnology/?p=2791)
- [Canvas New Quizzes Feedback](https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-add-feedback-to-a-question-in-New-Quizzes/ta-p/591)
- [Canvas Revealing Feedback for Missed Questions](https://community.canvaslms.com/t5/Canvas-Question-Forum/Canvas-Quizzes-Revealing-Feedback-for-Missed-Questions/m-p/535237)
- [Absorb — Configure Quiz for Completion](https://support.absorblms.com/hc/en-us/articles/15022894461459-Configure-a-Create-Quiz-for-Completion-in-the-LMS)
- [Cornerstone Compliance Training](https://www.cornerstoneondemand.com/learning/compliance-training)
- [Pilots of America — King vs Sporty's vs Gleim](https://www.pilotsofamerica.com/community/threads/king-vs-sportys-vs-gleim-online-ground-school.88050/)
- [Pilots of America — ASA, King, Sporty's or Gleim](https://www.pilotsofamerica.com/community/threads/asa-king-sportys-or-gleim.113065/)
- [Aviation Consumer — Test Prep Comparison](https://aviationconsumer.com/uncategorized/private-pilot-test-prep-sportys-gleim-excel/)
- [PPRuNe — Computer Based Training thread](https://www.pprune.org/archive/index.php/t-80930.html)
- [PPRuNe — A320 Type Rating CBT complaints](https://www.pprune.org/archive/index.php/t-258014.html)
- [E-learning's Most Annoying Traits — Cavendish](https://www.cavendish.ac/e-learnings-most-annoying-traits/)
- [Why People Complain About E-Learning — Articulate](https://www.articulate.com/blog/heres-why-people-complain-about-e-learning-how-to-fix-it/)
- [Common eLearning Assessment Mistakes — BrightCarbon](https://www.brightcarbon.com/blog/common-elearning-assessment-mistakes/)
- [From Box-Ticking to Behaviour — Emergent Learning](https://www.emergentlearning.com.au/post/from-box-ticking-to-behaviour-making-compliance-training-mean-something)
- [Scaffolding Feedback to Maximise Long-Term Error Correction — Memory & Cognition](https://link.springer.com/article/10.3758/MC.38.7.951)
- [Meaningful Feedback in Adaptive Learning — Taskbase](https://medium.com/taskbase/meaningful-feedback-is-essential-for-successful-adaptive-learning-4a9536a2d89d)
- [Alternatives to Correct and Incorrect — eLearning Coach](https://theelearningcoach.com/elearning_design/alternative-feedback/)
