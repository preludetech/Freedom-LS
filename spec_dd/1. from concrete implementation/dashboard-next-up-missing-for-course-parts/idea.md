# Idea: dashboard "Next up" hint is missing for course-parts courses

## The bug

Source: `system_qa/05_completion_and_dashboard/qa_report.md`, **Minor observation 2**.

On the learner dashboard, in-progress course cards show a **"Next up: …"** hint pointing at the
resume item. This appeared correctly on the "…show end with Topic" (43%) and "QA Free Course"
(0%) cards, but was **missing** on the **course-parts** card
("Functionality Demo - Course Parts", 43%).

This points at the "next item" resolution not handling **part-structured** courses — the same
resolver that works for flat courses appears to return nothing (or fails to render the hint) when
the course is grouped into parts. It is cosmetic in impact but inconsistent, and it's on the
main learner surface.

## Expected fix

In the FLS dashboard "next up" / resume-item resolution, ensure the next-incomplete-item lookup
traverses **course-parts** structure correctly, so the "Next up: …" hint renders consistently for
part-structured courses just as it does for flat ones. (Worth checking this is the same code path
as the dashboard resume link, which *does* land on the correct item — so the item is resolvable;
the hint just isn't being produced/shown for parts courses.)

## Sources

- `system_qa/05_completion_and_dashboard/qa_report.md` — Minor observation 2 (and Tests 2 & 4
  describing the working "Next up" hint and resume behaviour on flat courses).
