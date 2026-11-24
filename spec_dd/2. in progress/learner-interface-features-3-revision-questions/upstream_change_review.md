# Upstream-change review: learner-interface-features-3-revision-questions

direction: changed

## What main gained

Learner reference pages (finished spec `reference-material-content-2-learner-reference`, in `spec_dd/3. done/`). `learner_interface` gained a reference listing page, a reference topic page, a `{% reference_link %}` tag (`templatetags/course_reference_tags.py`) that draws a "Reference" section in the course player sidebar, and a Reference outline on the public course page. The sidebar section is an eyebrow heading link ("Reference", `text-xs font-semibold uppercase tracking-wide text-muted`, same style as the "Course outline" eyebrow) with the reference parts and topics under it in the shared course outline rows (`course_minimal_toc.html#course-children`). Space alone separates it from the rows above. New icon names and mappings in `icons`, and new `urls.py`, `views.py` and `utils.py` entries, are additive. No app boundary in `docs/app_structure.md` moved, and no shared base changed. The scan lists none.

Brand rule 6, "One kind of thing, one look" (`.claude/skills/brand-guidelines/visual.md`), is new, and the QA checklist gained a matching line. A list of course content uses the course outline rows. A heading matches its sibling headings. "A feature brings no list, link or heading style of its own." Rule 3 already says no rule between siblings that space can separate.

The rest of the 75 commits are test-runner, CI, SDD plugin and roadmap changes (faster-test-runs-5, sacaa idea). They touch no revision, `form_engine` or `content_engine` behaviour. `form_engine` and `content_engine` only gained test edits.

The rebase merge is sound. The sidebar renders `{% reference_link %}` and then the Revision include, inside `#course-toc-region`. The revision queries and the `revision` app are untouched by main. `_player_chrome_context` takes both `reference_linked` and `decision`.

## Why it matters for this spec

The Revision outline entry contradicts the new rule 6. `1. spec.md` ("Outline entry", under the learner interface section) and the implemented `partials/course_toc_revision.html` draw the entry as its own kind of link, which the sidebar's established sections do not:
- A `border-t border-border` divider with `mt-4 pt-4`. The Reference section beside it is separated by space alone, and rule 3 forbids a rule between items that space can separate.
- A row with a primary-coloured `revision` icon, semibold `text-on-surface` text and a `bg-primary/5` current state. Its sibling sections use an eyebrow link (`text-xs font-semibold uppercase tracking-wide`, muted, `bg-primary/10 -mx-1 px-1 rounded` when current).

Revision is not a list of course content, so the course outline rows requirement does not apply. The "no link style of its own" and "looks like its neighbours" checks do apply. In the sidebar, Revision would look pasted in beside the Reference eyebrow.

The dashboard (`partials/revision_dashboard.html`: `revision` icon in a tinted circle, `h1` "Revision", one line, full-width button) and the "Revision done" card are page content, not a repeated list or sidebar heading. They stay as they are. The `3. frontend_qa.md` and `qa_report.md` visual pass predate rule 6 and did not check this.

## What to change

- `1. spec.md`, "Outline entry" bullets: replace "One row under the table of contents, after a divider: the `revision` icon, 'Revision' in semibold, and a chip..." with an entry in the sidebar's eyebrow style. It is a "Revision" eyebrow link (same classes as the Reference link in `reference_outline.html`, `mt-6` spacing, no divider rule), with the "N due" chip on the right of the same line. It has no icon and no semibold body row. The current page shows the Reference link's current state (`bg-primary/10 -mx-1 px-1 rounded text-on-surface`) plus `aria-current="page"`. Keep the visibility rule (non-empty bank, "0 due" included, capped "40+ due").
- `2. plan.md`: update the batch step that builds `course_toc_revision.html` to match, and add the rule 6 check to the plan's QA checklist.
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_revision.html` (implemented batch): drop `border-t` and `pt-4`, use `mt-6`, swap the row for the Reference-style eyebrow link with the `c-chip` beside it, and drop the `revision` icon. Update the header comment. Keep `data-testid="revision-link"`, `data-testid="revision-due-badge"` and `<nav aria-label="Revision">`.
- Tests that assert the entry's markup (the revision outline tests in `learner_interface/tests/` and the Playwright revision flow): only adjust if they assert the removed icon or divider. Test ids stay the same.
- `3. frontend_qa.md`: re-check the sidebar screenshot against the new QA line "A new section looks like its neighbours" and re-take the sidebar screenshot.
- `idea.md`: no change.

status: ok
