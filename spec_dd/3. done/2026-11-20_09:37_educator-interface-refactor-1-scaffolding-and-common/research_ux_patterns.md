# Research: UX patterns for a pure-move refactor

Scope: no UI, URL, template or behaviour change. "Users" are educators (experience must not change) and developers (FLS maintainers, downstream projects).

## 1. Guaranteeing zero end-user-visible change

The educator interface is built from the panel framework (`Skill(fls-dev:panel-framework)`); `Skill(fls-dev:educator-interface)` promises placement of actions, sortable/filterable Audit log and History tables, the course outline, and course-name labels. A move that touches only Python module paths cannot alter these unless an import, patch string or registration changes. What to check:

- **URLs**: `reverse("educator_interface:interface", ...)` names and paths unchanged. `urls.py` is not touched by this spec. Check: `git diff` shows no change under `urls.py`, and the existing URL tests pass unedited.
- **Templates and Cotton**: no template path or `{% load %}` change. `templatetags/educator_tags.py` is the one template-facing module touched (`flag_badge`, `progress_status_badge`). The tag names and output must be identical; the existing tag tests are the guard.
- **HTMX fragments**: pickers, dialogs and bulk actions render fragments from `common/actions.py` helpers. Status codes (422 for validation errors) and fragment HTML must not change. Run the existing action tests unmodified apart from import and patch strings.
- **Denied experience**: `tests/test_denied_experience.py` asserts controls are hidden, not disabled, and stale posts 404/403, name an org admin to ask, and create nothing. It imports `OrganisationSectionConfig` from `views`; the moved file must pass with only that import repointed. Treat "assertions unchanged, only imports changed" as the rule for every moved test.
- **Stored data**: no migration (`makemigrations --check` must report no changes). `BulkActionRun.action_path` stores dotted paths of `@register_bulk_action` classes; the idea says none moves. Verify by grep that no stored dotted path names a moved module.
- **Mechanical proof a move is pure**: rename-only commits (git shows similarity), a test run of the whole suite before and after with the same pass count, and a grep that no old dotted path (including `mock.patch` strings) remains. Patch strings are the usual silent failure: a patch of the old path can still "work" by patching a now-unused name, so the test passes while no longer testing anything. Repoint each to the module that looks the name up.
- **TYPE_CHECKING to real imports**: the one change with runtime consequence. Import order and cycles are the risk; the cure is that `common/request.py` imports nothing from flat modules. Check with a fresh `python -c "import ..."` of each flat module and `manage.py check`.

General refactoring practice agrees: behaviour-preserving moves are best verified by an unchanged test suite and small separate commits (Fowler, Refactoring, "Move Function"): https://refactoring.com/catalog/moveFunction.html

## 2. Developer-experience patterns for layout

- **One place per concern**: `common/request.py`, `tables.py`, `badges.py`, `ids.py`, `filters.py`, `actions.py`, `bulk_actions.py`, `report.py`. Names say what is in them and match the concern names the sibling specs will use per area, so `panels/<area>/` and `panels/common/` read the same.
- **Predictable names**: reuse the existing framework vocabulary (`actions`, `filters`, `tables`) so a developer guesses the file. Avoid `utils.py`/`helpers.py` catch-alls; `common/` is allowed only because each file inside is single-concern.
- **Empty `__init__.py`, no re-exports, no shim**: one canonical import path per name, greppable. A shim would give two paths and hide who really depends on what. This suits downstream projects: a hard, loud ImportError beats a silent alias, and the release note names the new paths (see `research_downstream_imports.md`).
- **Mirrored tests**: `tests/panels/common/test_<module>.py` for `panels/common/<module>.py`; the repo's mirroring rule (`claude_plugins/django-stack/resources/testing.md`) and `mirroring_baseline.txt` enforce it. Create a test file only where a dedicated slice exists; do not add empty or token tests.
- **Cut slices, one commit per move**, so `git log --follow` and rename detection keep history; the old test files shrink and still mirror their modules.
- **Dependency direction**: `common` depends on nothing in sibling areas; areas depend on `common`. This is the point of the spec (lets area specs run in parallel with no cycle) and is a standard layered/"shared kernel" arrangement. Keep `common/` small: only code used by more than one area.
- **Leave the TODO block** at `views.py` 330-339 in place, per project rules.

## 3. Should QA be a smoke pass?

Yes, a short smoke pass, not a full QA round, because no UI code changes and the automated suite (including `test_denied_experience.py`) covers behaviour. Suggested smoke, one educator session:
1. Load the organisation dashboard and a Cohorts list (exercises `OrganisationScopedRequest`, tables, badges).
2. Open a learner page; open a course-picker dialog (Register for a course) and submit once (picker helpers, `CoursePickerMixin`, `EducatorReasonMixin`).
3. Run one bulk action on a table (bulk base, `interface_walk` path).
4. Open a progress report with its flag/status badges and over-limit message (`report.py`, `educator_tags`).
5. As a role without permission, confirm controls are hidden.
No screenshot comparison round is needed. Gate on: full test suite green, `makemigrations --check` clean, no leftover old-path strings. A smoke pass is the default for pure moves; extra effort goes into mechanical checks instead (see Fowler link above on tests as the safety net).

## Sources
- https://refactoring.com/catalog/moveFunction.html
- Local: `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`, `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `freedom_ls/educator_interface/tests/test_denied_experience.py`, idea.md.
(Web sourcing limited to one general reference; the rest is derived from the idea and local skills.)

status: ok
