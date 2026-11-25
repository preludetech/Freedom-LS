# Research: downstream imports of the educator_interface modules

Question: what breaks, in concrete projects and in FLS itself, when the contents of
`freedom_ls/educator_interface/{views,actions,filters,quick_views}.py` (and `reporting.py`) move
into `freedom_ls/educator_interface/panels/<area>/`? Paths are relative to the FLS repo root
unless they start with `/`.

## 1. Concrete projects

- `.claude/fls-dev/config.md:5` lists exactly one: `/home/sheena/workspace/first_class/First-Class-LMS.git/main` (First-Class-LMS). No other project is configured.
- First-Class-LMS carries FLS as a git submodule at `submodules/Freedom-LS` (`claude_plugins/fls-dev/commands/concrete/update_fls.md:26` reads `submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/upgrade_notes.md`). Its own code is a separate tree from that copy.

## 2. References inside the concrete project

Searched First-Class-LMS excluding `submodules/` (the FLS copy) and `spec_dd/` (history/QA artifacts) for `educator_interface.(views|actions|filters|quick_views|reporting)`, `from freedom_ls.educator_interface import ...`, and any `freedom_ls.(educator_interface|panel_framework).<module>.<Class>` dotted path.

Result: **no import of, subclass of, override of, mock.patch string for, or settings reference to any of the five modules.** The only references to the app are:

- `/home/sheena/workspace/first_class/First-Class-LMS.git/main/config/urls.py:62`: `path("educator/", include("freedom_ls.educator_interface.urls"))` (the `urls` module, not a moved one; it itself does `from . import views`, so FLS must keep `urls.py` pointing at the new locations).
- `/home/sheena/workspace/first_class/First-Class-LMS.git/main/config/settings_base.py:124`: `"freedom_ls.educator_interface"` in INSTALLED_APPS.
- `/home/sheena/workspace/first_class/First-Class-LMS.git/main/config/settings_base.py:211`: `freedom_ls.learner_management.context_processors.can_access_educator_interface` (a different app; unaffected).
- `.claude/agent-memory/fls-dev-qa-data-helper/bootstrap_and_gotchas.md` matched a looser search but contains no `educator_interface` text (checked); no action.
- Many `spec_dd/fls_integration/**/qa_report.md` and `frontend_qa.md` files mention `educator/` URLs or `educator_interface:` URL names only as QA prose. URL names are unaffected as long as `app_name = "educator_interface"` and the route names stay.

The submodule copy (`submodules/Freedom-LS/config/urls.py:68`, `settings_base.py:135,215`) is FLS itself at a pinned commit, not downstream code.

Conclusion: First-Class-LMS needs **no code change** from this refactor. It consumes educator_interface only through `include(...urls)` and INSTALLED_APPS. Caveat: FLS says it "is designed to be extended" (CLAUDE.md), so an unknown, unconfigured project could subclass `CohortConfig` etc. from `views`; the repo cannot see them.

## 3. References inside FLS, outside `freedom_ls/educator_interface/`

Python imports (must change):
- `freedom_ls/qa_helpers/management/commands/qa_create_course_cohort_registrations.py:50`: `from freedom_ls.educator_interface.views import CourseCohortRegistrationDataTable`
- `freedom_ls/qa_helpers/management/commands/qa_create_direct_course_registrations.py:42`: `from freedom_ls.educator_interface.views import CourseLearnerRegistrationDataTable` (docstring at line 6 names `freedom_ls/educator_interface/views.py`, update too)

Dotted-path strings resolved at runtime (not caught by import-refactoring tools):
- `freedom_ls/base/notification_categories.py:53`: `url_builder="freedom_ls.educator_interface.notification_urls.bulk_run_table_url"` (module `notification_urls`, not one of the moved ones; only breaks if that is also moved).
- `BulkActionRun.action_path` is **persisted** in the database: `freedom_ls/panel_framework/bulk_actions.py:348` writes `f"{type(self).__module__}.{type(self).__qualname__}"`, `freedom_ls/panel_framework/models.py:32,57` store it, `freedom_ls/panel_framework/bulk_runs.py:28` does `import_string(run.action_path)`. Every existing run row for an educator action holds `freedom_ls.educator_interface.actions.<Class>`. Moving an action class changes its `__module__`, so old rows stop loading. **A re-export shim in `actions.py`/`views.py` would make `import_string` work for old rows (the name is still importable there) but new rows would record the new module path; a clean move without a shim needs a data migration.** Precedent: `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py:5-30` does exactly this for a rename (`RunPython` updating `action_path`), and its test `freedom_ls/educator_interface/tests/migrations/test_0001_rename_unregister_bulk_runs.py:15` pins `ACTIONS = "freedom_ls.educator_interface.actions."`. Note that migration 0001 hard-codes the old path as a string; it stays correct as history (never edit existing migrations); a new migration must map old path to new path per class.

