# SDD Plugin Configuration

The spec-driven-development (sdd) workflow is enabled for this project. Product-specific SDD steps
and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here.

## Worktree Scripts

Paths are relative to the project root. Leave a value blank if this project has no such step.

- Setup script: .claude/fls-dev/scripts/install_dev.sh
- Teardown script: .claude/fls-dev/scripts/dev_db_delete.sh

## Vocabulary Sources

Where this project's domain vocabulary is defined, most authoritative first. Ideas, research notes,
specs and plans use these words rather than coining new ones.

- `.claude/skills/domain-glossary/SKILL.md` — **start here.** The FLS domain nouns, the words that are
  already taken, and where each one is defined.
- `freedom_ls/*/models.py` — the canonical nouns. Model class names and field names are a spec's
  nouns.
- `docs/product/` — concept-level prose. Start at `docs/product/README.md`;
  `docs/product/learner-tracking.md` carries the progress vocabulary.
- `.claude/skills/brand-guidelines/SKILL.md` §Terminology — the Use/Not table (learners not students,
  content not curriculum, extend not customise). **Copy-scoped**: it governs UI text, docs and prose,
  not Python identifiers. **"Learner" is the settled word in code too** — the `student_*` app
  namespace is legacy naming being migrated, so never introduce a new `student_*` name.
- `docs/app_structure.md` — the canonical app names.
- `claude_plugins/fls-content/skills/` — the author-facing content vocabulary.
