# Research: UX patterns for showing and handling retired content

Scope: educator/admin display of retired content that learner records still reference, learner experience of content disappearing, CLI sync reporting. Grounded in existing FLS patterns first; external pattern notes come from general LMS/CMS practice and the prior-art file the idea cites (Moodle hides, Questionmark retires), not fresh web fetches. No new URLs were fetched for this file.

## 1. Existing FLS patterns to reuse (paths)

- **Status badge component.** `freedom_ls/panel_framework/templates/cotton/panel-status-badge.html`. It takes `tone` (success | warning | error | info | muted) plus `label`, or a `badge` object (`StatusBadge(tone, label)`). It "owns no domain words: callers pass sentence case". It carries `forced-colors:border` for High Contrast. A retired mark is `StatusBadge("muted", "Retired")` (sentence case). It needs no new component.
- **Table badge column.** `freedom_ls/panel_framework/templates/cotton/data-table-cells/badge.html` renders a `BadgeColumn`'s badge callable, and a row with no badge shows nothing. So a Retired column or cell works with a callable that returns `None` for live rows.
- **Helper home.** `freedom_ls/educator_interface/panels/common/badges.py` holds `active_status_badge`, `inactive_badge` (returns `None` for the default state so only the exceptional state draws) and `learner_status_badge`. A `retired_badge(retired_at) -> StatusBadge | None` belongs beside them and follows the `inactive_badge` shape: nothing when live, a muted "Retired" when retired.
- **Page header rule.** `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` ("Page header", about line 228): the header `badge` slot "carries a state only when it differs from the default (Inactive, Pending)". A retired Course, Topic or Form page puts the Retired badge in that slot, and live pages show nothing.
- **Person badges rule.** The same skill (about line 274): badges go in the `badges` slot of `<c-panel-person-link>` / `<c-panel-avatar-chip>`, on their own line, never beside the component. Not directly about content, but it is the template for "badge on its own line under the title" in list rows. Check for a matching slot on any content-row component before inventing one.
- **Tooltip/date.** `<c-panel-date>` / `<c-panel-datetime>` exist in `freedom_ls/panel_framework/templates/cotton/` for rendering `retired_at`. A tooltip is not in the skill's text (the search for "tooltip" in the skills was not run). Prefer a visible date in the detail view over a hover-only date, because hover is unreachable on touch and by keyboard.
- **Glossary vocabulary clash.** `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` (about lines 225 to 253) defines **Inactive** for `is_active=False` rows, and already has "retired" for the hidden-but-kept `JobTitle`/`Department`/`Location` entries. The badge label must read **Retired**, never "Inactive", "Archived" or "Removed", to keep the three words apart as the idea requires. Tone `muted` is already used for Inactive, so Retired and Inactive look alike in tone. Option: use `warning` for Retired. That is a decision for the spec: a muted chip says "not in use, nothing wrong", and a warning chip says "look at this", which suits an answer given to a retired question in an audit view.
- **No existing content-level retired mark.** A grep of `educator-interface/SKILL.md` for "badge" found nothing. Educator content pages have no state badge today, so this spec sets the pattern.

## 2. Common patterns for retired content shown to educators/admins

These are general patterns across LMS and CMS products. Moodle hides questions and Questionmark retires them, per the prior-art file `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md`.

1. **Keep visible, mark, never hide.** Soft-deleted or archived items stay in the educator list with a chip. Hiding them breaks audit ("where did this answer go?"). This matches the answers file ("Retired content stays visible to educators, marked").
2. **Mark at every level that names the item.** The mark goes on the row in a list, the page header on the detail page, and the answer row in an attempt or report. It does not sit on a parent only. A course outline shows the chip on each retired Topic or Form row, plus a retired Course in the course list.
3. **Retired-by-ancestor.** A child under a retired parent is not itself flagged in the data but is not served. The educator view either marks the child "Retired" too (simple, says what the learner sees) or shows "Retired with Course" (more accurate). The idea says each model gets its own `retired_at`, and the sync retires each absent row. A parent's absence will normally take its children's files with it, so children are retired directly in the common case. The spec should say how an educator page treats a live row under a retired parent, which is rare.
4. **Filter, don't separate.** A changelist gets a three-state filter: All, Live, Retired. The default is All, so the audit view is complete. The default can be Live for authoring lists. Recommend All, because the answers say retired stays visible.
5. **Column, not just filter.** The Django admin changelist gets a `retired_at` column (shown as date, or blank when live) and a `SimpleListFilter` ("Retired: Yes / No"). Django's built-in `EmptyFieldListFilter` on a nullable `retired_at` gives "Empty / Not empty" with no custom code, but the labels are poor. A small `SimpleListFilter` with "Retired" and "Live" reads better.
6. **Date on detail, not hover.** "Retired on 12 Mar 2026" in the page header, or the definition list (`panel-definition-list`) on the detail tab. In tables the chip alone is enough, and the column can sort by date.
7. **Answers given to retired questions.** In the cohort report and attempt review, the question row carries the chip and the answer stays rendered in full, including selected options, even when the option is retired. A retired option still shows what the learner chose, which is why option retirement must never drop the record. Mark the retired option in the same way inside the attempt.
8. **Pinned paper note.** An attempt that finished on a paper containing a question retired after it started should not look like a defect. Same chip, no warning tone. The attempt's `max_score` is unchanged, so the totals must still add up on screen. Do not show strikethrough or greyed text that suggests the answer was discarded.
9. **Counts.** Where educators see progress totals, retired children are excluded from completion (answers file). Show a footnote or tooltip "Excludes N retired items" only where a number could surprise an educator (a learner at 100% whose recorded progress shows a retired item). Otherwise say nothing. A small, hidden-by-default explanation avoids clutter.
10. **Un-retire is silent.** The chip disappears. No history is shown, because the answers file says no per-row audit entry. Only the sync output counts it.