URL-name references (unaffected if names are kept): `freedom_ls/learner_management/tests/test_signals.py:172`, `freedom_ls/comms/tests/test_bell_tag.py:97`, `freedom_ls/contrib/conformance/test_urls.py:75`, `freedom_ls/organisations/tests/test_admin.py:179`, `freedom_ls/base/templates/partials/header_bar_user_menu.html:22` (`educator_interface:root`), `freedom_ls/base/tests/components/test_header_bar_user_menu.py:55`, `freedom_ls/base/tests/error_pages_urls.py:45` (`include("freedom_ls.educator_interface.urls")`), `freedom_ls/panel_framework/views.py:1501-1502` and `panel_framework/templatetags/panel_tags.py:146` (docstrings only).

Comment-only mentions: `freedom_ls/reports/gather.py:371` ("educator_interface/views.py"); `freedom_ls/panel_framework/tests/test_views.py:356` (points at `educator_interface/tests/test_config_authorisation.py`, which actually lives at `tests/invariants/test_config_authorisation.py`; already stale).

`docs/`: only `docs/app_structure.md` (app-level dependency graph, lines 31, 132-144, 211, 274, 323, 338). No module-level references. A new `panels` package inside the app does not change the app graph.
`config/`: `config/urls.py:68`, `config/settings_base.py:135,215`. `demo_content/`: no references.

Claude plugins (name file paths literally):
- `claude_plugins/fls-dev/resources/testing.md:26`: `from freedom_ls.educator_interface.views import learner_import` (auth-bypass example). Update.
- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:41`: names `freedom_ls/educator_interface/filters.py`. Update. Lines 9, 23, 25 name the app generally.
- `claude_plugins/fls-dev/skills/alpine-js/SKILL.md:46,51`: template paths `educator_interface/panels/course_content.html` and `.../cohort_report_downloads.html`. These are **template** directories, not Python; a new Python package `panels/` does not collide, but the spec should not rename templates by accident.
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md:9,19,89`: says `freedom_ls/panel_framework` and describes `panels.py` generically; no path into the moved modules. Not affected, but note a skill/test-layout rule ("Make sure the unit tests follow the same hierarchical structure") may need the `testing` skill (`skills/testing/SKILL.md`) and `resources/plan_review_fls_threats.md:24` checked for where tests must live.
- `.claude/ds/config.md` and `.claude/sdd/config.md`: no reference to these modules.

Inside `freedom_ls/educator_interface/` (the bulk of the work, listed for scoping):
- Non-test: `urls.py:3` (`from . import views`, uses `views.interface_root`, `cohort_report_download`, `learner_import*`, `interface`, etc.); `templatetags/educator_tags.py:7-8` (imports from `reporting` and `views`); `reporting.py:20,26,71`; `actions.py:50,189,1770`; `quick_views.py:40`; `filters.py:41`; `views.py:77,118,152,157`. Note `OrganisationScopedRequest` and `interface_config` are imported **from `views`** by `actions.py`, `filters.py`, `quick_views.py`, `reporting.py` (lazy, inside functions or TYPE_CHECKING; these form a cycle that the new layout needs a `common` home to break).
- Tests importing from `views`: `tests/test_views.py:63,76`, `test_interface_urls.py:19`, `test_create_cohort_action.py:34`, `test_filters.py:30`, `test_course_visibility_and_interest.py:19,260`, `test_cohort_delete_action.py:39`, `test_learner_section.py:24`, `test_denied_experience.py:19`, `test_actions.py:56`, `interface_walk.py:21`, `playwright/test_learners_list_flow.py:18`, `invariants/test_config_authorisation.py:31` (docstring line 3 too), `invariants/test_organisation_isolation.py:33`.
- Tests importing `actions`/`filters`/`quick_views`/`reporting`: `test_actions.py:33-34`, `test_cohort_delete_action.py:35`, `interface_walk.py:20`, `invariants/test_reason_mixin.py:13-14`, `test_filters.py:19`, `test_quick_views.py:38`, `test_reporting.py:27`, `test_dashboard.py:26`.
- **String patch targets (silent breakage: `monkeypatch.setattr`/`mock.patch` on a moved module raises AttributeError or, worse, patches the wrong namespace):** `tests/test_views.py:4802,4856,4878,4882` (`...views.own_conversation_with`, `...views.send_message`), `:5543` (`...views.MAX_UPLOAD_BYTES`), `:3610,3641` (`...actions.grantable_roles`); `tests/test_actions.py:2494, 3388, 3591, 3709, 3729, 3755, 3786, 3804, 3952, 3994, 4137, 4357, 4394, 4664, 4749, 4809, 4971, 5059, 6136, 9202, 9366, 9424` (`...actions.<helper>`). These patch a name **where it is used**, so each must follow the function to its new module.

## 4. How FLS communicates breaking changes, and the shim question

