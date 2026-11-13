# Test out of course sections

Spec 2 of 5 in the Learner interface features effort. Read the "Learner interface features" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A learner takes a pretest and, for each section they show they already know, skips that section. The skip counts as finished, but is recorded as its own kind of completion, separate from completing by study. Sections the learner did not show they know are done the normal way.

The source scenario: a certification is renewed every 2 years by taking a renewal course that covers the same ground as the original. Learners who have been using their skills probably know most of it, and the original course may have changed since they took it.

## Why

Making experienced learners repeat everything wastes their time. Research on expertise reversal says instruction that helps novices can waste or hurt experts. The pretest also helps the sections the learner does not skip, if its questions match the section.

The risk is completion semantics. Other systems (Moodle, Canvas, Docebo) reach test-out only by workarounds, and each breaks on what "complete" means for a skipped section. Regulators want the score, the date and which version of the content was tested. So the record is designed first.

## What is settled

From the source idea:
- Learners pre-assess with a test, and doing well means they do not do the related sections.
- The idea floats per-section pre/post tests and one big up-front test, and says "if there is a better way, do it the better way". It does not fix the shape.
- A section the learner has already shown they understand does not need its final blocking quiz.
- A section that needs more study is highlighted.

From the effort:
- Quiz questions name the section they test. `learner-interface-features-1-question-sections` gives them that; this spec builds on it and does not redo it.
- `learner-interface-features-3-revision-questions` must treat test-out completion as finished. Whichever of the two lands second wires that in.
- Design questions are settled in this spec's own research, not before it.

Facts about today's code:
- Nothing marks an item done other than studying it. No skip, exempt or waived status exists.
- Progress is keyed to the placement (`ContentCollectionItem`), not the content. A `CoursePart` is the only grouping, it does not nest, and a course may have none.
- The "final blocking quiz" is an ordinary scored quiz form with a pass mark, placed anywhere. Nothing marks it as a section's quiz. A failed scored quiz blocks everything after it.
- `completed_collection_item_ids` is the shared definition of "done" for percentage, outline, finish page and outstanding items. The sequential unlock reads rows directly through `_fetch_player_progress_maps`.
- The cohort report, the educator learner page, the admin and at-risk flags read raw rows, so a new kind of completion would be invisible to them unless changed.
- Course completion is stamped only when the learner visits the finish page, and that is where the `course.completed` webhook and GA4 event fire. Neither carries any sign of how the course was finished. The progress API reads `progress_percentage` and `completed_time`.
- Content has no version, hash or change marker, and `updated_at` moves on any save. A content reload never rewrites progress.
- A learner has one individual registration per course. A second pass today needs a new cohort registration, which gives a separate, unlinked progress record.
- Attempts at a quiz are unlimited and show the same questions every time. No pool, draw or shuffle exists.
- Quiz scoring gives one score per form; there is no per-section score and no per-section pass mark.
- `compliance-form-randomization` (question pools and draws) sits in `spec_dd/0. paused/` and is not built. `content_snapshots` (immutable point-in-time snapshots of content) is also paused there and not built. Nothing here may assume either exists.

## Open until the spec

Each is for `/sdd:spec_from_idea` to settle. Options come from the research files.

1. **Pretest shape.** One up-front test; a pre-test before each section; or a combination (source idea). A big test must not become a sequential blocker. Pretest scoring per section needs the section link from `learner-interface-features-1-question-sections`. Routing cannot live in form branching, which does not combine with quizzes.
2. **Pass mark.** Per section, overall, or both; whether a section needs a minimum number of questions to count.
3. **What a skipped section counts as.** Only its quiz; the whole section; or each child placement. Marking every child makes the percentage jump, and a course can then finish with no study.
4. **Where a skip shows.** Percentage, the course outline and unlock, the finish page and course completion, the cohort report, the educator learner page, the admin, the progress API and the `course.completed` webhook. Options: add the skip inside the shared definition of "done" and surface it separately in the raw-row readers; and either add a field to the API and webhook payload or accept that a tested-out course looks the same as a studied one. A fully tested-out course also needs a finish-page visit unless completion is stamped sooner.
5. **What is recorded for audit.** Score, date and content version are what regulators want. Content version has no home today; the options are a fingerprint written by the content loader, a snapshot from the paused `content_snapshots`, structure only (set of placements), or the pretest result alone.
6. **Content changed since a prior completion.** Always unskippable; skippable on the pretest alone; or skippable only if unchanged. Depends on the previous item. Whether test-out is offered only to learners who completed the original course.
7. **Renewal registrations.** Renewal as a new registration outside this work; or a link from the new progress record to prior completed evidence; and whether a new cohort registration is the route.
8. **Retakes and question pools.** One attempt; a cooldown; or unlimited with fresh questions and a pool larger than the draw. Whether this depends on un-pausing `compliance-form-randomization` or ships without it. Whether answers are shown after the pretest (pretesting effect) or withheld to protect the pool.
9. **Decline the pretest.** Whether a learner can skip the pretest and do everything.
10. **Never-skippable sections.** Whether an author can mark a section as never skippable, and where that is authored.
11. **Fail path.** Study only the failed sections, or the whole course.
12. **Reconciling the roadmaps.** `docs/product/roadmap.md` lists recertification under "Not planned", and the Deadlines effort in `spec_dd/1. next/roadmap.md` lists "recertification, retakes" as out of scope. The renewal scenario is recertification. The spec settles which wording changes.

## Out of scope

- Giving questions their section: `learner-interface-features-1-question-sections`.
- Revision questions, scheduling and explanations: `learner-interface-features-3-revision-questions`, which owns counting test-out completion as finished if this spec lands first.
- Flashcards: `learner-interface-features-4-flashcards`.
- Protected video: `learner-interface-features-5-protected-video`.

## Resources

- `spec_dd/1. next/learner-interface-features-2-test-out/research_content_and_completion.md`: course structure, completion and gating, who reads completion, content versioning, registrations and renewal.
- `spec_dd/1. next/learner-interface-features/research_question_model.md`: how questions are modelled and linked to content, per-section scoring gaps, retakes and pools, and the paused randomization work.
- `spec_dd/1. next/learner-interface-features/research_learner_features.md`, section 1: how other systems do test-out, compliance and audit expectations, gaming, learning science and design questions.
- `spec_dd/1. next/learner-interface-features/idea.md`: the source brief ("Testing out").
- `spec_dd/0. paused/compliance-form-randomization/` and `spec_dd/0. paused/content_snapshots/`: paused designs for question pools and content versions.
