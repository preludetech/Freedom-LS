# Save an immutable version whenever a question changes

Spec 3 of 5 in the SACAA content versions and access effort. Read the "SACAA content versions and access" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Whenever `content_save` finds that a `FormQuestion` differs from its latest saved state, it saves a new immutable version of that question. The `FormQuestion` row keeps its uuid and stays the live row; the live row is always the latest version. Old versions are kept and never served to anyone.

Each version records the question as it was: text, type, required, min, max, decimal_places, and every option's text, value, order and correct, plus the set of options. It also records when it was saved and the commit hash that `sacaa-compliance-content-versions-and-access-1-content-save-safety` records for the save.

An attempt pins the version of every question it is served when it starts. An attempt in progress finishes on those versions, even if `content_save` revises a question meanwhile; only attempts that start afterwards get the new version.

Everything that shows or scores a past attempt reads the version the learner answered, not the live row: quiz scoring, the results page and its incorrect-answers list, the form export, and the admin answer views that remain. These readers go through the served-paper reader (`sitting_path()` / `served_path()`), which returns the pinned versions for a sitting.

Answers recorded before versions exist get version 1, which is the content as it stood when the migration ran. The record says so: it is not the original wording if the question changed earlier.

## Why

SACAA requires that "whenever a question is revised it shall be blocked from the random questions available to the student but, should remain in the system for audit purposes". Today `content_save` overwrites the question and option rows in place on every run. A completed attempt then shows today's wording and today's correct answers against yesterday's answer, and the only surviving trace is the frozen `FormProgress.scores`. An auditor testing an old attempt cannot see what the learner was asked.

Immutable version rows under a stable `FormQuestion` identity leave `QuestionAnswer`, the served paper, `condition_option`, the keep-together groups of `sacaa-compliance-2-shuffle` and the pages that `sacaa-compliance-3-question-pools` draws from untouched, and add the history beside them. Moodle uses the same split of stable entry and immutable version, with attempts pinned to the version. A carve-out for minor edits is rejected because it would defeat the audit.

## What is settled

- **Identity.** `FormQuestion` keeps its uuid as identity. No new `FormQuestion` row is created for a revision. The authored uuid stays the sync key.
- **A new model holds the versions.** Its name is for the spec to choose. Rows are immutable once saved. A question has an ordered series of them, numbered from 1.
- **When a version is saved.** `content_save` saves a new version whenever any versioned field differs from the latest version of that question. The comparison is exact. There is no minor-edit carve-out: a corrected typo is a new version.
- **What a version covers.** `FormQuestion` question text, type, required, min, max and decimal_places; and, for every option, text, value, order and correct; plus the option set, so an added or removed option is a change. Nothing else counts: `file_path`, `slug`, `tags`, `meta`, `updated_at`, placement on a page, section links and the shuffle lock and group settings do not make a version.
- **Not versioned.** `FormContent` and `FormPage` are not versioned. A rewritten stimulus does not create a version of the questions that depend on it.
- **What each version records.** When it was saved and the commit hash recorded by `sacaa-compliance-content-versions-and-access-1-content-save-safety`.
- **Old versions are never served.** The live `FormQuestion` and its options always equal the latest version, so a revised question is shown to new attempts as its latest version only. This is what blocks the old wording from the random questions available to the student. Old versions exist only for audit readers.
- **Pinning at attempt start.** The attempt records the version of every question it is served when it starts, alongside the served paper that `sacaa-compliance-2-shuffle` and `sacaa-compliance-3-question-pools` write at that moment. An attempt in progress renders, resumes and scores on the pinned versions. A question revised while the attempt is open does not change under the learner.
- **Readers of a past attempt read the answered version.** Scoring (`FormProgress.compute_quiz_scores()` and the quiz correctness check), the results page and the incorrect-answers list, the form export, and the admin answer views read the pinned version through `sitting_path()` / `served_path()`. A reader does not look the live row up for a past attempt. The stored score is not recomputed against the live row.
- **Answers from before versions exist.** The migration creates version 1 for every existing question from its content at migration time and pins existing answers to it. This is stated as such, in the migration and in the documentation that describes versions. It is not claimed to be the wording the learner saw.
- **Admin answer views of QUIZ forms are hidden** by `sacaa-compliance-content-versions-and-access-4-question-access`, so only the admin answer views that remain (survey and application) need to read versions through the served-paper reader or be stated as exempt.
- **Hand edits.** The admin question and option pages are removed by `sacaa-compliance-content-versions-and-access-4-question-access`, so `content_save` is the only path that changes a question and the only place versions are saved.
- **Ordering with retired content.** Retiring content is `sacaa-compliance-content-versions-and-access-2-retire-removed-content`. A question retired there keeps its versions and its answers; this child adds no second retired state. A revision does not retire the question.
- **Non-QUIZ forms.** A survey or application sitting that is shown after a revision shows the same stored data as today unless the spec's pin decision (below) covers it.
- **Regrading is not built.** A completed attempt's stored `scores` are not changed by a revision or by this migration.

