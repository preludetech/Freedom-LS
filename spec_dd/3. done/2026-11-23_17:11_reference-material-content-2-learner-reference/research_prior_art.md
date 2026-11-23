# Prior art: learner reference listing and topic pages in the course player

Question: what has already been tried, here or elsewhere, and what happened? Facts only. Paths are repo-relative. `git log` was unavailable, so history is read from `spec_dd/` (`1. next`, `2. in progress`, `3. done`). Vocabulary: reference part = a `CoursePart` attached by a `CourseReferencePart` row; learning path = `Course.items`.

## 1. Here

### 1.1 No earlier attempt at untracked side content in the player

- No spec in `spec_dd/3. done/` built a player route outside the indexed `courses/<slug>/<int:index>/` numbering, a sidebar addition in `_course_base.html`, or an untracked learner page. The only specs that record reference material are the effort's own: `spec_dd/1. next/reference-material-content/` (`idea.md`, `research_learner_player.md`, `research_educator_content.md`), siblings `-3-educator-reference` and `-4-library-courses`, and `spec_dd/1. next/roadmap.md` "Reference material" (line 76; spec 2 is "in progress" and spec 4 is blocked by it).
- The one rejected design is recorded in the parent `idea.md`: reference parts inside `Course.items`. Reason: about 160 call sites walk `Course.items` and would count them in completion, `progress_percentage`, `lesson_count`, position/gating and due dates. This spec's settled "not a row in `get_course_index`" repeats the same reasoning for the sidebar (`research_learner_player.md` section 1: `next_entry`/`previous_entry` walk the rows positionally and would take a reference row as a neighbour).

### 1.2 The built predecessor: `reference-material-content-1-authoring`

Folder `spec_dd/3. done/2026-11-22_16:35_reference-material-content-1-authoring/`. QA (`qa_report.md`, `3. frontend_qa.md`): 0 bugs, admin-only UI, so it says nothing about player behaviour. What it hands this spec:

- `CourseReferencePart` model, loader and demo course (parts "Airspace Rules" with Airspace Classes and No-fly Zones, and "Glossary", per QA tests 1 and 4.2). Reference parts are not in collection items.
- Loader never deletes a reference part's topic rows, and `content_save` is additive except the deliberate delete of a part placement moved from `children:` to `reference:` (`upgrade_notes.md`). So a reader may meet a part that was a placement before, with a left-behind `ContentCollectionItem` row for the part's own topics (`research_prior_art.md` of spec 1, section 3).
- Validation rules (topics only, no due keys, part inside the loaded source path): the listing can assume every reference part holds topics only, but a part can have zero topics (hence the empty-state answer).
- A directory named `reference` beside a `course.md` is no longer auto-discovered into the learning path (breaking change in `upgrade_notes.md`).
- Lesson from spec 1's own research (`research_prior_art.md` section 4): earlier specs avoided automatic deletes of collection items; `TopicProgress.collection_item` and related FKs are `SET_NULL` (`better-course-progress-tracking/decision.md`), so a stale placement never blocks reading but progress rows can outlive it.

### 1.3 Closest earlier work: previews that write no progress

`spec_dd/3. done/2026-11-12_11:54_educator-interface-course-content-preview/` (spec lines 7, 13, 37, 40). Its brief states the same hazard this spec has: "the learner pages write progress the moment anyone opens them". Its solution was a separate read-only rendering (a modal fragment) that does not call the learner views, with no learner records created; it omitted the learner "Course content" outline because that outline is "built from learner progress". Its `research_prior_art.md` records the three failure modes of other LMS previews (Canvas Student View leaves Test Student data, Moodle role switch writes records and looks subtly different, Open edX preview vs live drift) and concludes: render directly, create no learner, progress or registration rows.
Lessons that apply here: do not route through `view_course_item`/`view_topic`; the downstream bug that the accordion re-sanitises nested component output (`spec_dd/2. in progress/downstream_bugs_oct_29/accordion-strips-nested-component-attributes/idea.md`) affects any topic rendered with `rendered_content()`, reference topics included; `content-link` renders no URL today (`research_learner_player.md` section 2), so cross-links in reference topics will not link.

### 1.4 Player history relevant to chrome and routes

