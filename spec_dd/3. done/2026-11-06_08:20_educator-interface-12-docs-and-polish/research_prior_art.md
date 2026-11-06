# Prior art: docs and polish pass (educator interface spec 12)

All paths are relative to the project root. Reports live under `spec_dd/3. done/<dated dir>/`.

## 1. Here: earlier polish and QA passes

### 1.1 Nothing was ever filed under "spec 12" by name

A search for "spec 12", "docs and polish", "deferred", "left for" in the done QA reports finds no
item explicitly handed to spec 12. The only hand-offs are in specs not yet done:
- `extract_panels_framework-1-gather-generic-code/research_framework_completeness.md` (line 165, 219) flags spec 12 as the highest conflict risk, because its polish pass edits framework templates and `alpine-components.js`.
- `extract_panels_framework-6-claude-plugin/research_plugin_distribution.md` (sections 1 and 2) and its `idea.md` line 98 take the panel developer doc and skill away from spec 12. This is already reflected in the idea.
- `test-organisation-and-hygene-15-educator-interface/idea.md` waits on spec 12.
- `deadlines/research_deadline_integration_points.md` line 417 says spec 12's product doc would need a deadlines note.

So the "deliberately left" list for spec 12 must be harvested from the QA reports below. Nothing was queued for it.

### 1.2 The closest precedent: `2026-10-08_06:54_educator-interface-looks-good`

A visual polish spec against the mockups. Its `qa_report.md` found 4 bugs and fixed 3 (the report footer says "3 fixed, 1 unresolved"):
- B1 sortable header label colour, B2 nav toggle shows chevron not hamburger (`menu_open` icon maps to a chevron in 3 of 4 icon sets), B3 mobile row secondary line not muted, B4 sort icon shrinks when label wraps. All "design drift against the mockups" defects.
- General notes (lines 185-196), left unfixed as cosmetic: org switcher popover offset about 48px, tab title stale after rename, nameless learner cannot be opened from the list, mobile sort fieldset has a border the design lacks, no-JS sort form position differs from the plan.
- **No dark mode exists in either theme.** Test 8.1 only confirmed nothing breaks under a dark preference. Spec 12's idea asks for "default theme and dark mode" screens. Dark mode is therefore not something earlier specs built or verified. Check whether it exists before the spec promises a dark-mode pass (this is a possible new feature, which the idea puts out of scope).
- Process lessons: `FLS_THEME` only changes Django settings, the stylesheet is built by `npm run tailwind_build`. QA ran mostly on the wrong theme until the tester rebuilt. The plan should say to rebuild with `FLS_THEME=first_class`.

### 1.3 Defects found in the effort's QA reports, by class

Items marked UNRESOLVED are open at close and are candidates for spec 12 to resolve or list as left.

**Unresolved bugs (product decisions never taken)**
- Spec 5 `educator-interface-5-permissions/qa_report.md` B1 (line 136-167): a stale delete on an out-of-scope cohort fails silently, because htmx drops the 404. The spec says 404 and the test plan says the 403 modal. Whether an in-page 404 gets visible feedback is undecided.
- Spec 6 `educator-interface-6-cohort-administration/qa_report.md` line 176: learners with no first or last name cannot be opened from lists. Commit 2a51c992 removed the blank link as an a11y fix (blank link has no accessible name); a reverting auto-fix was itself reverted (7452168c). Needs a copy decision, e.g. email or "Unnamed learner". This is an a11y vs reachability conflict, and it is the same finding as in the looks-good spec.
- Spec 7 `educator-interface-7-learner-administration/qa_report.md` line 127: removing the status chip, "Clear all" or Reset shows Removed learners rather than the Active+Pending default.
- Spec 8 `educator-interface-8-bulk-operations/qa_report.md` B1: JS-off bulk action redirects with a toast instead of a result page. Resolved by keeping the redirect and updating the docs, a "docs followed the code" fix.

**Wording and consistency (the "same wording everywhere" pass)**
- Spec 6 (lines 187-198): "Sort icons expose accessible names like `sort_neutral`"; Unregister and Deactivate confirm buttons are `btn-secondary`, the same weight as Cancel; the inactive-cohort fragment says "to edit it" even for register and unregister; the header Reactivate on the Courses tab lands on Overview; the Educators card shows emails in uppercase; full-page GET of an out-of-scope object shows the Django debug 404 while the HX request shows a dialog (9.3.1).
- Spec 7: a bare "Cohort:" label (fixed, a9f64247).
- Spec 8 (lines 173-180): "0 new accounts will get a setup email" appears in previews where it makes no sense; "0 rows were not added." headline; empty count with JS off; the resend confirmation predicts a send that is skipped at run time; the upload file input is unstyled.
- Spec 9: the choice-error message echoes a raw UUID ("polish note", lines 89, 278).
- Spec 10 (lines 228-233): over-limit wording differs between dashboard and cohort page, and the latter exposes the setting name `REPORTS_MAX_LEARNERS` to educators; two quizzes with the same title in different courses show identical headings.
- Spec 11 (lines 156-160): the shared mobile sheet is titled "Filter & sort" although the audit log has no sort.

