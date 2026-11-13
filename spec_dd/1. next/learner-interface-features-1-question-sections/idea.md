# Question sections

Spec 1 of 5 in the Learner interface features effort. Read the "Learner interface features" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A quiz question names the course section it tests. The author writes that link in the form file, and it survives a `content_save` reload. This is the one primitive the later features share, and it ships on its own before any of them.

## Why

`learner-interface-features-2-test-out` has to score a pretest per section, to decide which sections a learner can skip. `learner-interface-features-3-revision-questions` has to add a section's questions to a learner's revision bank and point a wrong answer back to the section to revise. Both need the same data: which section a question covers. Building it once, ahead of both, keeps them from each inventing their own link. Today a quiz placed after a section tests it only by position, and nothing records it.

## What is settled

From the source idea and the cut:
- A question knows the section it tests. That is the whole feature; the two features that use it are separate specs.
- The author states the link in the form file, not in the admin.
- This spec has no blocker and blocks `learner-interface-features-2-test-out` and `learner-interface-features-3-revision-questions`.
- Design questions about the section are settled in this spec's own research, not in the cut.

Facts about today's code (`research_question_model.md`, `research_content_and_completion.md`):
- `FormQuestion` has no link to course content. It belongs to exactly one `FormPage` of one `Form` (required CASCADE FK) and cannot be shared across forms.
- The only grouping of course content is `CoursePart`. Parts do not nest, are optional, and one demo course (`functionality_demo_course_parts`) uses them. A part is a shared row and can be placed in several courses; progress hangs off the placement (`ContentCollectionItem`), not the part.
- A question carries `tags` and `meta`, valid in YAML and stored by the loader. Nothing reads them for questions.
- `content_save` writes a `uuid` into the source file on first load. A question or option that keeps its `uuid` keeps its row through edits and moves. The author-written question `slug` is separate: unique per form, used only by `when`.
- `when` is not allowed in a `QUIZ` form.
- The pydantic schema models for questions and options forbid extra keys, so a new key needs a schema change.
- `form_engine` depends on `content_engine`, not the reverse.

## Open until the spec

These are for `/sdd:spec_from_idea` to settle with its own research. None is decided here.

1. **What a section is.** Options in the research: a `CoursePart`; a run of placements in a course; a group the author names. Parts are optional and rare in the demo content, so a part-only answer would leave flat courses without sections. Whatever is chosen has to work for the renewal-course case, where the same content is placed again. See `research_content_and_completion.md` section 1 and `research_question_model.md` section 4.
2. **One section per question or several.** The revision research asks this directly. A question tested in more than one section changes what "its section" means for pointing back a wrong answer. See `research_learner_features.md` section 2, design questions.
3. **How the link is authored.** Options in the research: `tags` on the question (no migration, no check that the section exists); a field naming the part or topic by path or `uuid`, resolved the way `children:` references are; a separate bank model. Includes whether a link by name or path survives a rename or a move.
4. **How the link survives `content_save` reloads.** Question identity holds only while the `uuid` stays in the file. The spec says what happens when the link target is renamed, moved or re-placed, and what a question authored without a `uuid` does on its first load.
5. **Whether a question can live outside a placed form (a bank form).** Today every question sits on a form page. The research says a form with no placement may not load; that is unconfirmed (`research_question_model.md` section 10, fact b). Whether `learner-interface-features-3-revision-questions` needs this is its concern; this spec decides only whether the link has to support it.
6. **What happens when the named section is removed.** Includes a question whose target no longer exists, and a question dropped from a file. The research found no code in `content_save` that deletes dropped questions, and answer rows are PROTECTed; that needs checking (fact a).
7. **What validation the link gets.** Whether a link to a missing section is an error at load, a warning, or allowed, and what the `fls-content` validator and docs say.

## Out of scope

- Explanations on questions or options. Owned by `learner-interface-features-3-revision-questions`.
- Per-section scoring, pass marks, the pretest's shape and any skipped-section status. Owned by `learner-interface-features-2-test-out`.
- The revision bank, scheduling and weak-section highlighting. Owned by `learner-interface-features-3-revision-questions`.
- Flashcards (`learner-interface-features-4-flashcards`).
- Question pools, random draw and shuffling (the paused `compliance-form-randomization`).
- Showing the section to the learner anywhere in the UI.

## Resources

- `spec_dd/1. next/learner-interface-features/research_question_model.md`: the form model family, authoring and loading, stable identifiers, and the options for linking a question to content (section 4 and "Implications for the cut").
- `spec_dd/1. next/learner-interface-features-2-test-out/research_content_and_completion.md`: course structure, `CoursePart` and placements, completion, and reload behaviour for placements.
- `spec_dd/1. next/learner-interface-features/research_learner_features.md`: how other systems tie questions to sections, and the design questions both later features raise.
