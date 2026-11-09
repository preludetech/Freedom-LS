# Research: known complaints about bulk selection and bulk actions

Topic `known_complaints`. Question: what do users commonly complain about with a data-table bulk-action bar (appears on selection, count, select all, de-select all, Clear, text-only buttons, More dropdown, modal confirmation)?

Evidence quality: searches returned mostly design-guidance articles and issue trackers, few raw forum threads. Where I found no sourced complaint I say so rather than invent one.

## 1. Complaints with a source

| Complaint | Evidence | Source |
|---|---|---|
| "Select all" is ambiguous: page or every matching result. A checkbox that silently covers only the visible page makes users under-scope or over-scope. | SaaS UI guide calls scope the most botched selection decision. The fix is a two-step: "All 50 on this page are selected. Select all 2,000." | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns ; https://www.patternfly.org/patterns/bulk-selection/ |
| Cross-page "select all" is fragile or does nothing. | Django forum: "Select all" for admin actions ignored the cross-page selection and acted only on checked rows. Clicking any single checkbox made the "Select all" link vanish until reload. Django ticket #15742: action applied only to the first page's objects. Ticket #33083: wrong selection when actions sit top and bottom. | https://forum.djangoproject.com/t/select-all-not-working-for-admin-actions/6615 ; https://code.djangoproject.com/ticket/15742 ; https://code.djangoproject.com/ticket/33083 |
| Cannot select all then untick a few. | Django #36706 asked for "select all but one" (402 users, untick one). Closed wontfix; the count falls back to "99/100 selected". | https://code.djangoproject.com/ticket/36706 |
| Selection is lost on pagination, sort, filter or navigation, so users rebuild the set. | Listed as a core failure; Ordio guide says selection should persist across pagination, filtering and sorting and warns against reading checked boxes from the DOM. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns ; https://www.ordio.com/docs/guides/BULK_ACTIONS_PAGINATION.md ; Django ticket reporting page navigation undoes select-all: https://code.djangoproject.com/ticket/33083 |
| Cross-page option missing or undiscoverable (Gmail). | TechRadar and a Google support thread: "select all conversations that match this search" missing in several browsers; the workaround was to jump to the last page by URL. Not available in the mobile app. | https://techradar.com/news/google-accidentally-deleted-this-fan-favorite-gmail-feature ; https://support.google.com/mail/thread/73130046 |
| Hidden selection size: users act without seeing how many records are selected. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| Destructive bulk actions with no confirmation, or a confirmation that omits the count and the operation. | Same guide. Gmail users rely on immediate undo and Trash as the safety net. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns ; https://blog.superhuman.com/how-to-mass-delete-emails-gmail |
| Over-confirmation: heavy dialogs on low-risk actions teach users to click through unread. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| Vague partial-failure results: a generic "Done" hides failures, a generic "Error" hides successes. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| No progress feedback on large runs: users are unsure whether to wait or re-trigger. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| Actions hard to find: users select rows but cannot locate where to act; or the bar shows buttons that do nothing until selection. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| Overflow menus cost discoverability: "one extra click and reduced discoverability" for frequent actions. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| Hidden modifiers (shift/ctrl-click range select) work only if discovered; nothing on screen says they exist. | Same guide. | https://www.saasui.design/blog/saas-bulk-actions-ux-patterns |
| LMS: a bulk add without the matching bulk remove gets complained about (Moodle MDL-61007, recurring bulk-unenrol request since Moodle 2.0). | Quoted in the repo's own earlier research. | https://moodle.org/mod/forum/discuss.php?d=166158 ; repo file `spec_dd/1. next/educator-interface-full-polish/comparable-systems-learner-management.md` lines 97-100 |

## 2. Asked for but not found sourced

I found no user complaint (as opposed to design advice) for these. Treat them as design-risk hypotheses, not evidenced complaints.
- Layout shift when the bar appears. One search result suggests rendering nothing at count 0 and using a fixed or floating bar (Jira and ClickUp float it at the bottom) so rows do not move. That is inference, not a stated complaint. https://hexdocs.pm/phia_ui/PhiaUi.Components.BulkActionBar.md
- Text-only buttons not looking clickable. No source found.
- Modal forms losing input on validation error. No source found. FLS already returns 422 for HTMX validation errors (CLAUDE.md), which is the relevant guard.
- Jira bulk-edit selection behaviour. Nothing returned.

## 3. FLS's own captured feedback and QA

- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` section "Selection bar" (lines 124-127): the bar is fixed to the bottom below `lg`, keeps every control inside the viewport at 375px, and the list reserves its height beneath. That is the one rule recorded; no complaint log lives in the skill.
- QA for the shipped feature, `spec_dd/3. done/2026-11-01_14:50_educator-interface-8-bulk-operations/qa_report.md` (§6, lines 83-108, and notes lines 173-180). Behaviours that already pass and must not regress:
  - Buttons hidden when nothing is selected; status "2 selected · showing 1-9 of 9 learners".
  - "Select all matching" then untick one gives "29 learners changed" (the exclusion model Django declined).
  - Sort and page change clear the selection and hide the bar buttons (6.7). So FLS does not persist selection across pages; the idea does not ask for that.
  - A stale all-matching selection returns a 422 "The selection changed since you opened this" (6.12).
  - Confirmations state skips with reasons; result states counts.
  - Large runs go to the background with a running state in the bar.
  - Observed defects: with JS off the status reads " selected · showing …" with no count; at 375px the running-state fixed bar is about 335px tall (about 40% of the viewport); a repeat resend still predicts the original count.
- The idea's own opener ("looks bad") is the only captured visual feedback on this bar; the roadmap line says restyle to the mock only.

## 4. Implications for the spec (derived)

1. Keep the count always visible and make "select all" state its scope (page vs all matching N), as Gmail and PatternFly do.
2. Keep the confirmation naming the count and the skips (already present; the modal restyle must not drop it).
3. Do not hide frequent actions in "More"; put the common ones as buttons and the rest in the menu.
4. Give text-only buttons a visible button treatment (hover, border or fill) via existing project components; no source, so a judgement call.
5. Avoid the bar pushing table rows: reserve its space or use the filter bar's slot (the design replaces the filter bar with the selection bar, which suggests the same footprint).
6. Fix the known defects above if in scope (the no-JS count, mobile height).

status: ok · reason: web sources are mostly guidance and trackers; layout shift, text-only buttons and modal input loss had no sourced user complaints and are flagged as such
