# Research: prior art for the account area on panels

Question: what has been tried for this, here or elsewhere, and what happened? All "here" findings are from the local tree; "elsewhere" is limited to allauth.

## Summary

- Nobody has built a panel-framework page outside `educator_interface` yet. This spec is the first learner-side host, so there is no precedent shell to copy. The closest are the educator `_shell.html` and the framework's own test shell (both extend `_base_interface.html`).
- The "plain views, not panels" decision was made for `learner-public-profile-1` (done) and has already been reversed in the ideas for -2, -3 and -4. Only the done spec's own files still carry the old line, and they are history (do not edit).
- The picture upload already ships on the plain page and its QA is a ready-made regression checklist for the move.
- Framework-1 (file uploads) is done but left one UNRESOLVED layout bug on the inline form that the account name panel will inherit.
- Template-override flagging convention exists and is simple: `requires_template_review` plus `changed_template_paths` in `upgrade_notes.md` front matter. No downstream override of the account templates is known.

## 1. Earlier decisions about the account page, and lines that need amending

### Done: `learner-public-profile-1-profile-picture`
Path: `spec_dd/3. done/2026-11-15_09:21_learner-public-profile-1-profile-picture/`.
- `idea.md:47`: "Account editing stays on plain views in `accounts`, not the panel framework." This is now superseded by the roadmap decision (`spec_dd/1. next/roadmap.md:155`). It is in a done folder, so leave it. Do not copy it into the new spec as a constraint.
- `2. plan.md:523`: the invalid POST re-renders with status 200 "as it does today; the form is a plain POST". The new name panel must return 422 instead (idea.md settles this). Any test that asserted 200 on invalid does not exist yet (the research confirms `edit_profile` has no tests), so the spec's "tests first" step must write them knowing the target status differs: pin current behaviour as 200 first, then change it deliberately.
- `upgrade_notes.md` (same folder) lists `accounts/profile.html` in `changed_template_paths`, with the review note "posts with `enctype=multipart/form-data` and shows the avatar chip. An override without the enctype silently drops the upload." That is the template this spec removes or replaces. This spec's own upgrade notes must say the page no longer uses that template, so an override of it silently stops applying (it fails open: no error, the override is just ignored).
- It also tells downstream to allow a 10 MB body on `/accounts/profile/` in any reverse proxy. If the path or the upload endpoint moves (panel action URLs are under a different path), that proxy rule needs restating. Keep the URL `accounts:account_profile` and flag any new upload URL in the notes.
- `qa_report.md` and `3. frontend_qa.md` there cover the current page (screenshots `page-profile-375.png`, `page-profile-768.png`, `page-profile-error-*.png`, `page-test5-replace-desktop.png`, `page-test7-tiny-error-desktop.png`, `page-test9-removed-desktop.png`, `page-test10-missing-file-profile.png`). Reuse as the before-state and as the list of behaviours to keep: replace deletes the old file, removal, tiny-image error, missing-file fallback, and header/messaging avatars refreshing. Tests 3.x also checked `/messages/` avatars.

### Not yet done: `learner-public-profile-2..7` (`spec_dd/1. next/`)
Already amended to point at panels in the account area:
- `-2-profile-and-page/idea.md:16-17, 55-58`: "No plain edit views are added"; adds a sidebar section; uses the editable list panel. Line 99 says its earlier case against panels "is superseded".
- `-3-completed-courses/idea.md:37-38`, `-4-certificates/idea.md:53-56`: same.
- `-5-index/idea.md:24, 57`: "learner-facing styling, not the educator panel framework". That is about the public index page, not account editing, and stays correct. Do not amend it.
- `learner-public-profile/idea.md:8` (parent): still poses the question "should we use the panels framework for the user-profile and these settings?" as open. This is the one line left that reads as undecided. Amendment candidate (the parent is a source idea; a one-line note pointing at the roadmap decision would do).
- `learner-public-profile/research_existing_profile_code.md` and `research_comparable_systems.md` still hold the old reasoning; they are research, leave them.
- `-7-contact/idea.md` and `-6` have no panel/plain lines. `-7` will probably add a settings section, which is a sidebar entry in this spec's account area. Worth naming in the sidebar's "room for later sections".
- `research_current_account_pages.md` (this dir) lines 10, 72-75, 92 still describe four "not the panel framework" lines. Those are stale as written: `-2`, `-3`, `-4` are amended, `-1` is done. Net lines still needing amendment: the parent idea line 8 only.

### Roadmap
`spec_dd/1. next/roadmap.md:139-159` ("Account area on panels") records every decision this spec relies on, including "Assumed: the account shell extends the general interface base, follows the host contract from `extract_panels_framework-4-template-contract`, and rebases across `extract_panels_framework-5-package-and-install`." Order note: this spec can start now, beside `-2-editable-list-panel`. Line 183 records the effort-level decision.

