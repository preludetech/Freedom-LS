# SDD Todo

This branch was worked interactively rather than through the SDD workflow, so it has no spec, no
plan and no security or structure reviews. The checklist below carries only the steps that still
apply, keeping the standard section numbering so the SDD commands find their headings.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (user) Implement the items in the idea file directly

## 9. QA

- [x] (cmd) Write the QA plan for the changes on this branch
- [x] (cmd) Run `/fls-dev:do_qa` to execute `3. frontend_qa.md` (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [x] (user) Review the QA report
- [x] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [x] (user + cmd) Fix QA bug: form completion page has no Previous button and does not use the player footer (TDD — failing test first, then fix)
- [x] (user + cmd) Re-run `/fls-dev:do_qa` for sections 1, 2, 10.2-10.3, 11.2, 11.4, 12 and the mobile/tablet passes once the dev database is back — they never ran this time
- [x] (user + cmd) Fix QA bug: allauth mail sent outside a request raises ImproperlyConfigured when neither FORCE_SITE_NAME nor SITE_ID is set (TDD — failing test first, then fix)
- [x] (user) Decide what an install that pins neither FORCE_SITE_NAME nor SITE_ID should get when allauth mail is sent outside a request — a default-Site fallback, a clearer FLS-specific error, or a system check that requires FORCE_SITE_NAME — then fix the resolver accordingly
- [x] (user + cmd) Fix QA bug: upgrade_notes.md omits the new freedom_ls/mail app — a downstream is not told to add it to INSTALLED_APPS, nor to rewrite a silenced freedom_ls_deployment.E007 to freedom_ls_mail.E001 (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: the dev preview overrides relabel courses as well as ungating them — an application-gated course wears a Free chip and a coming-soon course stops presenting as coming-soon (TDD — failing test first, then fix)
- [x] (user) Decide whether OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE and OVERRIDE_COURSE_ACCESS_TO_FREE should change badge labelling at all or only gating, then either fix get_access_badge/is_coming_soon_for_display or rewrite the plan's §10.3 expectation to match

## 10. Component styling moves into the components

Added after the first QA pass: component styling moved out of the shared stylesheets and into the
component templates. Meant to be visually inert.

- [x] (cmd) Move each component's styling into its own template; delete the two per-widget stylesheets
- [x] (cmd) Remove the `--fls-flashcard-back-*` and `--fls-card-*` tokens
- [x] (cmd) Record the placement rule in the ds and fls-dev styling skills, the cotton resource, the theming how-to and the product docs
- [x] (cmd) Write `upgrade_notes.md` — deleting two `@import`s downstream is a breaking change
- [x] (cmd) Add demo content that actually exercises the flashcard answer face and a wrapping accordion title
- [x] (cmd) Extend the QA plan: rewritten §5, new §14, wider §12.8
- [x] (user) Review the QA report and fix anything it finds with TDD
- [x] (user + cmd) Fix QA bug: a flashcard whose answer holds a table or code block overflows the viewport on mobile (TDD — failing test first, then fix)
- [x] (user) Decide how a flashcard answer face should handle content wider than the card — shrink and clip, scroll inside the face, or disallow tables and code blocks there — then fix the overflow accordingly
- [x] (user + cmd) Fix QA bug: the side-panel drawer variant's 24rem width cap is defeated by the max-w-none utility, so it renders 720px at a 900px viewport (TDD — failing test first, then fix)

## 11. Product docs

- [x] (cmd) Run `/update_product_docs` to update docs/product/ for this feature

## 12. Author plugin sync

- [x] (cmd) Run `/fls-dev:update_claude_plugin_fls_content` to sync the course-author plugin if authoring functionality changed

## 13. Pull request

- [x] (user) Open a pull request
- [ ] (user) Update the PR description to cover the styling move and its downstream upgrade notes
- [ ] (user) Merge the PR once approved

## 14. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
