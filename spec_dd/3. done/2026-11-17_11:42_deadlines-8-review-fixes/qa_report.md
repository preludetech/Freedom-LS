# Frontend QA report: deadlines-8-review-fixes

## Methodology

- Playwright MCP at 1920x1080 (desktop), plus short mobile (375x812) and tablet (768x1024) passes.
- Browser time zone set to Africa/Johannesburg, locale en-US.
- Screenshots were collected into `screenshots/` beside this report.
- Section 4 of the plan (validators) was run in the terminal, not the browser.

## Diff scoping

Class: FULL. The diff touches these files:

- `claude_plugins/fls-content/validate/validate.py`
- `freedom_ls/content_engine/management/commands/content_save.py`
- `freedom_ls/content_engine/moved_children.py`
- `freedom_ls/content_engine/signals.py`
- `freedom_ls/content_engine/validate.py`
- `freedom_ls/deadlines/admin.py`
- `freedom_ls/deadlines/resolver.py`
- `freedom_ls/deadlines/signals.py`
- tests
- the QA plan `3. frontend_qa.md`

All the code is `.py`, so the plan expected BACKEND_ONLY. The diff also includes the QA plan `.md`, which fired Rule 4 and made the class FULL.

Run: every section of the plan on desktop. Mobile and tablet were kept short: the player outline and the admin record page. Nothing was skipped.

## Smoke gate

Status: pass. Pages checked: `/` and `/admin/freedom_ls_learner_progress/courseprogress/96380511-3da1-4860-91a5-90c5c1ea0ba8/change/`. No failure URL or reason.

## Results by test