## 3. Learner experience of content disappearing

Common LMS patterns, and what the idea already fixes:

- **Course leaves the list.** The idea says a retired Course leaves the learner's course list and accepts no new registrations. Most LMSs do the same on archive. The learner keeps no way to reach the course, and progress is kept for audit. The risk is a learner who sees a course vanish with no explanation. Options: nothing (settled by the idea, simplest), or an empty-state/help line on the course list. Adding either is new functionality, so flag it as an open question for the spec. It is not recommended without being asked ("Don't build functionality that is not explicitly requested").
- **Direct link or bookmark to retired content.** A learner opening a URL to a retired Topic, Form or Course should get the same response as for a nonexistent row. The repo convention is `get_object_or_404`. A 404 page with no "this was retired" text is the safe choice, since it reveals nothing about content that is served to no one. A friendlier message ("This content is no longer available") is common in other LMSs but is a decision for the spec.
- **Resuming a retired Form.** The idea says an in-progress attempt on a retired Form cannot be resumed, and stays as recorded. The page the learner lands on from a bookmark or the course outline is therefore the same 404 or "no longer available" page. The progress row stays unchanged and is not marked complete or failed.
- **Retired question mid-attempt.** No learner-facing change. The paper is pinned at start, so the learner sees the same questions they started with. This is the main UX reason for pin-at-start: no question vanishes under the learner's hands.
- **Retired item in a course outline.** The item drops from the outline and the progress bar total. A learner who had finished 4 of 5 where the 5th is retired now shows 4 of 4 and completes. Check that `course-progress-bar.html` (`freedom_ls/learner_interface/templates/cotton/course-progress-bar.html`) and the outline's "next item" logic both skip retired children, or the bar and the next-item link will disagree.
- **Previous/next navigation.** `player-nav.html` and `player-footer.html` (`freedom_ls/learner_interface/templates/cotton/`) walk the outline, so they must skip retired items. A link to a retired neighbour is the commonest leak.

## 4. CLI sync reporting patterns

Existing pattern in `freedom_ls/content_engine/management/commands/content_save.py`:

- Line items are collected as `removal_lines` and printed only after the transaction commits (lines 1642 to 1649), so a rolled-back run reports no removal and no success. Retire/un-retire output should follow this: collect during the save, print after commit.
- A closing summary line already exists: `Images: N seen (a status, b status).` (lines 1651 to 1656), using `click.echo`. A matching line fits: `Retired: 3 (Topic 1, FormQuestion 2). Un-retired: 1 (Topic 1).`
- Common CLI practice (Terraform plan/apply, rsync, Django `migrate`): a one-line count per category, a per-item list only when it is short or when `--verbose` is set, and `0` counts still shown so the operator knows the check ran. Recommend a count line always, and per-item lines (`Retired Topic "<title>" (<path or uuid>)`) so the operator can catch a mistaken retire. A source path that was moved or mistyped is the main operator risk, and a mass retire is the failure mode to guard. Consider a loud line when a large share of a site's rows retire in one run. That guard is new functionality and is not asked for, so list it as an open question for the spec only.
- Counts by model type rather than a single total, because "retired 140 rows" hides that 130 are `QuestionOption`s of one question.
- `File` is reported by path, as it has no uuid.
- `ContentCollectionItem` is skipped, not retired, so it stays out of the counts.

## 5. Recommendations for the spec

1. Add `retired_badge(retired_at)` next to `inactive_badge` in `freedom_ls/educator_interface/panels/common/badges.py`, returning `StatusBadge(tone, "Retired")` or `None`. Pick the tone once (muted matches Inactive; warning stands out). Reuse `<c-panel-status-badge>`; add no new component.
2. Put it in the page header `badge` slot on detail pages, and in a badge column (`data-table-cells/badge.html`) on lists. Show "Retired on <date>" as a row in the definition list on detail pages.
3. Admin changelists: a `retired_at` column and a Live/Retired `SimpleListFilter`.
4. Attempt and report views: the chip on the question row, with the answer and chosen options shown in full.
5. Learner side: no new UI. A retired row is a 404, and outline, progress bar and previous/next skip it. Treat any "no longer available" message as an open question.
6. CLI: collect lines, print after commit, add a per-model-type count line in the style of the `Images:` summary.

## 6. Open points to carry into the spec

- Tone for Retired: muted or warning.
- Whether a live child under a retired parent shows a chip.
- Whether a learner opening a retired link sees a 404 or a "no longer available" page.
- Whether the sync prints per-item lines, counts only, or both.
- Whether a mass-retire guard is wanted. Not asked for, so not recommended without a decision.

## Sources

- `spec_dd/2. in progress/sacaa-compliance-content-versions-and-access-2-retire-removed-content/idea.md` and `answers.md`
- `freedom_ls/panel_framework/templates/cotton/panel-status-badge.html`
- `freedom_ls/panel_framework/templates/cotton/data-table-cells/badge.html`
- `freedom_ls/educator_interface/panels/common/badges.py`
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` (page header, person badges)
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` (Inactive, retired)
- `freedom_ls/content_engine/management/commands/content_save.py` (lines 990 to 1028, 1642 to 1656)
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md` (cited by the idea; not re-read here)
- The brand-guidelines skill was not found under `claude_plugins/fls-dev/skills/`, so it is not cited.

status: ok
