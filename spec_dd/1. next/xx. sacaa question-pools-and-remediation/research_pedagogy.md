# Active Remediation in E-Learning Quizzes — Research Findings

Scope: evidence-informed design input for an active-remediation-loop feature in FLS, with an eye to high-stakes aviation compliance (e.g. SACAA) training.

## Remediation approaches

- **Verification-only** (current baseline) — tells *what* is right but not *why*. Weak on conceptual repair; easy to skim. Fallback only.
- **Elaborative / response-specific feedback** — explains why the chosen distractor is wrong and why the correct answer is right. Strongest evidence base; risk is length (learners skip walls of text).
- **Explanatory re-teaching** — short targeted re-presentation of the concept. Good for missing-fact gaps; weaker for misapplication errors.
- **Worked examples** — step-by-step solutions. Reduces cognitive load for novices; excellent for procedural/decision-rule content (e.g. weight & balance). Loses value once learners are proficient (expertise-reversal).
- **Prerequisite-content branching** — route learner to the exact source section. Powerful with good tagging; risks navigation fatigue.
- **Retry with isomorphic variant** — structurally equivalent question, different surface details. Tests transfer, not memory of the reveal.
- **Socratic / guided-discovery prompts** — hints that narrow the problem without giving the answer. Strong for deep learning; expensive to author well.
- **Metacognitive prompts** — confidence checks, "why did you pick that?". Support calibration; weak alone.
- **Peer / instructor escalation** — necessary backstop for persistent failure in compliance contexts.

## What the evidence says

- **Elaboration beats verification.** Van der Kleij et al. (2015, 40 studies): elaborated feedback ES ~0.49 vs ~0.05 for knowledge-of-correct-results. Wisniewski, Zierer & Hattie (2020, 435 studies, d = 0.48) confirm *more information content → more learning*.
- **Hattie & Timperley (2007)** — effective feedback answers "Where am I going? / How am I going? / Where to next?" at task, process, or self-regulation levels. Self-directed praise and bare "wrong" are least effective.
- **Shute (2008)** — formative feedback should be specific, supportive, non-evaluative, timely, and *not* overly long. Response-specific elaboration outperforms generic explanation and "answer-until-correct" loops.
- **Retrieval + spacing.** Roediger & Karpicke: re-testing missed items after a delay produces far better retention than restudy (13% forgetting with repeated testing vs 56% with repeated study). Adaptive repetition at ~2-week intervals beats single exposure.
- **Timing.** Immediate feedback aids motivation and near-term performance; slightly delayed feedback can aid long-term retention. For high-stakes compliance the safer default is immediate elaborative feedback *plus* spaced re-test.
- **Mastery learning (Bloom).** Requiring proficiency before progression raises outcomes, but Bloom warned unrelieved frustration drives disengagement. Works only with varied remediation and sensible attempt caps.
- **Metacognitive prompts** help calibration when combined with instruction; alone, they don't reliably raise accuracy.

## Recommended pattern for high-stakes compliance training (aviation)

A tiered loop, escalating only as needed:

1. **Attempt 1 wrong →** immediate *response-specific elaborative feedback* (why this distractor is wrong + why the correct answer is right, with the regulation / reference cited). One short metacognitive prompt ("What made you pick that?" or a confidence check before revealing feedback).
2. **Require re-engagement**, not just "next". Either a short re-teaching snippet (worked example for procedural items) or a link to the exact source section.
3. **Retry with an isomorphic variant** (not the same item) to test transfer rather than recall of the given answer.
4. **Attempt 2 wrong →** branch to prerequisite content, then a second isomorphic variant. Track as a flagged gap.
5. **Attempt 3 wrong →** escalate: mark the topic non-mastered, surface to instructor dashboard, and schedule **spaced re-test** (days/weeks later) regardless of eventual pass.
6. **Mastery gate** on the *topic*, not the single item — e.g. 80% on a pool of isomorphic items across a session.
7. **Audit trail**: log attempts, feedback shown, and time-on-feedback (regulators care; it also reveals skip behaviour).

## Pitfalls to avoid

- **Wall-of-text feedback** — learners skip. Keep elaboration under ~3 short sentences plus an optional "read more".
- **Giving the answer away in the feedback, then asking the same question again** — tests memory of the feedback, not understanding. Always use isomorphic variants on retry.
- **Infinite "answer-until-correct" loops** — encourage guessing, erode trust, inflate completion stats. Cap attempts and escalate.
- **Punitive tone** — compliance content especially. Feedback should be corrective, not shaming; self-level feedback ("you failed") is the least effective level in Hattie's model.
- **Remediation that traps the learner** — no visible progress, no escape hatch. Always show where they are in the loop and allow "mark for review, continue".
- **One-shot remediation with no spacing** — passing the retry today ≠ retention next month. Schedule the missed concept to reappear.
- **Over-reliance on metacognitive prompts** without substantive feedback — feels performative.
- **Ignoring item quality** — if many learners miss an item, the item (or its distractors) may be the problem, not the learners. Feed attempt data back to authors.

## References

- Hattie, J., & Timperley, H. (2007). *The Power of Feedback.* Review of Educational Research, 77(1), 81–112. https://journals.sagepub.com/doi/abs/10.3102/003465430298487 (PDF: https://simvilledev.ku.edu/sites/default/files/PD%20Resources/Hattie%20power%20of%20feedback%5B1%5D.pdf)
- Shute, V. J. (2008). *Focus on Formative Feedback.* Review of Educational Research, 78(1), 153–189. https://journals.sagepub.com/doi/10.3102/0034654307313795 (PDF: https://myweb.fsu.edu/vshute/pdf/shute%202008_b.pdf)
- Wisniewski, B., Zierer, K., & Hattie, J. (2020). *The Power of Feedback Revisited: A Meta-Analysis of Educational Feedback Research.* Frontiers in Psychology. https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2019.03087/full — also https://pmc.ncbi.nlm.nih.gov/articles/PMC6987456/
- Van der Kleij, F. M., Feskens, R. C. W., & Eggen, T. J. H. M. (2015). Effects of feedback in a computer-based learning environment on students' learning outcomes: A meta-analysis. (Summarised in) https://link.springer.com/article/10.1007/s10984-024-09501-4
- Roediger, H. L., & Karpicke, J. D. (2006). *The Power of Testing Memory.* http://psychnet.wustl.edu/memory/wp-content/uploads/2018/04/Roediger-Karpicke-2006_PPS.pdf
- Retrieval-Based Learning: A Decade of Progress (ERIC). https://files.eric.ed.gov/fulltext/ED599273.pdf
- Bloom, B. S. (1968). *Learning for Mastery.* Overview: https://en.wikipedia.org/wiki/Mastery_learning
- Repeat individualized assessment using isomorphic questions. International Journal of Educational Technology in Higher Education (2021). https://educationaltechnologyjournal.springeropen.com/articles/10.1186/s41239-021-00257-y
- Cognitive Load Theory and worked examples. https://www.mdpi.com/2227-7102/14/8/813
- Timing of feedback and retrieval practice. Nature HSSC (2024). https://www.nature.com/articles/s41599-024-03983-6
- FAA Aviation Instructor's Handbook, Ch. 9 (remediation when trends indicate inadequate skill/knowledge). https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/aviation_instructors_handbook/11_aih_chapter_9.pdf
- Metacognition Guide (Agarwal et al., retrievalpractice.org). https://pdf.retrievalpractice.org/MetacognitionGuide.pdf