| Test | Viewport | Result | Note |
|---|---|---|---|
| 1.1 | desktop | pass | Placement course: Key Ideas "Deadline 20 Nov 2026, 23:59" (Reg+3, end of day). No line on Going Deeper, Knowledge Check or the part row. Dates render as "20 Nov 2026, 23:59" (24h, day-first), not the plan's en-US form; no template changed on this branch. [shot](screenshots/page-2026-11-17T04-27-00-193Z.png) |
| 1.2 | desktop | pass | Parts course: Welcome missed 31 Jan 2024; Key Ideas 1 Dec 17:00 (Reg+14); Going Deeper none; Knowledge Check 8 Dec (Reg+21). What to Expect reads "Today, 23:59", not Reg+7, because `qa_create_deadlines_seed_extras` gives the fresh learner a fixed override on it. The plan missed this. [shot](screenshots/page-2026-11-17T04-27-20-139Z.png) |
| 1.3 | desktop | pass | Dashboard shows "Missed deadline Welcome 31 Jan 2024" and "Deadline Key Ideas 20 Nov" (plus the extras' long-title course). No forbidden wording. [shot](screenshots/page-2026-11-17T04-27-28-073Z.png) |
| 1.4 | desktop | pass | Extended learner's record: Key Ideas 5 Dec 2026, 17:00 SAST (+14 days); course time limit end 7 Feb 2027 (+2 days). Learner outline shows Key Ideas "Deadline 5 Dec, 17:00", which matches. [record](screenshots/page-2026-11-17T04-27-53-811Z.png), [outline](screenshots/page-2026-11-17T04-28-06-446Z.png) |
| 2.1 | desktop | pass | Key Ideas: Content default "3 days after registration", Effective "10 days after registration", no note. Knowledge Check: Content default "No deadline", Effective "5 days after registration". Outline shows Key Ideas 27 Nov, Knowledge Check 22 Nov. [admin](screenshots/page-2026-11-17T04-28-45-740Z.png), [outline](screenshots/page-2026-11-17T04-29-00-082Z.png) |
| 2.2 | desktop | pass | Cohort Key Ideas: Content default "14 days after registration at 17:00", Effective "20 days after registration", no note. Course time limit: default "90 days after registration", Effective "120 days". [shot](screenshots/page-2026-11-17T04-29-31-475Z.png) |
| 2.3 | desktop | pass | Add page loads (200); the new row's picker offers only "Course time limit". Saved a cohort and placement course with a 30-day time-limit row: Effective "30 days after registration", Content default "-", no note. The column returns the string "None" (checked in the shell and in a real request); Unfold renders the string "None" as "-", as on main. The picker then lists Course time limit, Key Ideas, Going Deeper, Knowledge Check. Step 6: the admin delete is refused ("would require deleting protected related objects") because saving the registration created a CourseProgress for qa_deadline_cohort@email.com (3f9f9a90), which PROTECTs it. The residue went to the data helper in section 5. [add page](screenshots/page-2026-11-17T04-29-45-444Z.png), [after save](screenshots/page-2026-11-17T04-31-17-083Z.png) |
| 2.4 | desktop | pass | After changing placement Key Ideas 3 to 4 and running content_save: "Default has changed since this override was set (was relative:3, now relative:4)", Content default "4 days after registration". Knowledge Check row has no note. After git checkout and content_save the note is gone and the default reads "3 days after registration". [shot](screenshots/page-2026-11-17T04-32-15-798Z.png) |
| 2.5 | desktop | pass | Extend form loads for the fresh learner's parts-course record. Target kinds: One item, Course time limit, Whole course. The item list includes What to Expect, Key Ideas, Knowledge Check and the undated items. Not submitted. [shot](screenshots/page-2026-11-17T04-32-37-206Z.png) |
| 3.1 | desktop | pass | Load accepted the direct second placement. Outline: Getting Started (Welcome missed, What to Expect 24 Nov = Reg+7), Core Concepts (Key Ideas 27 Nov, Knowledge Check 22 Nov), top-level What to Expect 26 Nov (Reg+9). The override on top-level What to Expect (15 days) shows Content default "9 days after registration". Content admin: Core Concepts row lists Key Ideas 3 days and Knowledge Check with no due date; the Getting Started row's inline is empty. The picker problem is reported as fail below (B3). [outline](screenshots/page-2026-11-17T04-33-04-655Z.png), [content admin](screenshots/page-2026-11-17T04-33-53-904Z.png) |
| 3.2 | desktop | pass | The plan's subdirectory load fails on the category lookup ("Unknown category ... reference-demo; Categories declared in this repo: none"); this is not branch code. Workaround: a parts-only root `.sdd-work/qa_parts_only` with `course_categories.yaml` and a copy of the moved parts course; the load saved. Getting Started row lists Key Ideas 3 days; Core Concepts row lists only Knowledge Check. The fresh learner's 10-day override moved to the Getting Started Key Ideas (07d5a474), default "3 days", no note. Outline: Getting Started > Key Ideas 27 Nov (Reg+10); Core Concepts still lists Key Ideas "1 Dec, 17:00" from the left-behind row (existing behaviour per the plan). The cohort 20-day override moved to 07d5a474 (default "14 days after registration at 17:00"). Extended learner: Key Ideas 5 Dec 17:00 (+14 days), plus the left-behind Key Ideas at 23 Nov (+2 days). Deadline extensions list both Key Ideas extensions against "Getting Started - Key Ideas (order=2)". [content admin](screenshots/page-2026-11-17T04-34-35-805Z.png), [record](screenshots/page-2026-11-17T04-34-49-778Z.png), [outline](screenshots/page-2026-11-17T04-34-55-966Z.png), [extensions](screenshots/page-2026-11-17T04-35-19-765Z.png) |
| 3.3 | desktop | pass | Moved back (git mv, same parts-only reload). Core Concepts row lists Key Ideas 3 days and Knowledge Check; Getting Started row empty. The fresh learner's 10-day override, the cohort 20-day override and both Key Ideas extensions sit on the Core Concepts Key Ideas (bb8a51a7); extended learner Key Ideas 5 Dec 17:00 (+14). Outline: Core Concepts > Key Ideas 27 Nov. Getting Started lists the left-behind Key Ideas "1 Dec, 17:00" (existing behaviour, removed in section 5). [record](screenshots/page-2026-11-17T04-35-56-917Z.png), [outline](screenshots/page-2026-11-17T04-36-03-315Z.png) |
| 3.4 | desktop | pass | After both parts-only loads the 15-day override stayed on the top-level What to Expect (b765c38e), default "9 days after registration". Learner: top-level What to Expect "Deadline 2 Dec" (Reg+15); Getting Started > What to Expect "Deadline 24 Nov" (Reg+7). A row outside the load was not taken as left behind. [shot](screenshots/page-2026-11-17T04-36-03-315Z.png) |
| 3.3 | mobile | pass | 375x812: page fits (scrollWidth 375). "Open course outline" opens the bottom sheet; every item and date readable. The collapsed DjDT tab overlaps the right edge of body text (dev tooling). [closed](screenshots/page-2026-11-17T04-36-19-014Z.png), [sheet open](screenshots/page-2026-11-17T04-36-34-991Z.png) |
| 3.3 | tablet | pass | 768x1024: outline is behind the "Open course outline" button as on mobile; header and content share a left edge; no overflow. [shot](screenshots/page-2026-11-17T04-36-52-176Z.png) |
| 4.0 | terminal | pass | Setup as written gives no verdict: the scratch copy (course dir only) fails content_validate on "Unknown category reference-demo", and the bundled validator needs `.fls-content.yaml` in the working directory. Workaround: scratch root `.sdd-work/qa_review_fixes_bad` with `course_categories.yaml`, a minimal `.fls-content.yaml` (access_types free, application_gated) and the course copy; the bundled validator ran with that root as cwd (`uv run --directory`). Unmodified copy: both exit 0. |
| 4.1 | terminal | pass | Both exit 1: "Invalid children list", field `children[2]`, "this child is named twice", "Name each child once." `children[0]` not named. |
| 4.2 | terminal | pass | The plan's input fails earlier in both validators: `children -> 0 -> children -> 1` and `-> 2` "set a due key or no_due_date; an entry without either does nothing", so the named-twice check never runs. With `no_due_date: true` on the two repeats both exit 1, naming `children[0].children[1]` and `children[0].children[2]` ("this child is named twice" / "Name each child once."); `children[0].children[0]` not named. Header reads "Invalid due date placement" (top-level repeats read "Invalid children list"), as on main. The summary count is reported as fail below (B2). |
| 4.3 | terminal | pass | Both exit 1 naming `children[0].children[0]`, given "99. missing/content.md", "the part has no child at this path", and the part's children "01. welcome/content.md, 02. what-to-expect/content.md". |
| 4.4 | terminal | pass | Valid file: both exit 0. |
| 4.5 | terminal | pass | `content_validate demo_content` exits 0. The bundled validator from the repo root exits 1 only because there is no `.fls-content.yaml` there; with a cwd holding a minimal one it exits 0 ("Validation passed"). |
| 5 | desktop | pass | git restore of `demo_content/`: key-ideas back under 02. Core Concepts; content_save; the data helper deleted the QA rows and left-behind items. Outline matches 1.1: only Core Concepts, Key Ideas "Deadline 20 Nov" (Reg+3). The full reload included the placement course, which no longer named its top-level What to Expect, so that row counted as left behind and the "QA second placement" override followed the child to Getting Started > What to Expect before cleanup deleted it. This is the designed moved-children behaviour for a collection the load saved. [shot](screenshots/page-2026-11-17T04-41-06-515Z.png) |
| 0.3 | terminal | fail | Content reset (`danger_content_delete --yes`) left a CoursePart behind (B1). A leftover example.com CoursePart "Core Concepts" (d3053e39) then blocked `content_save demo_content DemoDev` with a primary-key IntegrityError until deleted by hand. |
| 4.2 | terminal | fail | Both validators print "Validation failed for 2 file(s)" when one file has two errors (B2). |
| 3.1 | desktop | fail | The override item picker labels both placements of What to Expect identically (B3). |

## Design check

No design states tested.

## B1: Content reset leaves CourseParts behind

Manifestations: test 0.3 (terminal).

- Expected: `danger_content_delete --yes` removes all content, CourseParts included, so a following `content_save` loads cleanly.
- Actual: CoursePart is missing from the command's model list. A leftover CoursePart survives and makes `content_save` fail with a duplicate primary key.

## B2: Validator header counts errors as files

Manifestations: test 4.2 (terminal), in `content_validate` and the bundled fls-content validator.

- Expected: "Validation failed for 1 file(s)" when the errors are all in one file.
- Actual: "Validation failed for 2 file(s)" for one file with two errors. `failed_files` gets one entry per error and the header counts entries as files.

## B3: Override picker cannot tell two placements of one child apart

Manifestations: test 3.1 (desktop).

- Expected: each picker entry identifies its placement (which part, or the course itself).
- Actual: both What to Expect entries show the same label, "What to Expect (functionality_demo_course_parts/01. Getting Started/02. what-to-expect/content.md)" (title plus file path). A staff user cannot tell the Getting Started placement from the top-level one.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| smoke | desktop | `/admin/freedom_ls_learner_progress/courseprogress/96380511.../change/` | [shot](screenshots/page-2026-11-17T04-26-14-305Z.png) | clean |
| smoke | desktop | `/admin/freedom_ls_learner_progress/courseprogress/96380511.../change/` | [shot](screenshots/page-2026-11-17T04-26-32-763Z.png) | clean |
| 1.1 | desktop | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-27-00-193Z.png) | clean |
| 1.2 | desktop | `/courses/functionality-demo-course-parts/1/` | [shot](screenshots/page-2026-11-17T04-27-20-139Z.png) | clean |
| 1.3 | desktop | `/` | [shot](screenshots/page-2026-11-17T04-27-28-073Z.png) | clean |
| 1.4 | desktop | `/admin/.../courseprogress/f487d0b1.../change/` | [shot](screenshots/page-2026-11-17T04-27-53-811Z.png) | clean |
| 1.4 | desktop | `/courses/functionality-demo-course-parts/1/` | [shot](screenshots/page-2026-11-17T04-28-06-446Z.png) | clean |
| 2.1 | desktop | `/admin/.../courseprogress/96380511.../change/` | [shot](screenshots/page-2026-11-17T04-28-45-740Z.png) | clean |
| 2.1 | desktop | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-29-00-082Z.png) | clean |
| 2.2 | desktop | `/admin/.../cohortcourseregistration/99cac1a0.../change/` | [shot](screenshots/page-2026-11-17T04-29-31-475Z.png) | clean |
| 2.3 | desktop | `/admin/freedom_ls_learner_management/cohortcourseregistration/add/` | [shot](screenshots/page-2026-11-17T04-29-45-444Z.png) | clean |
| 2.3 | desktop | `/admin/.../cohortcourseregistration/9eefd7d4.../change/` | [shot](screenshots/page-2026-11-17T04-31-17-083Z.png) | clean |
| 2.4 | desktop | `/admin/.../courseprogress/96380511.../change/` | [shot](screenshots/page-2026-11-17T04-32-15-798Z.png) | clean |
| 2.5 | desktop | `/admin/.../courseprogress/ea94704c.../extend/` | [shot](screenshots/page-2026-11-17T04-32-37-206Z.png) | clean |
| 3.1 | desktop | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-33-04-655Z.png) | clean |
| 3.1 | desktop | `/admin/freedom_ls_content_engine/contentcollectionitem/55bf9c64.../change/` | [shot](screenshots/page-2026-11-17T04-33-53-904Z.png) | clean |
| 3.2 | desktop | `/admin/freedom_ls_content_engine/contentcollectionitem/07645634.../change/` | [shot](screenshots/page-2026-11-17T04-34-35-805Z.png) | clean |
| 3.2 | desktop | `/admin/.../courseprogress/96380511.../change/` | [shot](screenshots/page-2026-11-17T04-34-49-778Z.png) | clean |
| 3.2 | desktop | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-34-55-966Z.png) | clean |
| 3.2 | desktop | `/admin/freedom_ls_deadlines/deadlineextension/` | [shot](screenshots/page-2026-11-17T04-35-19-765Z.png) | clean |
| 3.3 | desktop | `/admin/.../courseprogress/96380511.../change/` | [shot](screenshots/page-2026-11-17T04-35-56-917Z.png) | clean |
| 3.3 | desktop | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-36-03-315Z.png) | clean |
| 3.3 | mobile | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-36-19-014Z.png) | clean |
| 3.3 | mobile | `/courses/functionality-demo-per-placement-due-dates/1/` (outline sheet open) | [shot](screenshots/page-2026-11-17T04-36-34-991Z.png) | flags: stacked: sidebar ink spans x=0..375, more than half of the 375px viewport; overlap: header and sidebar ink intersect; overlap: content and sidebar ink intersect |
| 3.3 | tablet | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-36-52-176Z.png) | clean |
| 5 | desktop | `/courses/functionality-demo-per-placement-due-dates/1/` | [shot](screenshots/page-2026-11-17T04-41-06-515Z.png) | clean |

