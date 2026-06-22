# fls-content-plugin: bundled Django-free validator

`fls-content-plugin/validate/` ships a standalone copy of `freedom_ls/content_engine/schema.py` + `validate.py`, patched to drop Django. Re-synced via `/update_claude_plugin_fls_content` (SDD task D4). Patches recorded in top-of-file comments and must be re-applied on every re-sync:
- schema.py: `Course._validate_icon_fields` body → `return self` (drops deferred django + icon_validation import).
- validate.py: `from .schema` → `from schema`; added `__main__` CLI shim.

Critical constraint: the bundled copy must stay Django-free and runnable offline. The implementation settled on `uv run --no-project --with pydantic --with pyyaml --with python-frontmatter python validate.py <path>` — note `--no-project`, used consistently in validate.py docstring/shim, validate-content.md, markdown-conversion SKILL.md, and the subprocess tests. (The plan/spec text omits `--no-project`; the implementation is correct to add it and is internally consistent.)

## Tooling gotchas for this plugin dir — NOW RESOLVED (as of branch course-editing-plugin)
- ruff per-file-ignores added: `fls-content-plugin/validate/validate.py` → T20; `fls-content-plugin/validate/tests/*.py` → S404,S603 (+ test defaults). pyproject.toml ~L176-178.
- mypy `exclude` now lists `fls-content-plugin/` (pyproject.toml L245), so `from schema import SCHEMAS` no longer trips "cannot find module".
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

Plan: `spec_dd/2. in progress/course-editing-plugin/2. plan.md` §6 (D3).