## 2. Framework-1 file-upload actions (done) and framework-2 editable list panel (in progress)

Path: `spec_dd/3. done/2026-11-19_06:14_learner-profile-use-panels-framework-1-file-upload-actions/`.
- It gives the form actions `files`, multipart encoding and a request-error message inside the form (`upgrade_notes.md`). The picture panel builds on it. A form used by a panel form action whose `__init__` takes `data` then keyword-only arguments raises `TypeError` on `files`; the new account forms must accept `files` after `data`.
- Inline record form moved to `panel_framework/partials/inline_record_form.html`; the educator path is a one-line include. A name panel in `accounts` should use the framework path.
- `qa_report.md` bug B1, **UNRESOLVED**: the hidden `[data-request-error]` element is the inline form's last child and adds 12px under the field row. The auto-fix (`456fa222b`) was reverted (`494c1202f`) because the base `form { @apply space-y-2 }` rule in `tailwind.components.css` then applied an 8px margin. A correct fix must neutralise the base form spacing (for example keep the holder from being the last child, or `space-y-0` with flex gap) and be tested by measuring rendered layout in a browser. The account name panel uses the same inline form, so it will show the same extra space unless the bug is fixed first or in this spec. Decide who owns it.
- Same QA: a blank learner first name is accepted by the server (general note b, pre-existing). The account name panel replaces `UserForm`; decide whether blank first/last name stays valid (it is today) rather than inherit it by accident.
- Framework skill facts to reuse (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`): a record's own name is an inline field with Save, not a dialog (369-371); an inline field error is one line under the field, `role="alert"`, `aria-describedby`, `aria-invalid`, no summary (374-377); file forms (382-420, 416-417: a response carrying the out-of-band toast from `partials/messages.html` gets no framework error message, because the toast is the message).
- Framework-2 (`spec_dd/2. in progress/learner-profile-use-panels-framework-2-editable-list-panel/idea.md`): no consumer page changes there; the account page only needs it for later specs. It edits the same action and form templates as `extract_panels_framework-4`; the roadmap says whichever lands second rebases (`roadmap.md:152`). This spec touches neither, but should not duplicate list logic.

## 3. Open item: how "Profile saved" becomes the panel's confirmation

- Today `edit_profile` adds a Django messages flash "Profile saved" and re-renders (no redirect) (`research_current_account_pages.md`, row 1).
- The skill already says a response with the out-of-band toast from `partials/messages.html` gets no framework message (SKILL.md:416-417). So the existing precedent is: a successful panel save may emit the toast (flash messages through the framework's out-of-band `messages.html`), or the refreshed panel heading shows the new name. The educator inline name save was QA'd as: disabled "Saving…", then the heading updates and focus returns to the first field (framework-1 QA test 2.3, 3.2). No educator action sets a toast on error (test 7.5 skipped), so toast-on-success is untested for panels in the educator interface. Grep of `claude_plugins/fls-dev` found no skill text that names an "announcer" convention beyond the `announcer_host` fragment (coupling audit T11); no QA entry records its live-region behaviour.
- Precedent for the choice: educator Name panel (heading refresh and focus return) is the established look; adding a toast or announcer message would be new. Consider the announcer for screen readers only if the heading refresh does not announce.

## 4. Host and template contract (`extract_panels_framework`)

- `spec_dd/1. next/extract_panels_framework/research_coupling_audit.md`:
  - **T11** (lines 74): the real page-shell contract. A host shell extends `_base_interface.html`, `partials/page_title.html`, and fills the blocks `header footer sidebar_content content_header_top quick_view_host modal_host extra_alpine_components page_title sidebar_storage_key`. The framework's `modal_host`, `quick_view_host`, `announcer_host`, `sidebar_nav`, `breadcrumbs`, `document_title` fragments are included by the host's shell (educator `_shell.html:5,36,71,79,83,90,94`). The package ships no production shell. Reference: `freedom_ls/panel_framework/tests/templates/panel_framework/test_interface.html:1-57`.
  - **J3** (line 91): fixed DOM ids the framework addresses: `#main-content`, `#interface-main`, `#app-modal`, `#app-modal-body`, `#quick-view*`, `#instance-header`, `#sidebar-nav`. `#interface-main` is also read by `freedom_ls/base/static/base/js/interface-swap-fallback.js:9-10`, which expects the response to contain it. An account shell that omits `#interface-main` breaks the swap fallback.
  - P9 (line 47): `request.panel_url_kwargs` and `request.panel_scope_name` are read with `getattr` and default; the educator sets them in `educator_interface/views.py:1884`. An `accounts` host should set them or accept the defaults.
  - P10 (line 48): `site_name` template variable required by `navigation_response.html` and `document_title.html`, from an FLS context processor; check it is present on the account area.
  - J2 (line 90): `sidebar_nav.html` named an FLS component `refreshTimer` and a `comms` event. Now resolved: the skill lists `refreshTimer` as owned by `panel_framework` (`shell-components.js`), with menu count events from `get_menu_count_events()` (`claude_plugins/fls-dev/skills/alpine-js/SKILL.md:28`). The account sidebar needs no counts.
  - J4/J5 and 2 (lines 92-93, 127): host provides htmx 2.x, the Alpine CSP build, the global `X-CSRFToken` `hx-headers` on body, and JS load order (framework JS after the host base bundle, before Alpine). `_base_interface.html` must be checked to supply these.
- `spec_dd/2. in progress/extract_panels_framework-4-template-contract/idea.md` (not yet landed; no research or todo hits for T11/J3 in its `todo.md`): part 1 documents exactly this contract and says the framework ships no production shell. Part 2 introduces `panel-`-prefixed primitives and may change cotton component names the account shell uses; part 3 moves `.panel-surface/.panel-canvas/.modal-backdrop-host` to a package stylesheet. FLS theme overrides of `.panel-surface/.panel-canvas` keep working there. The account shell should use only documented hooks so it survives this spec, and rebases across `extract_panels_framework-5-package-and-install` (roadmap line 156).
- Coupling audit section 3 (lines 135-162): `comms` is already a second consumer of framework components (`c-panel-search-field`, `c-panel-avatar-chip`, `c-panel-empty-state`), so a learner-side non-educator use of the cotton kit exists. It did not need a shell. This account page is the first non-educator consumer of the shell fragments.

## 5. Educator interface refactor
- `spec_dd/1. next/educator-interface-refactor*/` and `educator-interface-refactor-1-scaffolding-and-common` (in progress): they define the `panels/<area>/` layout (config.py, panels.py, instance_view.py) the idea says to follow in `accounts`. `research_panel_framework_fit.md:213-220` (learner-profile-use-panels-framework) recommends `accounts/panels/<area>/` so later areas fit, and notes a new `accounts` consumer does not collide with the refactor moves. `research_code_inventory.md:294,341,358`: shell-level tests (`test_sidebar.py`, `test_interface_urls.py`, `test_document_title.py`) stay at the educator top level; `test_sidebar.py:173-187` asserts the educator cog link to `account_profile`, which must keep passing.
- Invariants: `research_panel_framework_fit.md:120` says the educator invariants (`invariants/test_config_authorisation`, `test_organisation_isolation`) walk only educator `SECTIONS`, so an `accounts` config is not covered; the idea already says to test that in `accounts`.
- The framework check `check_panels` (E001-E008, `checks.py`) runs on `manage.py check`; `educator_interface/tests/invariants/test_system_checks.py:13` runs `manage.py check` and the new `accounts` panel must pass it (`research_panel_framework_fit.md:231`).

## 6. fls-dev captured feedback bearing on this spec

- Searched `claude_plugins/fls-dev/` (skills, resources, commands) for account, allauth, confirm, announcer, sidebar, saved. Hits that matter: `skills/panel-framework/SKILL.md` (confirmations are a modal in `#app-modal`, never a page of their own, JS on or off; confirm states what is true now and names the records it touches; tone `error` for delete/remove, 300-311, 531-534; dialogs for multi-field forms and confirmations, 369-371). That governs the picture "Remove" confirmation: the done spec's UX research recommended no confirmation for photo removal (`research_ux_patterns.md:26` of the done spec, "no authoritative source on confirmation"), and the skill lists Remove as `error`-tone confirm. The new spec has to decide which rule wins for removing a picture. Prior behaviour to preserve (per idea): removal as it works today.
- `skills/registration/SKILL.md` and `resources/email_templates.md` mention account flows (registration completion, email templates) but not the account page; nothing captured about sidebars outside the educator interface (`skills/educator-interface/SKILL.md` has 2 hits, educator only).
- `skills/domain-glossary/SKILL.md`: no entry for "Profile", "Account" or "Personal details" (grep hits only for `Learner` is not `User`, line 91, `registered` vs `signup`, 257, and `account` as in an account being created, 224). So the labels "Account" and "Personal details" are not in conflict with a glossary term, but "Profile" appears nowhere as a defined term either; the new "public profile" will need an entry. `Learner` is the `(user, organisation)` row, not a user (line 91): the account page serves users, including educators and admins, so avoid "learner account" wording.
- No captured user feedback (`capture-feedback` output) about the account page exists in `claude_plugins/fls-dev` or in `spec_dd` outside the done picture spec.

## 7. Upgrade notes and theme-override flagging

- Convention (`claude_plugins/fls-dev/commands/update_upgrade_notes.md:21-22, 49, 89, 103-105`): front matter `requires_template_review: true` and a list in `changed_template_paths`; changed templates under `freedom_ls/` trigger it; Manual steps name "review and re-apply customisations to `freedom_ls/...`"; Breaking changes cover renamed settings, removed template blocks, changed URLs. Worked examples: the picture spec's notes (above) and framework-1's notes, which add a distinct "A host that shadows the old path keeps its own markup and misses X; move the override to the new path" paragraph. That wording is reusable for `accounts/profile.html` and `allauth/layouts/manage.html`.
- The theme doc, `docs/how tos/theme-fls.md:9,11,30-32` and `~80, 287-324` per the current-pages research: Tier 3 theme overrides shadow any template by path, so a theme can shadow `accounts/profile.html`, `allauth/layouts/manage.html` and the allauth page bodies. No concrete downstream override of these is recorded in `docs/` or `claude_plugins/fls-dev` (confirmed by the earlier research); it is unverifiable from this tree and the owner or `fls-dev:concrete_spec_integration` (`claude_plugins/fls-dev/resources/concrete_spec_integration.md`, 5 hits for account/allauth/etc.) would know.
- Failure mode to state: an override of `accounts/profile.html` stops applying silently if the page now uses a different template. An override of `allauth/layouts/manage.html` keeps applying but replaces the account shell for email and password pages, which breaks the shared sidebar for that project. Say both. A project overriding `manage.html` in its theme will see the new shell on neither page (it loses the sidebar), so the notes should tell it to port the sidebar include.
- `base/templates/allauth/layouts/{base,entrance,manage}.html` and `allauth/elements/button.html` are FLS-owned overrides (research_current_account_pages.md). Only `manage.html` should change; `entrance.html` must not (complete_registration etc.).

## 8. Elsewhere: restyling django-allauth manage pages

- allauth's templates were refactored in 0.58.0 (2023-10-26, flagged backwards incompatible) so that look and feel changes by overriding a few core templates (the layouts and element templates); projects with their own full page templates were unaffected, projects relying on built-in templates could be affected. Source: https://docs.allauth.org/en/latest/release-notes/2023.html
- Official guidance: the account-management layout is `allauth/layouts/manage.html`, overridable by providing it in your project; there is a base layout and an entrance layout as well. Source: https://docs.allauth.org/en/latest/common/templates.html (surfaced via search; this page was not fetched in full, so treat the exact filenames as confirmed only by the local tree: the project already overrides `allauth/layouts/{base,entrance,manage}.html` and `elements/button.html`).
- Pitfalls seen in practice, partly unverified (search returned mirror sites and I could not confirm any official 65.x change to `manage.html`):
  - Overriding page bodies (`account/email.html`, `password_change.html`) copies allauth markup that moves between versions, so the override quietly drifts or breaks when forms change (new fields, reauthentication prompts, the "elements" system). Overriding the layout only, as this spec plans, is the supported low-risk route.
  - The nav links in `manage.html` are `{% url ... as x %}` guarded, so the FLS file already tolerates optional apps being absent. A rewrite should keep the guards, because enabling `allauth.mfa`, `usersessions` or `socialaccount` later would otherwise break `{% url %}` with `NoReverseMatch` or lose their links. Out of scope here, but the sidebar should have a place for them or be easy to extend.
  - Upgrade check: diff the project's `manage.html` against the shipped `allauth/templates/allauth/layouts/manage.html` of the target allauth version when upgrading, as no changelog entry covers a layout-only change reliably.
- Not fetched or verified: any specific project's post-mortem about restyling manage pages. I found none beyond the release notes above.
- Sources:
  - https://docs.allauth.org/en/latest/release-notes/2023.html
  - https://docs.allauth.org/en/latest/common/templates.html (search result only)
  - https://docs.allauth.org/en/dev/common/templates.html (search result only)

## 9. What this means for the spec (short)

1. Amend only the parent idea line 8 (`spec_dd/1. next/learner-public-profile/idea.md`) and fix stale lines in `research_current_account_pages.md` if it is re-used; -2, -3, -4 are already amended, -1 is done.
2. Pin today's `edit_profile` behaviour (200 on invalid, flash "Profile saved") in tests first; the change to 422 is deliberate.
3. Decide ownership of framework-1's unresolved B1 (extra 12px under the inline form) before the name panel ships on it.
4. Reuse the picture spec's QA list as the regression checklist; reconcile "Remove" confirmation with the panel-framework skill's confirm rule.
5. Build the shell from T11 and J3 (ids including `#interface-main`, `site_name`, htmx/Alpine/CSRF header) and note it is the first non-educator host.
6. Upgrade notes: `requires_template_review: true`, list `accounts/profile.html` (no longer used) and `allauth/layouts/manage.html` (new shell), and say what an existing theme override of each does after the change.

status: ok
