# Research: prior art for retiring removed content

Scope: earlier attempts in `spec_dd/` (read from files; git history not available) and soft-delete experience elsewhere. Labels: (a) read in a file or source, (b) search snippet only, (c) my inference. Paths are relative to the repo root; `spec_dd/1. next/sacaa-compliance-content-versions-and-access/` is written `<sacaa>/` below.

## Here

### 1. Nobody has built retirement for content before
- (a) No spec in `spec_dd/0. paused`, `1. next`, `2. in progress` or `3. done` built a content prune, hide or retire. `<sacaa>/research_content_save_pipeline.md` (sections 1, 3, 5) confirms: nothing is removed for a deleted Topic, Activity, Article, Course, CoursePart, Form, FormPage, FormContent, FormQuestion, QuestionOption, CourseCategory or File. `ContentCollectionItem` is never deleted (`moved_children.py` docstring: "A sync never removes the row a moved child left behind"). `_resolve_condition` already notes "questions dropped from the YAML ... leave stale rows".
- (a) No content or form model has `is_active`, `archived`, `retired` or a version field. Only `Course.visibility` and `Article.visibility`.
- (a) `<sacaa>/research_question_versioning_prior_art.md` section 3: every surveyed LMS import (Moodle GIFT/XML, Open edX library import) is additive; none prunes. Full sync per site with retire-not-delete is stricter than anything surveyed, so the match key, absence rule and un-retire are ours to design.

### 2. `danger_content_delete`
- (a) It is the only thing that deletes content (`freedom_ls/dev_tools/management/commands/danger_content_delete.py`, per the pipeline research). Learner rows reference content with PROTECT, so a delete against a site with learner data is refused by the database. Evidence of the same refusal in the UI: `spec_dd/3. done/2026-09-10_09:45_simple-application-forms/screenshots/admin-formprogress-delete-refused.png`. Lesson: PROTECT has already been the de facto guard; retirement avoids ever hitting it.

### 3. `content_snapshots` (paused)
- (a) `spec_dd/0. paused/content_snapshots/0. idea.md`: immutable point-in-time snapshots, default "never prune", no consumer yet, not built. Its snapshot of referenced `File` rows implies files may be "renamed, replaced, or deleted" later. It does not address what the live tables serve. `spec_dd/1. next/learner-interface-features-2-test-out/idea.md` (lines 43, 53) states nothing may assume it exists.
- (a) `<sacaa>/research_question_versioning_prior_art.md` ("Patterns worth rejecting" 5): surveyed systems reach question-level audit with per-question version rows, not whole-course snapshots. Snapshots are not a prior attempt at retirement.

### 4. The `is_active` "retired" pattern (JobTitle, Department, Location)
- (a) Glossary `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` ("Words with an existing meaning"): "retired" means a list entry with `is_active=False`, hidden from pickers, never deleted. Context in `spec_dd/1. next/corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`. This is the closest in-house precedent: hide from selection, keep because rows reference it. Differences: those are admin-edited flags on three models, filtered at the picker only; here the state is set by a sync, on twelve models, and must be applied to every read path. Also the glossary says content models have no `is_active`, and "setting to False is deactivating", so a content `is_active` would clash with the glossary; the answers chose `retired_at` instead.

### 5. `Course.visibility`: the working model of filtering content out of reads
- (a) `spec_dd/3. done/2026-07-11_16:24_override_course_access_and_details_page/research_visibility_and_access_system.md`: visibility is set from YAML, readonly in admin (`content_engine/admin.py`), and enforced at two chokepoints: `VisibilityEnforcingBackend.filter_visible()` (queryset level, used by `all_courses`, the dashboard "discover" list and recommendations) and `raise_404_if_hidden_unregistered()` (single-course views). Its docstring says it exists so views "cannot drift". `get_all_courses()` does no filtering; all filtering is applied afterwards via the backend.
- (a) Visibility has a HIDDEN value (the idea lists only published and coming soon; the code has `HIDDEN` too, `courses.py`). HIDDEN never disrupts a registered learner. That is the opposite of the retired rule ("served to no one, existing learners included"), so HIDDEN cannot be reused and the retired check must sit before any registration bypass in `get_access`/`filter_visible`.
- (a) Lesson: course-level filtering is centralised and works. Below the course (topics, pages, questions, options) there is no equivalent chokepoint: `<sacaa>/research_question_version_seams.md` shows the reads go through relations (`related_name="options"`, `"questions"`, `FormPage.children()`, `compute_path()`, `served_path()`, `build_served_paper()`, `count_form_questions()`, `form_questions()`, `page_questions()`, `load_quiz_questions()`, `question_number()`).
- (a) `spec_dd/3. done/2026-07-03_07:52_courses_coming_soon/research_visibility_states.md` records the original design of the visibility states.

### 6. Earlier analysis of the retired-state design
- (a) `<sacaa>/../sacaa-compliance-content-versions-and-access-3-question-versions/research_question_version_seams.md` (path: `spec_dd/1. next/sacaa-compliance-content-versions-and-access-3-question-versions/`), options (a) and (b):
  - (a) retired flag on the live `FormQuestion`: undisturbed `condition_option`, `FormQuestionTopic`, shuffle groups, pools and PROTECT. Serving filters on the flag in `build_served_paper()` and `compute_path()`.
  - (b) new row per revision with the old one retired: an `order` collision on a page, copies of section rows, and `condition_option` (RESTRICT) repointing.
  - It warns that a default manager filter would hide retired rows from audit readers too, so an explicit filter is safer. This bears directly on the design choice below.
