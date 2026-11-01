# Research: reference implementations

Note: written from background knowledge of these projects; URLs were not re-fetched this session. Check them before quoting.

## 1. Consolidated upgrade notes for template overriders

| Project | Pattern | Take-away for FLS |
|---|---|---|
| Django release notes | One page per release. Fixed sections: "Backwards incompatible changes", "Features deprecated", "Features removed". Each item names the exact symbol or setting. | Group `upgrade_notes.md` by what the downstream must act on, not by which spec made the change. |
| Wagtail "Upgrade considerations" | A separate page per release, apart from the changelog. Each item says who is affected ("if you have overridden template X") and gives the fix. Template overrides are called out by file path. | Per-template entries: path, what changed in the context or blocks, and the migration step. |
| django-oscar | Release notes include "Minor changes" and "Backwards incompatible changes". They list renamed templates and changed block names, because Oscar expects forks to override templates. | Say "renamed or removed" per template path, since overriders break silently when a template is orphaned. |
| Saleor | `CHANGELOG.md` with a breaking-change marker, plus migration notes in the GitHub release. | The marker convention is useful; a flat changelog is weaker than grouped sections. |
| Open edX | Per-release "Upgrade notes" and DEPR (deprecation) tickets. Removals are announced a release ahead. | Mention deprecation order if anything is removed. |
| Moodle | `upgrade.txt` in every component directory, written by the developer who makes the change, and a central "Moodle dev docs: upgrade notes" page assembled from them. Entries are "Information: ... / Impact: ..." style. | Our model matches: each spec's own notes are the Moodle-style per-component files. The effort-level `upgrade_notes.md` is the assembled central page. |