- `spec_dd/3. done/2026-05-07_22:31_bug-course-part-navigation/` (`research.md`): the flat index once included `CoursePart` rows, giving a dead "Previous" that redirected forward; fixed by skipping `CoursePart` in prev/next (option 1) rather than changing index semantics (option 2, "not recommended for a bugfix" as it changes URLs). Today `<int:index>` is the position in `viewable_collection_items()` with parts dropped. Lesson: previous/next logic assuming a flat list breaks when a non-leaf row is in it; this is the same argument for keeping the Reference entry out of the outline list. Also: reference-part next/previous must be written fresh (within a part's topics, none at the ends) and tested for the first and last topic edge cases, the bug class seen here.
- `spec_dd/3. done/2026-06-03_15:19_student-interface-course-player/` (`research_mobile_bottom_sheet_nav.md`, `1. spec.md`, `3. frontend_qa.md`): the mobile outline is a modal bottom sheet needing an explicit close control, scrim dismiss, Escape, and `overscroll-behavior: contain`; most-used items should sit slightly above the bottom edge. Answer "right under the course table of contents" must live inside the sheet's scroll area and keep a thumb-reachable target.
- `spec_dd/3. done/2026-11-15_13:44_deadlines-3-extensions-and-pause/` (`2. plan.md` line 25, `research_codebase.md` lines 186-198): the player's paused/ended gate is `_course_access_redirect` plus `PlayerRoute` (ITEM, FORM_RESULTS, SUBMIT_AND_EXIT, FINISH). Earlier QA hardened the ended path so only listed routes pass. Reference routes have no `PlayerRoute` member, so the settled "paused and ended learners cannot read" falls out of the existing gate with no new rule; a new member would be needed only if that decision changes.
- Earlier OOB swaps in FLS: educator-interface-better-nav (`spec_dd/3. done/2026-04-24_09:16_educator-interface-better-nav/1. spec.md`) uses `hx-swap-oob` fragments for breadcrumbs and sidebar `aria-current`; `toasts-bottom-viewport` appends OOB fragments to HTMX responses. Learner player uses `#course-toc-region` as the OOB target for Previous/Next (`research_learner_player.md`). Reference pages that are not boosted-swap targets of Previous/Next must still render a Reference entry on direct load and not leave a stale outline highlight (no row `is_current`).
- Bug found while researching: `spec_dd/2. in progress/` and `downstream_bugs_oct_29` hold `course-detail-continue-restarts-at-item-one` (`_detail_start_url` returns item 1 for all registered learners). It is on `course_detail`, the page this spec also edits; it is a reminder that detail-page start URLs and reference links are separate concerns.

### 1.5 Facts that shape risk

- `course_detail` is public. "Course content" renders even for an empty course (`research_learner_player.md` section 1), so a reference section needs its own guard, as the idea says.
- Library-only course failures (404 at `course_home`, `course_finish` completing an empty course) belong to spec 4, not this one. Spec 2 only needs the Reference entry on pages that extend `_course_base.html`.
- No earlier spec tested a player-chrome change on the finish page or closed-item page together; the idea says the entry appears on those, so verify it there.

## 2. Elsewhere (web, thin coverage)

Two searches; sources are forums and university help pages, not vendor docs.

- Canvas: a community thread on large amounts of supplemental or reference material reports a workaround of keeping reference libraries as a separate self-enrolled course that other courses link to, so content is updated once. Pattern seen: no first-class "reference" area beside modules. https://community.canvaslms.com/thread/40389
- Canvas Files: students normally reach files only through modules or pages; the Files link is often hidden by institutions, and module publish state overrides item state, so a "published" file can be unreachable. A known Melbourne issue let students navigate to items in modules they should not reach. Lesson: reachability and access gating must be one decision, as this spec's reuse of `raise_404_if_unavailable` plus `can_access_content` does. https://sites.gatech.edu/dlt-blog/2025/06/13/hide-your-canvas-files ; https://lms.unimelb.edu.au/updates/known-issues/canvas-lms/known-issue-students-can-navigate-to-items-in-modules-they-are-not-assigned-to ; https://answers.illinois.edu/129501
- Articulate Rise: users ask for a resources area apart from tracked lessons, because a "Resources" lesson inside tracking blocks completion at 100% when learners never open it; another thread asks how to keep a glossary or references block always accessible in a restricted course, with no clear answer. Lesson: untracked and outside the completion count, as FLS settled. https://community.articulate.com/discussions/rise-360/always-allow-access-to-one-section-in-restricted-rise-course ; https://community.articulate.com/discussions/discuss/rise-resource-page/431346/replies/431354
- Moodle completion and progress-percentage complaints (optional activities counting) are cited in `spec_dd/3. done/2026-11-22_16:35_reference-material-content-1-authoring/research_prior_art.md` section 5 (docs.moodle.org/503/en/Course_completion_tracking, tracker-old.moodle.org/browse/MDL-67750); they support keeping reference out of `Course.items`.
- Preview-style failure modes (Canvas Student View data pollution, Moodle role switch, Open edX preview vs live) are in the educator preview spec's `research_prior_art.md` (written from background knowledge, URLs not verified there).

## 3. Takeaways for the spec

1. No earlier player route outside the index scheme exists; this is new ground, so copy the pattern of the educator preview (render directly, write nothing) rather than reuse `view_course_item`/`view_topic`.
2. Keep the Reference entry out of the outline rows (prev/next bug history and `next_entry` neighbour risk).
3. First and last topic of a reference part need next/previous edge-case tests (bug-course-part-navigation precedent).
4. Test the entry on topic, form, closed-item and finish pages, and after an HTMX OOB Previous/Next swap.
5. Paused and ended denial needs no new rule; add a test that asserts it.
6. Mobile bottom-sheet needs the entry inside the scroll area, close control intact.

status: ok
