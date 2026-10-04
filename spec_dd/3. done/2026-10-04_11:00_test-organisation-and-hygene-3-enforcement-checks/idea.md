# Enforcement checks for the two test-organisation rules

Spec 3 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Add a mechanical, gated check for each of the two rules from spec 1 (`ds:testing`): an app's tests
import only apps it depends on at runtime, and every test file maps to an existing source module.
Both checks run in pre-commit and CI. Both start from a baseline file listing today's violations, so
the checks are green the day they land. A cleanup spec's job (specs 4-15) is to delete its app's
lines from these baselines, never to fix everything at once.

## Why

Nothing in the repo checks either rule today, not pre-commit, not CI, not a documented review step.
A rule that only a human or agent remembers to apply at review time erodes the moment attention
drifts, which is the exact problem `idea.md` names. The owner wants both rules enforced by pre-commit
and CI, and was worried adding the checks would break pre-commit or CI before the cleanup specs have
run. The baseline is the answer to that: every violation `research_test_layout_audit.md` found is
captured in a baseline on day one, so the check only fails on a *new* violation, never on the
backlog. Specs 4-15 depend on this spec having already built that baseline and the mechanism for
shrinking it. This spec's output is their contract: a baseline file each of them can delete lines
from, and a check that fails if they add a line back.

## What is settled

- Depends on spec 1. Both rules, their names and their scope come from `ds:testing`. This spec only
  builds the check, not the rule.
