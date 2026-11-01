# Best practices: docs and polish close-out (educator interface spec 12)

Note: written from established knowledge of the cited sources; URLs were not re-fetched this session. Verify exact wording before quoting in the spec.

## 1. Accessibility polish (WCAG 2.2 AA)

Method: automated scan first (catches roughly a third of issues), then manual keyboard, then screen reader. Record results as a per-screen checklist in the spec, with a "deliberately left" list.

**Modal dialog** (APG dialog-modal pattern)
- Use native `<dialog>` with `showModal()` where possible, or `role="dialog"` + `aria-modal="true"`, with `aria-labelledby` (title) and `aria-describedby` (message).
- Focus moves into the dialog on open (first focusable, or the least destructive button for destructive confirms). Tab and Shift+Tab are trapped. Esc closes. Focus returns to the invoking element on close.
- Background is inert (`inert` attribute on the rest of the page, or native `showModal`).
- Use `role="alertdialog"` for destructive confirmations that need an immediate response.

**Quick-view drawer** (a non-modal or modal dialog, or disclosure)
- Decide one model and apply it everywhere. If it covers the page, treat it as a modal dialog (above). If the page stays usable, use a non-modal `role="dialog"` or `complementary` region with a labelled close button. Either way: focus in on open, back to the row trigger on close, Esc closes.
- The trigger is a real `<button>` with `aria-expanded` and `aria-controls` (APG disclosure). Do not make a whole `<tr>` clickable without a keyboard-reachable button inside it.
- Announce loading via HTMX swap into an `aria-live="polite"` region, or move focus to the drawer heading after swap. Don't do both.

**Data tables** (APG table pattern; grid pattern only if cells are interactive)
- Plain `<table>` with `<caption>` (or `aria-labelledby`), `<th scope="col">`, `<th scope="row">`. Don't use `role="grid"` unless implementing full arrow-key navigation; for static tables with action buttons, plain table + Tab order is correct and less risky.
- Sortable headers: `aria-sort` on the active `th`, and a `<button>` inside the header.
- Status badges must not rely on colour alone: include text (and a visually-hidden prefix if the icon is the only cue).
- On 390px: a horizontally scrolling wrapper needs `tabindex="0"`, `role="region"`, and an `aria-label` so keyboard users can scroll it; or reflow to cards. Reflow at 320 CSS px without two-dimensional scroll is WCAG 1.4.10 (data tables are exempt).

**WCAG 2.2 criteria that matter most here**
- 2.4.11 Focus Not Obscured (Minimum): sticky headers and drawers must not hide the focused element.
- 2.4.7 / 2.4.13 focus visible and appearance; 2.5.8 Target Size (Minimum) 24x24 CSS px, which matters for row action icons at 390px.
- 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication (less relevant).
- 1.4.3 contrast 4.5:1 text, 1.4.11 non-text contrast 3:1 (badges, borders, focus rings): check both light and dark themes separately.
- 4.1.3 Status Messages: toasts and HTMX result messages need `role="status"`/`aria-live`.
- 1.4.4 / 1.4.10 zoom and reflow; 2.1.1 keyboard; 2.1.2 no trap.

**Screen reader matrix**: NVDA + Firefox or Chrome (Windows), VoiceOver + Safari (macOS/iOS). At minimum one desktop pair; the spec should say which was actually used and note that Orca/Linux alone is not representative.

**Automated checks**: add axe-core to Playwright (`@axe-core/playwright` for Node, `axe-playwright-python` for Python). Run `AxeBuilder.analyze()` with tags `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa`, once per section per theme per viewport (2 x 2 matrix). Fail on violations; keep an explicit, commented allow-list for deliberate leftovers (matches the "left deliberately" list). Also open the drawer and the dialog before scanning, since closed states hide most problems. Playwright's `page.accessibility.snapshot` / `aria_snapshot` (`expect(locator).to_match_aria_snapshot`) can assert the role/name tree of the drawer and table.

Sources:
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- https://www.w3.org/WAI/ARIA/apg/patterns/alertdialog/
- https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- https://www.w3.org/WAI/ARIA/apg/patterns/table/
- https://www.w3.org/WAI/ARIA/apg/patterns/grid/
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- https://playwright.dev/docs/accessibility-testing
- https://playwright.dev/docs/aria-snapshots
- https://github.com/dequelabs/axe-core

## 2. UI copy and consistency pass

- Build an inventory table once: action, verb, confirm title, confirm body, button labels, success message, empty state, per screen. Review the table, not the screens; then grep templates to enforce it.
- Button labels name the action and object ("Deactivate learner", not "Yes"/"OK"). Cancel is the secondary, safe option. Destructive buttons are visually distinct (GOV.UK warning button) and not the default focus.
- Distinguish reversible from irreversible: deactivate/reactivate (reversible, low friction, maybe no confirm) versus remove/unregister (confirm, say what happens to progress/history). The confirm body states the consequence and whether it can be undone.
- Empty states: say what is empty, why, and the next action if one exists; distinguish "nothing yet" from "no results for these filters" (with a clear-filters action).
- Badge vocabulary: one fixed set of states, each with a text label, colour token, and meaning, defined in the glossary skill. Sentence case, no new synonyms.
- GOV.UK guidance: plain language, sentence case, buttons start with a verb, avoid "please", no "click here".
- Tie to `fls-dev:domain-glossary` as the source of truth; if the glossary lacks a term the pass needs, update the glossary rather than inventing wording.

