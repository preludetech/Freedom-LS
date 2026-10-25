# Downstream edits for the recommend outcome

Edits outside the code that the plan carries out once the spec lands.

- `spec_dd/1. next/roadmap.md`, Registration rules, "Unknowns resolved inside a spec": mark "How
  organisation-owned rules scope `RecommendedCourse`" settled. Each rule keeps its own
  `RuleRecommendation` on a recommendation, and the row is deleted when the last one goes, so no
  rule touches another organisation's rows (spec decision 1).
- `spec_dd/1. next/corporate-job-course-recommendations-4-educator-interface-screens/idea.md`:
  record the same answer, and that a recommendation can carry several rules from different
  organisations. An organisation's screens show its own rules' `RuleRecommendation`s.
- `spec_dd/2. in progress/educator-interface-11-audit-log/idea.md`: add that a rule creating or
  removing a recommendation is an action it records.