Note on the mobile open-sheet row: this was measured with the outline bottom sheet deliberately open. A modal sheet covering the page is its intended look, and the closed-state probe on the same page is clean. It is not grouped as a bug.

## Data changes

| Via | What |
|---|---|
| `sdd:qa-data-helper` | `create_demo_data --yes`: created sites Demo, DemoDev, Bloom, Prelude, Wrend and their users (the branch DB had only example.com). |
| Targeted shell delete, approved by the user (the helper's own delete was refused by the permission check) | Deleted two leftover example.com Topic rows (bc4c9f84..., 1fd4eae7...) whose ids clashed with demo_content. |
| Content reset (`danger_content_delete --yes`), approved by the user | Cleared leftover example.com content that blocked `content_save`. |
| Targeted shell delete, approved by the user (the helper's own delete was refused) | Deleted leftover example.com CoursePart d3053e39, which the content reset does not cover (see B1). |
| `sdd:qa-data-helper` | Created qa_deadline_fresh@email.com individual registration and CourseProgress 96380511 on the placement course, 2026-11-17; override checks empty. |
| `sdd:qa-data-helper` | Deleted the QA override rows (3 learner, 3 cohort), the QA cohort registration 9eefd7d4 with the CourseProgress 3f9f9a90 it created, and the left-behind collection items 07645634, b765c38e, 07d5a474. |

## Bug status

- **FIXED** (commit: 39534064a) — B1: Content reset leaves CourseParts behind
- **FIXED** (commit: ee840f5eb) — B2: Validator header counts errors as files. Decision: the header counts problems ("Validation failed: N problem(s)"), since cross-file errors are filed under the scanned root and a file count would be wrong
- **FIXED** (commit: f2afbc5a1) — B3: Override picker cannot tell two placements of one child apart. Decision: an item in a part reads "Part › Title"; one placed on the course reads its title; no file path
- **FIXED** (commit: f2afbc5a1) — `test_signal_names_the_children_a_load_moved` failed. Decision: keep the rule that only rows in the load's own collections count as left behind; the test now reloads the whole course. Full suite: 15053 passed

## General notes

Plan corrections the run found:

- 1.2: What to Expect does not read Reg+7. The extras seed (`qa_create_deadlines_seed_extras`) gives the fresh learner a fixed override due today 23:59 on it.
- 2.3: the plan expects "None", but Unfold renders the string "None" as "-".
- 2.3 step 6: the delete is blocked by a PROTECTing CourseProgress that the save itself creates.
- 3.2: the subdirectory load fails on the category lookup. The workaround was a parts-only root (`.sdd-work/qa_parts_only`).
- Section 4: setup needs `course_categories.yaml` and a `.fls-content.yaml`. 4.2's input needs due keys on the repeats.

Other observations:

- Dates render as "20 Nov 2026, 23:59", not the plan's en-US form. No template was changed on this branch.
- The admin override inline is cramped: values wrap mid-word.
- Nested repeat errors are headed "Invalid due date placement"; top-level ones are headed "Invalid children list". This is as on main.
- The section 5 full reload moved the second-placement override. This is designed behaviour.
- The scratch dirs `.sdd-work/qa_review_fixes_bad`, `.sdd-work/qa_parts_only` and `.sdd-work/qa_cfg` were left in the gitignored `.sdd-work` because the delete script refuses directories.
- The data helper edited a tracked agent-memory file; the edit was reverted.

status: ok · reason: 3 bugs — 1 fixed, 2 unresolved; a branch signal test fails; report rendered, screenshots verified
