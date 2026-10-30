# Research: prior_art

Method: no Bash, so no `git log --follow`. The history below comes from the dated `spec_dd/3. done/` directory names plus each spec's own prose. Dates are the directory-name dates. Nothing under `docs/` mentions `for_freedom_ls`, "hand back" or "integration bug". The `for_freedom_ls` convention exists only in the downstream. `docs/` has no `upgrade_notes*` file and no CHANGELOG. `docs/product/configuration-and-extension.md` is the only doc that describes the integration surface.

## 1. Specs that created or changed the update flow

- `spec_dd/3. done/2026-04-02_12:31_make-claude-code-plugin/` — first plugin packaging; the earliest hit for `update_fls`.
- `spec_dd/3. done/2026-06-26_14:55_concrete-implementation-helpers/` — the main design spec. Says `update_fls` "core design is correct and stays", then adds: structured per-spec `upgrade_notes.md`, a dry-run preview, `migrate --check` before and `makemigrations --check` after each spec, template-drift detection, a rollback section, and `uv sync` after every pointer move. Also defines the thin GitHub-template repo. Reacting to: FLS "is designed to be included in other Django projects... We need to make creating and maintaining these implementations easy."
- `spec_dd/3. done/2026-07-09_09:37_fls-test-portability-part1/` — switched the bare `uv run pytest` calls in `update_fls.md` to a marker selection, and added the `fls_internal` marker, optional-app collection guards and de-branded asserts. Problem: "FLS ships its entire test suite inside the installed package... pytest vacuums up every FLS test in the submodule", and observed during the real First Class `home_page` update. Three failure modes: collection aborts, brand-coupled asserts, un-runnable Playwright tests.
- `spec_dd/3. done/2026-07-17_09:57_support-concrete-project-deployment-1-prod-settings/` — has `upgrade_notes.md`. Its `changed_settings` entries carry inline "hard:" comments, which later became the convention.
- `spec_dd/3. done/2026-07-28_23:40_split-claude-plugin/` — moved `update_fls.md` to `claude_plugins/fls-dev/commands/concrete/`. Its notes record the path change.
- `spec_dd/3. done/2026-08-22_15:42_learner-terminology-rename/` — `research_downstream_upgrade_path.md` argues for a hard break with find-and-replace upgrade notes, because FLS "has no live installs". Its list of what a downstream depends on: `INSTALLED_APPS`, URL namespaces, template overrides, `COURSE_ACCESS_BACKEND`, conformance strings, permission strings, table names.
- `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/` — added `manage.py check` as a Layer 4 signal. Problem: `manage.py check` passed "while the site was broken". It also repurposed `freedom_ls_course_access.E001`, which silently breaks downstreams that had silenced it.
- `spec_dd/3. done/2026-08-24_06:31_test_portability_4_upgrade_notes_and_docs/` — current shape of `update_fls.md`: the 3g `check` and `check --deploy` steps, the 3i conformance opt-in file written verbatim, and the corrected marker selection. It fixed a gap: the selection was stale, so downstreams collected WeasyPrint tests and hit a `--strict-markers` collection error.
- `spec_dd/3. done/2026-08-30_10:42_upgrade-notes-name-a-storage-class-that-does-not-exist/` — a correction to notes already shipped; see item 2.
- `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/`, `2026-10-10_11:22_testing-cleanup-junk/`, `2026-10-12_20:53_sdd-improve/` — each mentions `update_fls` in its plan or notes. The marker selection in the file now has a fifth marker (`dev_tooling`), so later specs kept editing it.

## 2. The `upgrade_notes.md` artefact

- Introduced by `concrete-implementation-helpers` (2026-06-26), authored by `/fls-dev:update_upgrade_notes` at the end of an SDD run.
- Frontmatter today, as in `spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/upgrade_notes.md`: `requires_migrations`, `requires_template_review` + `changed_template_paths`, `requires_settings_change` + `changed_settings`, `requires_package_upgrade` + `changed_packages`, `requires_npm_install` + `changed_npm_packages`, `requires_tailwind_rebuild`. The body is prose with "Breaking changes" and "Manual steps".
- `spec_dd/3. done/2026-10-27_20:02_organisation-courses/upgrade_notes.md` — same schema; its body carries a renamed-function breaking change.
- Complaint, in FLS: `.../2026-08-30_..._upgrade-notes-name-a-storage-class-that-does-not-exist/idea.md`. The `prod_bucket_setup` notes named a class that was deleted in PR review. They also missed `E003`/`E004` and miscounted. "First-Class-LMS has not applied these notes... will hit the boot failure". Cause: the notes are written about two-thirds of the way through a spec, and nothing re-reads them after PR review. Fix: a re-verify item in the todo template.
- Complaint, in the downstream: `First-Class-LMS.git/main/spec_dd/for_freedom_ls/simple-application-forms-notes-recommend-a-reverted-upload-setting/idea.md`. The notes tell downstreams to raise `DATA_UPLOAD_MAX_MEMORY_SIZE`, a change the branch reverted.
- Schema weakness, `test_portability_4/idea.md`: 2 of 15 notes set `requires_settings_change: true` for purely optional changes. Authors encode "hard" in inline comments.
- Notes are tied to completion commits. `update_fls` pins to the completion commit, so an in-place fix to archived notes never reaches a downstream integrating that spec.