## Open until the spec

- **Where the pin lives.** Options: a `versions` key in the served paper, or a nullable FK from `QuestionAnswer` to the version. The served paper has no record for non-QUIZ sittings, and an answer can exist before a paper key is read. Recommendation: pin in the served paper for QUIZ sittings, which is where the shuffle and pool specs already write the attempt's fixed content, and add the `QuestionAnswer` FK for the answered version so the answer states its own version and non-QUIZ sittings are covered. If one is chosen alone, choose the served paper and leave non-QUIZ sittings on the live row, stated as a limit.
- **How the cohort and learner reports in `reports/` handle versions.** They aggregate by question id and option id and do not go through the served-paper reader, so a revised question mixes two meanings in one row. Recommendation: the reports read the pinned version per attempt where they already have the attempt, and group their statistics by version; if that is too large for this child, leave the aggregate statistics on the live row with the limitation written into the report and the documentation, and let the per-attempt learner detail read the answered version.
- **Whether the hash is taken on stored markdown.** `save_with_uuid` translates the markdown after the row is written, so the authored text and the stored text differ (embedded images become components). Recommendation: compare and hash the stored, translated value, so a change in translation output makes a version and an unchanged stored value never does.
- **How a version exposes the question to templates and scoring.** The paper-reading code and templates today use model instances (`rendered_question()`, option text and `correct`). The version must give the same interface or be built into instances. Recommendation: version-backed objects with the same attributes, carrying the live option ids so `QuestionAnswer.selected_options` still match.
- **How the option set is stored in a version** (JSON snapshot or version-owned option rows). Recommendation: a JSON snapshot on the version, with the live option ids included.
- **Change detection on first run.** Recommendation: a question with no version yet gets version 1 on the first `content_save` after the migration, without double-counting the migrated version 1 when the content has not changed.

## Out of scope

- Retiring and un-retiring removed content: `sacaa-compliance-content-versions-and-access-2-retire-removed-content`.
- The educator view of the version answered, when it changed and whether it is still served: `sacaa-compliance-content-versions-and-access-5-answered-version-review`.
- The role, permission and audit entries, and removing the admin question pages and QUIZ answer views: `sacaa-compliance-content-versions-and-access-4-question-access`.
- The git cleanliness check and recording the commit hash: `sacaa-compliance-content-versions-and-access-1-content-save-safety`.
- The shuffle and the draw themselves: `sacaa-compliance-2-shuffle` and `sacaa-compliance-3-question-pools`. This child adds the pin beside what they write at attempt start and does not change how they choose.
- The educator attempt review that this child's versions feed: `sacaa-compliance-4-attempt-review`.
- `content_snapshots` (paused), versioning topics, courses, `FormContent` or `FormPage`, regrading, and the learner's `quiz_show_incorrect` results setting.
- Versioning `CATEGORY_VALUE_SUM` scoring beyond reading the pinned option values where the served-paper reader already does.

## Resources

- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-3-question-versions/research_question_version_seams.md` (all sections: models, readers, in-progress attempts, the two shapes, what counts as a change, interaction with shuffle and pools).
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md` (Moodle stable entry plus immutable version, Canvas, Open edX, Questionmark).
- `spec_dd/2. in progress/sacaa-compliance-2-shuffle/idea.md` (the served paper this child writes beside; blocker).
- `spec_dd/1. next/sacaa-compliance-3-question-pools/idea.md` (the draw at attempt start; collides on the served paper).