**Mobile and touch targets**
- Spec 6: Filter/Sort 35px, Unregister 38px under 44px. Spec 9 decided in B6 that 44px applies below `md` only, and listed 40px buttons and 38px row actions at 768 as intended. Spec 12 should reuse that rule rather than reopen it.
- Spec 7: tablet Cohorts table is 747px in a 718px scroll container, so the last column is clipped by 29px.
- Spec 8: the fixed selection bar is about 335px tall (40% of viewport) at 375 while running.
- Spec 9: the Add member sheet's Cancel and Add buttons sit below the fold on the checklist step at 375.
- Spec 2 B1 (fixed): the mobile nav button opened the Filter sheet because Alpine scope merged `dialog` references. B3 (fixed): no-JS mobile filter form was invisible.

**Contrast and a11y**
- Spec 10 line 232: the dashboard over-limit notice is pale amber on white, low contrast. This is not fixed.
- Spec 3 `educator-interface-3-panel-framework-dialogs/qa_report.md` line 88 and 185: screen reader checks (section 5) were **never run**. Only proxy ARIA checks (aria-live, aria-labelledby, aria-expanded) were recorded. Spec 12's real screen reader pass has no earlier result to build on.
- Spec 3 B1 (fixed 8dcfd89a): quick view reopened empty after Back restores htmx history. This is a stale Alpine instance and is a class to retest.
- `educator-interface-better-nav/qa_report.md`: breadcrumbs and sidebar a11y attributes were verified (`aria-current`, `aria-expanded`, `nav` landmark), with no keyboard or aria issues.

**Test-plan staleness (recurring)**
Specs 6, 8, 9, 10 and 11 all record "plan wording was stale" notes (for example spec 8 section 7.2 and 7.3, spec 9 sections 3.8 and 4.5, spec 11 section 4.2, spec 10 login credentials). The plans drift from the code that was changed on purpose. Expect the same when reusing plans for the spec 12 walk.

**Environment and flake notes**
- A Playwright flake under load, `test_modal_form_htmx`, passed alone (looks-good report line 183). The spec 12 requirement "Playwright suites run green" should account for it.
- QA screenshots directories are shared between processes, and spec 8 notes foreign files in its folder. The fresh product-doc screenshots come "from the QA folders", so pick only files the reports reference.
- Seed residue persists between runs (spec 10 line 229).

### 1.4 What earlier docs and upgrade-notes work produced

- Every one of specs 1-11 and looks-good shipped its own `upgrade_notes.md`. These are YAML front matter plus prose: `requires_migrations`, `requires_template_review`, `changed_template_paths`, `requires_settings_change`, `changed_settings`, `requires_tailwind_rebuild`, and so on, followed by "Breaking changes" (see spec 8's `upgrade_notes.md`). The consolidated notes can be assembled mostly by union of these front matters. Spec 8 shows the level of detail expected: API signature changes and renamed context keys. Spec 5 additionally renamed three roles (`organisation_staff` to `organisation_admin`, `instructor` to `cohort_admin`, `ta` to `cohort_viewer`), per `spec_dd/1. next/roadmap.md` line 87.
- `docs/product/educator-interface.md` exists today and has not been rewritten in the rebuild as one piece. The roadmap's text says each spec "documents its own change", and `docs/product/` has no per-section file for the new panels.
- The roadmap is the only record of the decisions (deactivate not delete, role hand-out rules, the three-part denied experience). It states the assumptions, including "mockups are the visual language, not the scope". The consistency pass should read it for terms.
- The `alpine-js` skill drift (a component listed that is not registered) is recorded in `extract_panels_framework-6-claude-plugin/research_plugin_distribution.md` line 26 and 71. It stays in spec 12.
- Agent memory note `project_panel_framework.md` is called out for the deletion pass (same file, line 73).

### 1.5 Implications for the spec

1. Treat the unresolved items above as the seed backlog. Several need a product decision before they can be fixed (nameless learner link text, status chip reset, stale 404 feedback). Make those decisions in the spec, or list them as deliberately left.
2. The pass should be defined by a fixed checklist (viewports 390 and 1440, theme, keyboard, screen reader), because the earlier looks-good spec found its defects through a checklist and a mockup comparison and fixed all within the spec.
3. Confirm dark mode exists. Only the default and `first_class` themes were checked earlier, and neither had dark mode.
4. Screen reader testing is net new. No earlier spec performed it.

## 2. Elsewhere: how end-of-project a11y and polish passes go

Based on general practice; the sources below are general-purpose and none is specific to LMSs.

- Accessibility evaluation methodology insists on fixing scope first, then sampling pages and states, then reporting findings. W3C WCAG-EM requires that the target product be defined so each view is clearly in or out of scope. A vague boundary is the main route to late scope creep. Sampled audits do not prove full coverage, so say so in the spec's "deliberately left" list rather than claiming completeness. Sources: https://w3.org/wai/test-evaluate/conformance/wcag-em , https://www.boia.org/blog/what-is-wcag-em-an-introduction-to-accessibility-evaluation-methodology , https://design.education.gov.uk/accessibility/evaluation-methodology . A search turned up a WCAG-EM 2.0 Working Group Note, but sources disagree on its date, so verify before citing.
- The typical failure mode is that audits produce long findings lists that mix defects with feature requests. The practice that works is to triage by severity and to push new capabilities out as separate items. The idea already follows this ("missing capability goes in `spec_dd/1. next/` as its own idea"). I did not find a web source that documents this specifically, so treat it as general experience rather than a cited finding.
- Automated checks catch only part of the issues, so manual keyboard and screen reader walks are standard. This supports the idea's choice and also argues for time-boxing the screen reader pass to quick view, modal and tables.

status: ok