## 3. `freedom_ls/contrib/conformance/`

- Introduced by `spec_dd/3. done/2026-07-18_13:35_test_portability_2_conformance_suite/` (split from `fls-test-portability-part-2`, Layer 3).
- Motivating failure: the First Class `home_page` update, where `COURSE_ACCESS_BACKEND` was unset and the `applications/` URL include was missing, so `manage.py check` and the stock tests stayed green while a learner hit a 500. See `3. done/2026-08-24_06:31_fls-test-portability-part-2/1. spec.md`.
- Shape: an importable, opt-in module with six probes (`test_fls_namespace_reverses`, `test_reference_url_reverses`, `test_configured_backend_instantiates`, `test_active_theme_resolves`, `test_active_icon_set_resolves`, `test_migration_state_consistent`). `conformance.drop(...)` removes a probe. It is deliberately not a `pytest11` plugin.
- Fragility on rename: probe ids hardcoded `student_interface:*`. `drop("student_interface:courses")` became a silent no-op after the terminology rename.
- `spec_dd/1. next/mega-qa/idea_3_downstream_propagation.md` names conformance as "the model for the whole mechanism" for pushing QA plans downstream: shared source upstream, a thin local opt-in, and an explicit visible skip.

## 4. Keyword hits (workaround, hand back, for_freedom_ls, concrete, First Class, downstream)

- `spec_dd/2. in progress/update_concrete_project_improvements/idea.md` — the idea itself.
- `spec_dd/3. done/2026-06-26_14:55_concrete-implementation-helpers/idea.md` — Claude must never edit the submodule; keep the template thin; do not fork migrations.
- `spec_dd/3. done/2026-07-09_09:09_support-concrete-project-deployment-master-decomposed-into-specs/` — deployment-for-concrete-projects effort; pulled in shared scaffolding.
- `spec_dd/3. done/2026-10-25_21:23_corporate-job-course-recommendations-3-recommend-outcome/downstream_edits.md` — the only FLS-side "downstream edits" file; it lists FLS-internal edits and does not mean concrete projects.
- `spec_dd/1. next/mega-qa/idea_3_downstream_propagation.md` and `research_downstream_qa_inheritance.md` — planned downstream QA inheritance via stub files, a manifest, and upgrade_notes-style declared QA-plan paths. Not started.
- `claude_plugins/fls-dev/commands/concrete/update_fls.md` — the command being inverted.
- `docs/product/configuration-and-extension.md` — Tier 1 to 3 override model, `COURSE_ACCESS_BACKEND` "downstream must set", Conformance Suite section (symbol-free).
- `docs/how tos/theme-fls.md` — Tier-3 shadowing; its worked example needed editing in the terminology rename.
- `docs/product/deployment.md`, `docs/deployment-security-checklist.md`, `docs/app_conventions.md` — downstream-facing wording only.
- `First-Class-LMS.git/main/spec_dd/3. done/2026-08-31_17:37_deploy/research_cross_repo.md` — lists downstream commits `89785e16` "Update FLS: prepare-to-deploy" and `059a7a56` "Update FLS: deploy_prep_2". Each commit had to adapt settings and dev deps after an FLS change. Those are the only downstream "Update FLS" spec records found; nothing else under the downstream `spec_dd/3. done/` matches `Update FLS`.

## 5. How integration pain is recorded today

- FLS side: only per-spec `upgrade_notes.md`, with no docs page, CHANGELOG or version tag (`pyproject.toml` is 0.1.0). The terminology-rename research confirms there is no CHANGELOG or tag convention.
- `docs/product/roadmap.md` is the product roadmap. `docs/app_structure.md` is the app dependency map; neither records integration pain.
- Downstream side: `spec_dd/for_freedom_ls/` (item 7) and `system_qa/07_fls_recent_features/qa_report.md`. That QA report cites six more `for_freedom_ls` filings that have no directory in the downstream now. Examples: `site-resolution-native-callers-500`, which "has now blocked seven QA runs", and `qa-fixture-commands-hardcode-the-demodev-account`. Either they were pulled into FLS or removed; unverified.