Sources:
- https://design-system.service.gov.uk/components/button/ (warning button)
- https://design-system.service.gov.uk/styles/content/ ; https://www.gov.uk/guidance/style-guide
- https://design-system.service.gov.uk/patterns/confirmation-pages/
- https://design-system.service.gov.uk/components/error-message/
- https://carbondesignsystem.com/patterns/empty-states-pattern/ (empty-state types)
- https://carbondesignsystem.com/patterns/dialog-pattern/ (destructive confirmation shape)

## 3. Product documentation with screenshots

- Task-oriented, in the order the user meets the product (the idea already fixes this). One short intro per section: what it is for, what you can do, then screenshots with captions and alt text that says what matters, not "screenshot".
- Generate screenshots by script (Playwright against seeded demo data) rather than by hand, so they are reproducible and refresh cheaply. Fixed viewport, fixed theme, fixed seed data and clock. Use `page.screenshot(path=..., animations="disabled")` and mask volatile elements (`mask=[...]`).
- Keep screenshot count modest (one desktop per screen, a few mobile and dark examples); every image is a maintenance cost.
- Run an unslop pass last; remove "spec N added" history from product docs (history belongs in upgrade notes and changelog).
- Docs-as-code: link check and a grep that every referenced image exists.

Sources:
- https://diataxis.fr/ (how-to vs reference vs explanation)
- https://playwright.dev/docs/screenshots
- https://developers.google.com/style (alt text and tone)

## 4. Upgrade notes for downstream projects

Follow Django release-note structure: grouped, scannable, each entry says what changed, who is affected, and what to do.
- Sections: Backwards-incompatible changes, Removed, New settings, Migrations, URL changes (old to new table), Template overrides (path, what changed, action), Events, Build steps (`requires_tailwind_rebuild`).
- Template overrides table is the high-value part: for every template in the rebuild, list path, status (unchanged, changed, renamed, removed), and the context or block changes. Generate the list from `git diff --name-status <base>..HEAD -- '*/templates/*'` so none are missed; then annotate by hand.
- Provide old-URL to new-URL mapping, and say whether redirects exist.
- Use deprecation wording consistently ("removed in", not "no longer recommended"). Note required order: migrate before or after deploy, and anything irreversible.
- Merge, don't copy, each spec's notes; link back to them. Check schema fields in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`.

Sources:
- https://docs.djangoproject.com/en/stable/releases/6.0/ (structure and tone; check the actual current version page)
- https://docs.djangoproject.com/en/stable/internals/release-process/#deprecation-policy
- https://keepachangelog.com/en/1.1.0/

## 5. Dead-code and template removal

- Find candidates mechanically, then confirm: for each template under the educator templates dirs, grep for its path in `*.py`, `*.html`, and cotton component names (`<c-...>`); list `{% include %}`/`{% extends %}` references; run `vulture` (Python) as a hint, not an oracle.
- Verify with coverage from the full test run (Playwright plus pytest); a template never rendered is a candidate.
- Dynamic template names (string-built paths, cell templates chosen by column type) defeat grep: check registries and `get_template_names` before deleting.
- Delete in a separate commit from behaviour changes, one category per commit, so revert is cheap. Also remove: stale Tailwind classes only via the rebuild, agent notes and docs that mention deleted commands (grep for the command names), unused i18n or CSS.
- Never remove TODO/`@claude` comments (project rule). Anything deleted that a downstream might override goes in the upgrade notes under Removed.
- Skill inventory drift: generate the list of registered Alpine components by grep (`Alpine.data(`) and compare it to the `alpine-js` skill list, ideally as a small test so drift is caught.

Sources:
- https://github.com/jendrikseipp/vulture
- https://coverage.readthedocs.io/

## 6. Playwright smoke tests per section

- One test per section (dashboard, learners, cohorts, courses, members, history, reports): load as an educator, assert heading, one data row visible, no console errors, no failed network responses (`page.on("console")`, `page.on("response")`), then run axe.
- Prefer role and label locators (`get_by_role`) over CSS; this doubles as an accessibility check because failures indicate missing names.
- Keyboard smoke: open the quick view with `press("Enter")`, assert `expect(dialog).to_be_focused()` or focus within, press Escape, assert focus returned to the trigger.
- Parametrise over viewport (390x844, 1440x900) and `color_scheme` ("light", "dark") using context options (`color_scheme`, `viewport`) rather than duplicating tests; keep full matrix for axe only, and smoke at one combination to keep the suite fast.
- Use seeded fixtures, web-first assertions (auto-wait), no `sleep`. HTMX: wait on the visible result, not on network idle.
- Dark mode in this project: confirm how the theme is switched (class vs media) before choosing `color_scheme` emulation or toggling the class.
- Visual regression via `expect(page).to_have_screenshot()` is optional; the idea says "by eye is fine", so do not add it here (avoid flaky baselines). Revisit in a separate idea.

Sources:
- https://playwright.dev/python/docs/test-runners (pytest-playwright)
- https://playwright.dev/python/docs/emulation (viewport, color scheme)
- https://playwright.dev/python/docs/locators#locate-by-role
- https://playwright.dev/python/docs/best-practices
- https://playwright.dev/python/docs/test-assertions

## 7. Recommendations for the spec

1. Make axe-in-Playwright the gate for "no regressions" and the manual keyboard/SR pass the source of findings; record findings as a table (screen, issue, WCAG SC, fixed/left, reason).
2. Decide the quick-view model (modal vs non-modal) first; everything else follows from it.
3. Resolve the open question: by eye for mockup fidelity; no screenshot diff.
4. Do the copy inventory before touching templates; enforce with grep.
5. Generate the template-override list from git diff, not memory.
6. Order of work: deletions, copy pass, a11y fixes, tests, screenshots, product doc, upgrade notes (docs last so they match the final UI).

status: ok