- (a) The served paper (`form_engine/served_paper.py`) stores ids only and rebuilds with `served_path()`, which treats a missing served item as skipped (`has_missing_served_items`). If retired rows are excluded from live lookups inside `served_path()`, a pinned in-progress attempt silently loses the retired question, which breaks "Attempts pin at start". The pinned lookup must bypass the retired filter. (c)
- (a) `build_served_paper()` reads `page.children()` and `child.options.all()` live, so it serves retired rows today.

## Elsewhere

### 7. Retirement in assessment and LMS products
(From `<sacaa>/research_question_versioning_prior_art.md`, section 2; sources cited there.)
- Moodle: deleting a question that a quiz uses only hides it; "show old questions" reveals them. https://docs.moodle.org/405/en/Question_bank
- Questionmark: retired items stay in the bank for defending past tests (vendor claim). https://www.questionmark.com/platform/flexible-authoring/
- Canvas New Quizzes: old version remains only in quizzes already taken. https://kb.wisc.edu/luwmad/page.php?id=153005
- Open edX: no retirement concept found; library import is additive, no deletion. https://openedx.atlassian.net/wiki/spaces/COMM/pages/3966795804
- Blackboard random blocks: linked questions, removal from pool is the exclusion mechanism, so edits leak into served content. https://help.blackboard.com/Learn/Instructor/Original/Tests_Pools_Surveys/Reuse_Questions/Random_Block
- Staff display (c): status badge plus a "show retired" toggle; Moodle is the precedent. Matches the answers (retired stays visible to educators, marked).
- Moodle in-progress attempts stay on the version they started (forum summary https://moodle.org/mod/forum/discuss.php?d=453360); same as "Attempts pin at start".

### 8. Soft delete in Django: the reported problems
Source for all of this: one search pass, snippets only (b); I did not open the pages.
- Unique constraints: plain `unique=True` or `unique_together` still counts soft-deleted rows, so a deleted value blocks reuse. Fix suggested in django-safedelete docs: a conditional `UniqueConstraint` limited to live rows. https://django-safedelete.readthedocs.io/en/1.3.0/managers.html , https://pypi.org/project/django-safedelete/1.2.0
  - FLS relevance (c): retire here keeps the same uuid and the same slug, and un-retire revives the same row, so the clash is mostly avoided. It reappears if an author reuses a slug or path under a new uuid. Candidates: `Course` `unique_together ["site","slug"]`, `Form` unique, `File` `(site, file_path)`. The spec should say whether a new-uuid row colliding with a retired row fails the save or retires/replaces the old one.
- Related manager leaks: related managers use the model's default manager and have no access to an alternate "all rows" manager, so filtering via a custom default manager both hides deleted rows from audit reads and still leaks when code uses a different manager. django-safedelete adds `all_with_deleted()` for this. https://django-safedelete.readthedocs.io/en/1.3.0/managers.html ; Django ticket on related managers and M2M https://code.djangoproject.com/ticket/17746 ; forum https://forum.djangoproject.com/t/manyrelatedmanager-inconsistent-with-relatedmanager/10089
  - FLS relevance (c): `QuestionAnswer.selected_options` is an M2M to `QuestionOption`; audit reads must still see a retired option. A default-manager filter would drop the chosen option from the audit record, the exact failure the idea warns about for deleted options. This supports the explicit-filter route (as the seams research concluded) over a default-manager filter.
- Admin: default admin hides soft-deleted objects when a filtering default manager is used; safedelete ships `SafeDeleteAdmin`. https://django-safedelete.readthedocs.io/en/1.3.0/managers.html . This is the "admin confusion" case; the answers already pick the opposite (changelists show retired with a filter and column), which needs the admin to use an unfiltered manager.
- Cascading and data integrity: critics say soft delete as a base-class pattern causes lasting integrity problems and admin disruption. https://lightrun.com/answers/jazzband-django-model-utils-softdelete-is-an-anti-pattern ; cascading soft deletes need manual propagation https://medium.com/button-blog/cascading-soft-deletion-in-django-a8dce06668c2 . FLS relevance (c): the idea retires each row only when its own uuid is absent; it does not cascade. A retired Form with live questions, or a live question under a retired FormPage, must be served as retired by the read side (parent retired implies child unreachable). The spec should state whether parent retirement is derived at read time or stamped on children.
- Admin delete page: Django ticket #27852 about the delete block page not listing all blockers (https://groups.google.com/g/django-updates/c/_W0JIxX2F1Y/m/jSV4rTt6AQAJ). Minor.

## Takeaways for the spec
1. No in-house prior attempt exists to build on; nearest are `JobTitle` "retired" (concept) and `Course.visibility` (centralised read filter).
2. Course-level read filtering has chokepoints; question, page and option reads do not. Listing every read path (see seams research list) is the main work and the main leak risk.
3. Use explicit filtering or a named queryset method, not a default-manager filter, so audit reads and `QuestionAnswer.selected_options` still see retired rows; the admin then needs no special manager.
4. The pinned served-paper lookup (`served_path()`) must bypass the retired filter.
5. Retired must be checked before the registered-learner bypass used by `VisibilityEnforcingBackend`.
6. Decide the uniqueness behaviour for a new uuid colliding with a retired row's slug or path, and whether parent retirement cascades at read time.

status: ok