Adoptable layout for a Django/HTMX project:
- Order sections by risk: URL changes (old to new table), overridable templates (changed, renamed, deleted), new settings with defaults, new event types, migrations (ordered, with data migrations flagged), `requires_tailwind_rebuild`.
- Every item names an exact path, URL name or setting, so the notes can be grepped.
- Generate the template list mechanically. Run `git diff --name-status <base>..HEAD -- '**/templates/**'` and walk the result. Moodle and Wagtail depend on authors remembering; that is where gaps appear.
- Keep it to the schema in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`.

URLs:
- https://docs.djangoproject.com/en/stable/releases/
- https://docs.wagtail.org/en/stable/releases/upgrading.html
- https://django-oscar.readthedocs.io/en/latest/releases/
- https://github.com/saleor/saleor/blob/main/CHANGELOG.md
- https://docs.openedx.org/en/latest/community/release_notes/
- https://moodledev.io/docs/apis/ (upgrade notes and `upgrade.txt` are described under the dev docs "Upgrade notes")

## 2. Product and user docs for admin and educator dashboards

- Moodle docs (docs.moodle.org) are organised per task and role ("Teacher docs", "Admin docs"). Pages are short, screenshot-led, one task each.
- Canvas Instructor Guide is task-based, grouped by feature area, with a "what you'll see" screenshot per step.
- Open edX "Instructor dashboard" docs are organised by dashboard tab (Course Info, Membership, Data Download, Grade Reports). One section per tab, in on-screen order.

For FLS: the idea already picks the on-screen order (dashboard, learners, cohorts, courses, members, history, reports), which matches the Open edX per-tab approach. Keep one heading per screen. Under each heading, give a purpose line, a screenshot, and the actions available. Use the `domain-glossary` terms, and keep screenshots reproducible from the QA folders. Canvas and Moodle put screenshots next to the task, not in an appendix.

URLs:
- https://docs.moodle.org/en/Teacher_documentation
- https://community.canvaslms.com/t5/Instructor-Guide/tkb-p/Instructor
- https://docs.openedx.org/en/latest/educators/

## 3. Accessibility audit artifacts

- GOV.UK accessibility statements follow a legal template. Sections: compliance status, "Non-accessible content" split into "non-compliance with the regulations" and "disproportionate burden", and the date the statement was prepared and last tested. Each known issue is one line naming the page or component, the failing WCAG criterion, and often a planned fix date.
- Wagtail runs a documented accessibility process: automated checks (axe, Lighthouse) in the admin and CI, manual screen-reader testing with named combinations, and a published "known accessibility issues" list on its accessibility page and tracker.

For FLS, the "list of what is deliberately left" should use the GOV.UK shape: one row per known issue with screen, WCAG criterion, impact, reason left, and a link to the follow-up idea in `spec_dd/1. next/`. Also record the test matrix: screen reader and browser, keyboard-only pass, widths 390 and 1440, light and dark. That is what Wagtail publishes.

URLs:
- https://www.gov.uk/guidance/make-your-website-or-app-accessible-and-publish-an-accessibility-statement
- https://www.gov.uk/government/publications/sample-accessibility-statement (sample statement, as linked from the guidance above)
- https://docs.wagtail.org/en/stable/contributing/ui_guidelines.html (accessibility section) and https://wagtail.org/accessibility/ (statement, not re-verified)

## 4. Playwright smoke tests with axe-core

- Node: `@axe-core/playwright` (Deque). Pattern: `new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()` and `expect(results.violations).toEqual([])`. Known issues are suppressed via `.disableRules([...])` or `.exclude(selector)`, each with a comment.
- Python: `axe-playwright-python` (`from axe_playwright_python.sync_playwright import Axe`; `Axe().run(page)` returns results with `.violations_count` and `.generate_report()`). Younger and less maintained than the Node package. The fallback is to inject `axe.min.js` with `page.add_script_tag` and `page.evaluate("axe.run()")`. The fallback has no extra dependency but means vendoring axe-core.
- Wagtail and GOV.UK Design System both run axe in CI, plus manual testing. GOV.UK states automated tools find only a minority of problems, so the manual pass stays.

Adoptable approach for FLS (pytest-playwright):
1. One parametrised smoke test per section: load the page logged in as an educator, assert a heading is visible and no console errors, then run axe and assert no violations.
2. Run each page at 390 and 1440 and in dark mode. This uses the same list as the polish pass.
3. Also run axe after opening the quick view and modal, since axe on page load misses dynamic UI. HTMX swaps need `page.wait_for_load_state` or a wait on the swapped element before analysing.
4. Keep an explicit, commented allowlist of rule ids that mirrors the "deliberately left" list. A test that fails on any unlisted violation keeps the two in step.
5. Colour contrast in dark mode is where axe tends to find real failures. Run it there.

URLs:
- https://playwright.dev/docs/accessibility-testing
- https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright
- https://github.com/pamelafox/axe-playwright-python (check the current repo location; the PyPI name is `axe-playwright-python`)
- https://pypi.org/project/axe-playwright-python/

## 5. Keeping component docs from drifting from code

- Django: `docs/` is in the same repo and PRs must update docs. `versionadded` and `versionchanged` directives tie statements to releases. Docs are built in CI with warnings as errors, and a spelling check runs there.
- Wagtail: same repo, docs build in CI, `autodoc` for API reference, and a PR checklist that includes docs and the changelog.
- Moodle: `upgrade.txt` and a PR template that asks for it. Weaker enforcement.
- Storybook-style and pattern-library projects, including the GOV.UK Design System, render the documented examples from the same source as the component, so the doc cannot describe something that is not there.

Adoptable cheaply for FLS (the idea's example of drift is an Alpine component listed in a skill but never registered):
- A pytest that extracts registered Alpine component names (`Alpine.data("...")` in the JS) and compares them with the names listed in the `alpine-js` skill. It fails on any difference in either direction. This also fixes the known drift, and it needs no new tooling.
- The same idea applies to Cotton components. Compare the files in `templates/cotton/` with the component inventory in docs.
- A deletions check: grep the repo for the old URL names, templates and management commands removed. Run it once in this spec, and keep it as a test if cheap.
- Take the screenshots from QA runs, so the doc is regenerated by the process rather than hand-edited.

URLs:
- https://docs.djangoproject.com/en/stable/internals/contributing/writing-documentation/
- https://docs.wagtail.org/en/stable/contributing/documentation_guidelines.html
- https://design-system.service.gov.uk/ (examples rendered from the component source)

## Short recommendations for the spec

1. `upgrade_notes.md`: Wagtail "who is affected + fix" items, ordered per the Django backwards-incompatible-first convention, with the template list derived from `git diff --name-status`.
2. Product doc: Open edX one-section-per-tab ordering, Canvas/Moodle screenshot-beside-task.
3. Deliberately-left list: GOV.UK statement table, linked to follow-up ideas.
4. Smoke tests: pytest-playwright plus axe (Node package's pattern, Python wrapper or injected `axe.min.js`), a test allowlist that mirrors the deliberately-left list, and a check on the open quick view and modal.
5. Drift guard: a test comparing the registered Alpine components with the `alpine-js` skill inventory.

status: ok
