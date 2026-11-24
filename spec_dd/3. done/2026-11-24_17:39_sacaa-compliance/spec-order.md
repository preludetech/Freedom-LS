Archived from the spec roadmap on 2026-11-24, when the last of its specs finished.

## SACAA compliance

Priority: 🔴 High

Quiz randomisation and a per-attempt record of the paper served, for training organisations audited by SACAA. Parent: `sacaa-compliance`.



**Notes**
- Build order: `sacaa-compliance-3-question-pools` and `sacaa-compliance-4-attempt-review` run in parallel.
- Decided: randomisation is opt-in per quiz form and off by default; existing quizzes behave exactly as today.
- Decided: one seed per attempt and the served paper saved at attempt start; a retake is a new attempt with a fresh draw and order.
- Decided: scoring, results, export and review read the served paper, never a re-derived shuffle or the whole form, and a draw keeps `max_score` the same for every attempt.
- Assumption: randomisation applies to quiz forms only, which already ban `when` conditions, so shuffles and draws cannot break a condition.
- Assumption: no SACAA text found mandates a randomisation mechanic; the client's ATO manual is the audit reference, so the effort ships common practice.
- Out of scope: exam time limits, retake waiting periods, frozen copies of question text (`content_snapshots`, paused), difficulty-weighted draws, banks shared across forms, draws by course section.
- References: `sacaa-compliance/research_sacaa_requirements.md` and `sacaa-compliance/research_form_engine_seams.md`.