- **Rule 2 (test imports only runtime deps)** is checked with `import-linter` `forbidden` contracts,
  one per app. `source_modules` is that app's `tests.*` subtree plus its root-level `factories.py`
  and `conftest.py` (mirroring `generate_app_map.py`'s own `is_test_path` classification).
  `forbidden_modules` is every other app's module path minus that app's own runtime deps, computed
  from `edges.runtime` in `claude_plugins/django-stack/scripts/generate_app_map.py`, the same AST
  walk that already renders `docs/app_structure.md`. Contracts are generated from that walk, not
  hand-written and hand-maintained. At 29 apps, hand-maintaining ~29 near-identical forbidden lists
  is the kind of thing that rots the day app 30 is added.
- The generator only ever regenerates `forbidden_modules`/`source_modules`. `ignore_imports`, the
  per-edge baseline, is a separately committed, **hand-edited** file, never regenerated. If the
  generator rewrote it from current-state test imports on every run, a careless new violation would
  get silently re-baselined instead of failing the check, and the baseline would never shrink. This
  mirrors the existing discipline in `docs/app_structure.md`'s own header: a new cross-app edge needs
  deliberate approval before it lands.
- `docs/app_structure.md`'s dashed edges (test-only) are exactly rule 2's violation inventory, and
  `generate_app_map.py` lives in the generic `django-stack` plugin, not `fls-dev`. Anything specific
  to FLS (the actual baseline file, the generated `pyproject.toml` contract entries) lives outside
  that script, so the shared plugin stays generic across projects that use it.
- **Rule 1 (test file maps to a source module)** follows spec 1's mapping, including subpackages
  mirrored as test subdirectories (`tests/templatetags/test_x.py` ↔ `templatetags/x.py`). It is checked
  with a small custom script, because no
  existing Python tool checks source/test path mirroring (import-linter, tach, pytestarch and
  pytest-archon all check import relationships, not file-path correspondence). It gates only "every
  test file's target must exist", the case of a source module renamed or deleted with its test file
  left behind. It does not gate "every source module has a test file": that direction has an
  unacceptable false-positive rate (`apps.py`, `urls.py`, `admin.py`, settings-shaped modules and
  re-export `__init__.py`s legitimately have no 1:1 test file) and stays out of scope per the
  effort's assumptions.
- Rule 1's exemption list: `conftest.py`, `factories.py`, underscore-prefixed private helper modules
  (an existing repo convention), `stub_*.py` files, and the `tests/playwright/`
  subtrees (a Playwright test exercises a flow across several source modules, not one file, so 1:1
  mirroring is the wrong model there by design). Integration-style test files whose name doesn't map
  to one production module get an explicit per-file exemption, not a structural carve-out.
- Rule 1 gets its own baseline file, same shrink-only discipline as rule 2's `ignore_imports`: every
  currently-orphaned or currently-misplaced test file is listed once, generated from a first run of
  the checker, then only shrunk.
- Both baseline files are how this spec hands off to specs 4-15: each cleanup spec's contract with
  this one is to delete its own app's lines from both baselines as it fixes the violations they
  record, never to add to them, and never to regenerate a baseline wholesale.
- Both checks are wired as `repo: local` pre-commit hooks, matching the existing `mypy` hook's shape
  in `.pre-commit-config.yaml` (`uv run lint-imports` for rule 2; `uv run python` plus the rule 1
  script). They are mirrored into the `lint` job of `.github/workflows/tests.yml` alongside the
  existing `ruff check`/`ruff format --check` steps, the same belt-and-braces pattern already used
  there, so a `--no-verify` commit or a fork PR without pre-commit installed still gets caught.
- Both checks are dev-time only: `import-linter` and any custom script dependency go in the `dev`
  group (`[project.optional-dependencies].dev` / `[dependency-groups].dev` in `pyproject.toml`),
  never `[project].dependencies`. The generated import-linter config and both baseline files live at
  the repo root, not inside `freedom_ls/`, so they're excluded from the package build the same way
  `spec_dd/`, `claude_plugins/`, `demo_content/` and `config/` already are. Neither check runs inside
  pytest or needs a marker. They're static/CLI tools outside pytest collection, so a downstream
  project installing `freedom_ls` never invokes either of them against its own code.
- Whichever of spec 2 and this spec lands second wires both checks into `implement_plan`'s review
  step, per the effort's ordering decision. If spec 2 lands first, this spec does that wiring. If
  this spec lands first, spec 2 does it.
- Spec 4 depends on this spec landing first, because it is the first cleanup spec to delete baseline
  lines and it edits `freedom_ls/conftest.py`, a file every app's tests load.

## Open until the spec

- **How the check and `docs/app_structure.md` learn the two edges the import graph cannot see.**
  This spec owns the decision. Spec 1 settles the rules: a model relation declared by string label
  (`"content_engine.Course"`, `settings.AUTH_USER_MODEL`) is a runtime dependency on the app owning
  the model, and any app's tests may use `accounts`' `UserFactory` because the user is framework-level.
  The spec decides the mechanism: `generate_app_map.py`'s AST walk adds runtime edges for
  string-label relations it finds in `models.py`, and the generated contracts allow
  `accounts.factories.UserFactory` everywhere, or some other shape. `course_recommendations`'
  `content_engine` edge is a string-label relation today. Specs 6, 9 and 12 depend on the answer.
- The concrete file format for each baseline (a TOML block in `pyproject.toml` for `ignore_imports`
  versus a sibling file; the shape of rule 1's baseline), whatever is easiest for a cleanup spec to
  hand-edit and diff-review.
- Whether the `generate_app_map.py` extension is a new function reusing its existing
  `find_apps`/`compute_edges` or a sibling script driven by the same functions. Reuse is recommended
  so the existing longest-path-first module matching (which avoids a short app name falsely matching
  a longer sibling path) isn't reimplemented and its bug class reintroduced.

## Out of scope

- Fixing any existing violation. That is specs 4-15's job: deleting lines from the baselines this
  spec creates.
- Gating "every source module has a test file", rule 1's high-false-positive direction, stays
  advisory at most, never a hard gate.
- Wiring the checks into `implement_plan`'s review step, unless spec 2 has already landed. That
  ownership follows the "whichever lands second" rule, not a fixed assignment.

## Resources

- `research_test_rule_enforcement.md` (moves into this spec's directory): the full tool comparison
  (import-linter vs. tach vs. pytestarch/pytest-archon vs. a custom script), the contract-generation
  design, the false-positive analysis for both rules, and the downstream-distribution reasoning.
- `research_test_layout_audit.md` §1 and §5, staying in the parent
  `spec_dd/1. next/test-organisation-and-hygene/` (specs 4-15 also read it): the current rule-2
  test-only edges per app and the rule-1 `management/commands/` gap that both baselines start from.
  Regenerate the actual baseline contents against the live tree when this spec is built rather than
  transcribing the audit's numbers. They are illustrative of the shape and scale, not a snapshot to
  copy in.
- `claude_plugins/django-stack/scripts/generate_app_map.py`: the existing AST walk and edge
  classification (`is_test_path`, `compute_edges`) this spec extends rather than reimplements.
- `docs/app_structure.md`: the generated dependency graph; its dashed edges are rule 2's violation
  inventory.
- `.pre-commit-config.yaml`: the existing `repo: local` `mypy` hook is the shape both new hooks match.
- `.github/workflows/tests.yml`'s `lint` job: where both checks mirror into CI.