Mechanism: `claude_plugins/fls-dev/commands/update_upgrade_notes.md:14-44` defines `upgrade_notes.md` per spec: YAML frontmatter flags (`requires_migrations`, `requires_template_review` + `changed_template_paths`, `requires_settings_change` + `changed_settings`, `requires_package_upgrade`, `requires_npm_install`, `requires_tailwind_rebuild`) plus markdown `## Breaking changes` and `## Manual steps`. Line 104: "Breaking changes — list anything a downstream project must change in their own code to stay working (renamed settings, removed template blocks, changed URLs, altered model fields)". Line 102: "Every name must resolve": each dotted path in the notes is checked against the tree (step 4, lines 109-126). `commands/concrete/update_fls.md:26-38` consumes these per spec. There is **no flag for renamed Python import paths**; they go in the prose Breaking changes section (and `requires_migrations: true` if a data migration is added).

Shim precedent in FLS (house style is mixed but leans to "re-export when cheap, for stable public names"):
- `freedom_ls/content_engine/course_icon.py:20-22`: "Re-export so existing callers importing IconResolutionError from this module continue to work without change", with `__all__`.
- `freedom_ls/reports/gather.py:8-9, 94`: "The report contract is re-exported here, so `from freedom_ls.reports.gather import CohortReportData` keeps working".
- `freedom_ls/form_engine/models.py:38`: re-exported `FormStrategy` "keeps ..." working.
- `freedom_ls/course_access/__init__.py:3`, `freedom_ls/form_engine/phone_numbers.py:26`: ergonomic re-exports.
- Counter-precedent for renames of persisted dotted paths: migration `educator_interface/migrations/0001_rename_unregister_bulk_runs.py` renamed two action classes with **no alias**, only a data migration, and the class names were not kept.
- `docs/` has no policy text on deprecation (no matches for deprecation/compat in `docs/`). There are no `DeprecationWarning` usages in `freedom_ls/`. A re-export shim for a whole module is not documented as house style anywhere; the precedents are small and module-local, justified by "existing callers".

Relevant facts for the decision: (a) the only known downstream project does not import any of these modules; (b) `views.py` is an internal module whose classes are configured in `interface_config` and reached through URLs, not a documented extension API (the skills describe panels as built from `panel_framework`, and no doc tells projects to import from `educator_interface.views`); (c) a shim does not solve the persisted `action_path` problem, and a `views.py` shim re-importing every panel would keep the circular-import tangle the refactor is meant to remove (`actions`/`filters`/`quick_views`/`reporting` import `OrganisationScopedRequest`/`interface_config` from `views`).

## 5. Recommendation

**Clean break, no compatibility shim for `views`/`actions`/`filters`/`quick_views`/`reporting`**, with these obligations in the specs:

1. Move every FLS-internal import and every string patch target (section 3 lists them) in the same spec that moves the code; no old import path left behind. Update `freedom_ls/qa_helpers/management/commands/qa_create_{course_cohort,direct_course}_registrations.py`, `educator_tags.py`, `urls.py`, and the docs/skill mentions in `claude_plugins/fls-dev/resources/testing.md:26` and `skills/educator-interface/SKILL.md:41`.
2. Keep stable: the `educator_interface` app label, `app_name`, every URL name and path, the template paths under `educator_interface/`, `educator_interface.urls`, and `notification_urls.bulk_run_table_url`. Then First-Class-LMS needs no change.
3. Add a **new data migration** in `freedom_ls/educator_interface/migrations/` (do not edit 0001) that rewrites `BulkActionRun.action_path` from `freedom_ls.educator_interface.actions.<Class>` to the new `freedom_ls.educator_interface.panels.<area>....<Class>` path for every moved action class, with a reverse mapping and a test modelled on `tests/migrations/test_0001_rename_unregister_bulk_runs.py`. Add `requires_migrations: true`. This is the one place a clean break can lose data (old runs fail `import_string` at `bulk_runs.py:28`). Also check that `BulkActionRun.action_name` / any other stored dotted path (grep `import_string`, `action_path` showed only these) needs no change.
4. If the team wants a softer landing for unknown extenders, a thin `views.py`/`actions.py` re-export is acceptable by precedent but should be time-boxed and is not recommended: it keeps the import cycle alive and does not cover persisted paths.

Upgrade notes (`upgrade_notes.md` for the specs) should say:
- Frontmatter: `requires_migrations: true`; template/settings/package/npm/tailwind flags `false`.
- Breaking changes: the modules `freedom_ls.educator_interface.views`, `.actions`, `.filters`, `.quick_views` and `.reporting` no longer define the panel, config, action, filter, quick-view and report classes; list the new `freedom_ls.educator_interface.panels.<area>.<module>` path for each public class (every name must be verified against the tree per update_upgrade_notes step 4). Anything a project subclassed, imported, or named in `mock.patch`/`monkeypatch` strings must switch to the new path. URL names, URL paths and template paths are unchanged. Note that `OrganisationScopedRequest` and `interface_config` have moved to the `common` area (if the specs place them there).
- Manual steps: run `uv run manage.py migrate` (rewrites stored bulk-action run paths); grep the project for `freedom_ls.educator_interface.(views|actions|filters|quick_views|reporting)` and update; "no action needed" for a project that only uses `include("freedom_ls.educator_interface.urls")` and INSTALLED_APPS (First-Class-LMS is in this case).

Sources: all are repo files cited inline; no web sources.

status: ok
