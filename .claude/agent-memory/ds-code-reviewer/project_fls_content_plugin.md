# fls-content plugin: bundled Django-free validator

`claude_plugins/fls-content/validate/` ships a standalone copy of `freedom_ls/content_engine/schema.py` + `validate.py`, patched to drop Django. Re-synced via `/update_claude_plugin_fls_content` (SDD task D4). Patches recorded in top-of-file comments and must be re-applied on every re-sync:
- schema.py: `Course._validate_icon_fields` body → `return self` (drops deferred django + icon_validation import).
- validate.py: `from .schema` → `from schema`; added `__main__` CLI shim.

Critical constraint: the bundled copy must stay Django-free and runnable offline. The implementation settled on `uv run --no-project --with pydantic --with pyyaml --with python-frontmatter python validate.py <path>` — note `--no-project`, used consistently in validate.py docstring/shim, validate-content.md, markdown-conversion SKILL.md, and the subprocess tests. (The plan/spec text omits `--no-project`; the implementation is correct to add it and is internally consistent.)

## Tooling gotchas for this plugin dir
- ruff per-file-ignores: `claude_plugins/fls-content/validate/validate.py` → T20; `claude_plugins/fls-content/validate/tests/*.py` → S404,S603 (+ test defaults). pyproject.toml ~L182-184.
- mypy does **not** reach the validator by crawling. `uv run mypy .` never descends into `claude_plugins/fls-content/` because the directory name is hyphenated (not a valid Python identifier), so the `claude_plugins/(?!fls-content/validate)` lookahead in the pyproject `exclude` is only load-bearing for explicitly-passed paths. The pre-commit hook therefore runs `uv run mypy . claude_plugins/fls-content/validate` — 456 source files when the validator is covered, 453 when it is not. If someone "simplifies" that entry back to `uv run mypy .`, type regressions in the bundled copy go unnoticed.
- `from schema import SCHEMAS` resolves via mypy_path="." + explicit_package_bases; no duplicate-module clash.
- `--no-project` is required to prove Django-freedom and IS used everywhere. Verified.

## Verification outcomes (review of full branch vs main)
- schema.py bundled copy: verbatim except icon stub. Django-free. CORRECT.
- validate.py bundled copy: verbatim + `from schema import` + `__main__` shim. Django-free. CORRECT.
- All 15 MARKDOWN_ALLOWED_TAGS tags + attribute sets reproduced verbatim across widget-reference SKILL.md + 4 resources. MATCH settings_base.py exactly.
- Admonition base set (note,tip,important,warning,danger,key_takeaways,checklist[,default]) matches ADMONITION_TYPES keys. init.md template lists the 7 minus default. CORRECT.
- D4 tick-text byte-identical between update_claude_plugin_fls_content.md L60 and setup_todo_list.md L118. CORRECT.
- setup_todo_list renumber (§11 sync / §12 PR / §13 cleanup) internally consistent; README new Step 9 + renumber to Step 10 consistent.
- mdx_headdown used with default offset=1 → body `#`→H2 claim is accurate (markdown_utils.py L20).
- `__pycache__`/*.pyc present in worktree but gitignored (.gitignore L5) — not tracked, not a concern.

Plan: `spec_dd/3. done/2026-06-24_00:22_course-editing-plugin/2. plan.md` §6 (D3).