## 6. `spec_dd/1. next/roadmap.md`

- No row about inverted update flow, multi-repo work or concrete-project integration. Closest: `mega-qa` (three ideas, "idea_3 downstream propagation" last). It is listed under "Needs work on main first": cut it with `/sdd:roadmap mega-qa`. The roadmap says idea 2 is best written after the educator-interface rebuild.
- Several roadmap efforts (test-organisation-and-hygene, deadlines, educator-interface) touch markers and QA, so they will keep changing the selection string in `update_fls.md`.

## 7. Downstream `spec_dd/for_freedom_ls/` (29 entries, all `idea.md`)

No FLS spec directory matched any of these names in `1. next`, `2. in progress` or `3. done`. Exceptions I could not check: `social-login` and `phone-number-verification` look like feature asks, and `phone-number-form-field` is in `1. next`.

Test-suite portability defects (FLS tests that break in a downstream). The first four are workarounds the downstream built:
- `registration-rules-playwright-tests-escape-the-not-installed-gate` — collection fails if the app is not installed. Workaround: `addopts` ignore of that path.
- `registration-signal-test-leaks-a-mock-site-request` — an FLS test leaks a thread-local request and fails 6 later tests. Workaround: autouse `_no_ambient_site_request` in `apps/conftest.py`.
- `error-page-render-depends-on-base-dir-node-modules` — a 404 becomes a 500 when `BASE_DIR` is repointed. Workaround: session fixture `_warm_icon_cache` in `conftest.py`.
- `settings-defaults-tests-assert-against-the-downstream-config-package` — tests import `config.settings_prod` and hit the downstream's package. Workaround in `pyproject.toml` (lines about 129).
- `icon-intrinsic-size-test-assumes-the-default-icon-set` — a hardcoded 24px; the same class of bug Part 1 was meant to remove. Workaround in `pyproject.toml` (about line 153).
- `sidebar-sections-test-assumes-messaging-is-enabled` — no workaround; the downstream turned messaging on.

Upgrade-note defect:
- `simple-application-forms-notes-recommend-a-reverted-upload-setting`.

Product bugs found by the downstream's mega QA (2026-10-28 and 10-29). Workarounds are shown where they exist:
- `honeypot-rerenders-its-value` — workaround: `BlankHoneypotInput` and a signup form in `apps/project_setup/forms.py`. Only fixes signup.
- `registered-learner-on-gated-course` — workaround: subclass of `ApplicationCourseAccessBackend` in `apps/project_setup/course_access.py`. It could not reach the status page or the apply URL.
- `empty-course-sends-learners-to-a-404-and-finishes-at-zero` — workaround: wrapped `course_home` in `apps/project_setup/course_views.py`.
- `course-detail-continue-restarts-at-item-one` — workaround: template shadow of `course_detail.html`.
- `header-site-name-is-an-h1` — workaround: template shadow of `header_bar.html`.
- `header-auth-links-drop-the-current-page` — workaround: `url_back_here` tag in `auth_link_tags.py`.
- `notification-emails-show-utc-times-without-a-zone` — workaround: shadowed email base templates plus an `in_site_zone` filter.
- `learner-ux-polish-from-mega-qa` — workaround: shadow of `markdown-container.html`.
- Reported with no workaround: `apply-view-accepts-courses-that-need-no-application`, `profile-form-allows-a-blank-required-name`, `zero-page-form-blocks-course-completion` (the downstream fixed its content instead), `accordion-strips-nested-component-attributes` (a workaround section exists), `leave-and-save-discards-the-current-page`, `submitted-answers-are-not-checked-against-the-question`, `course-access-url-changes-state-on-get`, `interest-lost-when-email-confirmed-in-another-browser`, `form-pages-re-query-the-whole-form-to-number-each-question`, `allauth-pages-use-stock-templates-and-copy`, `learner-polish-from-mega-qa-2026-10-29`.
- Feature asks: `social-login`, `phone-number-verification`.

## 8. Downstream workaround census (path:line, from `First-Class-LMS.git/main`)

- `conftest.py:10-43` — `_warm_icon_cache` autouse fixture; states "workaround for an upstream defect, not a fix".
- `apps/conftest.py:47` — `_no_ambient_site_request`; cites the FLS mock-site-request leak.
- `apps/project_setup/forms.py:17` — `BlankHoneypotInput`; "Remove it once FLS's..." fixes the honeypot.
- `apps/project_setup/course_views.py:1-3` — wraps FLS `course_home`; "Remove it once FLS fixes it".
- `apps/project_setup/course_access.py:2-4` — backend subclass for two upstream defects.
- `config/settings_base.py:643` — points `COURSE_ACCESS_BACKEND` at that subclass ("upstream defects").
- `pyproject.toml:129` — pytest config added for the settings-defaults tests defect.
- `pyproject.toml:153` — pytest config added for the icon-size test defect.
- `templates/cotton/markdown-container.html:6` — shadow, "Recorded upstream".
- `templates/emails/base_notification_email.html:5` and `.txt:5` — UTC time shadow.
- `templates/learner_interface/course_detail.html:7` — Continue-button shadow.
- `templates/partials/header_bar.html:8` — h1 shadow.
- `CLAUDE.md:15` — still says `git -C submodules/Freedom-LS pull && git add ... && git commit -m "Update FLS submodule"`. The documented update step is out of date next to `/fls-dev:update_fls`.
- `system_qa/07_fls_recent_features/qa_report.md:135-237` — six more `Filed:` pointers to `for_freedom_ls` items; one "blocked seven QA runs".

## 9. Per-project values an FLS-side command would need (downstream, no secrets copied)

- `claude.sh`: `PLUGINS_ROOT="submodules/Freedom-LS"`; three `--plugin-dir`s (`django-stack`, `fls-dev`, `sdd`); launch refused without it.
- `.claude/fls-dev/config.md`: `Base URL` (`http://127.0.0.1:8000`); dev admin credentials, which are committed local-only values; "QA Dev Data" commands: content reset (`danger_content_delete --yes`), DB drop and create scripts (`.claude/fls-dev/scripts/dev_db_delete.sh`, `dev_db_init.sh`), and `migrate`. Seed list comes from the test plan.
- `.claude/ds/config.md`: Dev base URL; admin theme `unfold`; Alpine CSP build enabled; guardian enabled; rebase rebuild script `.claude/fls-dev/scripts/rebuild_after_rebase.sh`.
- `.claude/sdd/config.md`: setup script `install_dev.sh`, teardown script `dev_db_delete.sh`, rebase hooks, QA command `fls-dev:do_qa`, PR-comment fetch script, a vocabulary source (`apps/*/models.py`). Hooks point into `submodules/Freedom-LS/claude_plugins/...`.
- Not in config, but `update_fls.md` needs them: the settings module (`DJANGO_SETTINGS_MODULE` comes from the downstream `pyproject.toml`), the production settings module for `check --deploy` (a downstream `config/settings_prod.py` exists), and which tests dir holds the conformance import. There is no key for the project's path, branch or test command.

## What the history says

- The invert-the-flow pain is already evidenced: 29 `for_freedom_ls` ideas, at least 9 with a live downstream workaround. Several comments say "Remove it once FLS fixes it". Those removals are exactly the rollback burden the idea names.
- Test-portability defects keep recurring after Part 1 (icon size, sidebar/messaging, settings-defaults, optional-app gate, thread-local leak). Part 1's fixes were one-off; the root cause is that FLS tests run against someone else's config, and only an FLS-side run catches that.
- The idea's "fix in FLS first" matches the downstream's own habit of filing, but the filing path is lossy: no FLS spec exists for any current entry. Six `Filed:` pointers in the QA report have no directory.
- `upgrade_notes.md` works as a machine-readable skeleton (migrations, template paths) but its prose has been wrong at least twice. Both defects were found only by a downstream integrating. An FLS-side run that actually applies the notes to a real project would catch these before merge.
- `update_fls` has accreted steps spec by spec (preview, migration gates, conformance opt-in file, `check` and `check --deploy`). Each addition was a reaction to one observed downstream failure. A rewrite can fold them into one flow.
- The conformance suite is the proven pattern for sharing logic upstream with a thin local opt-in and a visible `drop`. `mega-qa` idea 3 already plans to reuse it for QA plans, and that planned work overlaps the "QA plan might need adapting" part of this idea.
- Rename and hard-break specs need FLS-side coordination. `conformance.drop("student_interface:...")` became a silent no-op. A command run from FLS could test every registered project against a rename.
- Constraints to keep: the downstream must never have its submodule edited, and artefacts live in the downstream tree (`mega-qa` rejects symlinks for this reason). An FLS-side command writes into the other repos, which inverts that rule. Decide explicitly which repo owns branch and commit.
- The downstream's per-project values are scattered across three config files plus `pyproject.toml`. There is nowhere to list "paths of concrete projects" today. A new config key is unavoidable.
- The roadmap has no row for any of this. `mega-qa` idea 3 depends on the same plan-path declarations, so sequencing matters.

status: ok · reason: complete; no Bash, so git history inferred from dated spec directories; some downstream entries only partly read
