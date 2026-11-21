# Research: UX patterns for affected-test selectors (topic `ux_patterns`)

Users here are developers and AI agents running `select_tests.py` and editing `[tool.test_tiers]`.

## What select_tests.py does today (read from the repo)

- Output is line-based: `tier: <tier>`, then one `why: <path> -> <outcome> (<reason>)` per changed path, then `command: ...`. Reasons already name the matching glob (`matches config/**`, `owning app X`, `from main; ...`). `first_match` exists so the reason names the glob.
- `ConfigError` is raised for malformed `[tool.test_tiers]` values (wrong type for `tooling`, `markers`, missing `glob`). Line 127 also raises; I did not check whether unknown top-level keys are rejected. The spec should check this.
- Config today: `none`, `escalation` (glob lists), `markers`, `[tool.test_tiers.memory]`, and a `[[tool.test_tiers.tooling]]` array of `{glob, tests}` tables.

## Patterns in other tools

| Tool | Pattern | Source |
|---|---|---|
| Pants | `--changed-since=<ref>` selects the directly changed targets. `--changed-dependents=direct` or `=transitive` is an explicit, opt-in widening. The default is no dependents. Selection flags work with `list`, which shows what a filter picks. | https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection |
| Nx | `nx affected -t test`. `nx show projects --affected` lists the selection without running anything. `--explain` reports why each project counts as affected. `--graph` previews the task graph. `--base`/`--head` set the range. | https://nx.dev/docs/reference/nx-commands (the page fetch was summarised by a small model, so check the `--explain` claim against the live docs before relying on it) |
| Turborepo | `--filter` syntax: `...pkg` selects dependents, `pkg...` selects dependencies, `^` leaves the target itself out, `!` excludes, `[ref]` is a git range. `--affected` is sugar for `--filter=...[main...HEAD]`. `--dry-run` (or `--dry=json`) lists the tasks with their `dependents` and `inputs`. `--summarize` writes a JSON run record. Experimental `affectedUsingTaskInputs` narrows selection by each task's `inputs` globs. A shallow clone can make everything look changed. | https://turborepo.dev/docs/reference/run |
| Bazel | `rdeps(universe, targets, depth)`: the optional depth caps the reverse-dependency walk (depth 1 gives direct dependents only). `somepath(S, E)` gives one concrete chain that answers "why is this included", and `allpaths` gives all chains. | https://bazel.build/query/language |
| Jest | `--findRelatedTests <files>` (a pre-commit hook use). `-o`/`--onlyChanged`, `--changedSince=<ref>`, `--lastCommit`. `--listTests` prints the selected files and exits. It needs a static dependency graph, so dynamic requires are missed. | https://jestjs.io/docs/cli |
| pytest-picked | `--picked` with `--mode=unstaged` (default) or `--mode=branch`, plus `--parent-branch`. The header prints the changed test files and folders it detected. It selects only test files that changed. | https://github.com/anapaulagomes/pytest-picked |

## Takeaways for this spec

1. **Widening is a named, bounded setting, and the default is narrow or off.** Pants' `direct`/`transitive` and Bazel's `rdeps` depth both make fan-out a value, not a fixed behaviour. This fits the "opt-in per project" answer. One option is a `[tool.test_tiers]` key such as `importer_depth` (`0` = none, `1` = direct, omitted = today's behaviour). Unset must keep the current wide default, per `answers.md`.
2. **Per-package override beats a single global limit for the "one widely imported app" case.** Turborepo exposes per-package control through filters. Nx and Pants have no per-package dependents knob, so this would be our own design. A table such as `[[tool.test_tiers.fanout]] app = "panel_framework"; depth = 1` or `mode = "own_tests"` mirrors the existing `[[tooling]]` `{glob, tests}` shape, so it reads like the rest of the config.
3. **Narrowing by importing module is the Jest/Bazel idea.** Selecting the importers of the changed module (a finer graph) is what `--findRelatedTests` does. It is more precise but costs more code and is wrong for dynamic imports. The tools above treat depth limits as the cheap option and module graphs as the accurate one. A depth limit is the lowest-risk first step.
4. **Explanation output is a solved pattern, and ours already matches it.** `why:` lines with the matched glob equal Nx `--explain` and Turborepo `--dry-run`. New rules should keep that contract. Each narrowed decision should say what was left out and which run still covers it, for example `owning app panel_framework; importers limited to depth 1 (36 more covered by the final full run)`. The idea file requires "No rule is dropped without naming the run that still covers the tests it selected", so that sentence belongs in the reason string, not only in docs.
5. **A dry-run or list mode matters for agents.** Jest `--listTests`, Pants `list`, `nx show projects --affected` and `turbo --dry` all print the selection without running. The existing output ends in a `command:` line, so the selector may already be a dry run. If so, say so in the docs. If not, add an explicit mode. A `--format=json` option (as in `turbo --dry=json`) would help agent consumers, but is not requested, so don't build it unless asked.
6. **Escalation to full should be loud and name the glob.** Existing output does this (`matches config/**`). Narrowing the `escalation` list should keep that line. Globs that fall out of `escalation` need a smaller target, not silence. Pants documents a caveat, that one lockfile change marks all users as changed. This is the same shape as `conftest.py`/`urls.py` escalation, so document the reason for each glob next to it in `pyproject.toml`, as the current comments do.
7. **Unmapped paths: prefer an explicit default over silent full.** Today an unknown path escalates to `full`. Turborepo and Nx avoid this by mapping by directory ownership. The spec's "`demo_content/` gets a rule" follows the existing `[[tooling]]` pattern. An optional catch-all key (for example `unmapped = "full" | "none" | [tests]`) is a possible later step, but is not requested.
8. **Validation.** Reject unknown keys under `[tool.test_tiers]` with a message that names the key and lists the valid ones. This catches a typo in an opt-in flag that would silently leave the wide default on. That is the main failure of an opt-in setting. Check whether the current `ConfigError` paths already do this, and add it if not. Validate types of new keys (depth must be a non-negative int, an app name must exist) with the same `ConfigError` style, and name the key in each message.
9. **Discoverability.** Comment each key where it is set (the repo already does this) and document the key list in one place. Printing the effective narrowing setting in the output (for example a `config:` line) lets an agent see whether narrowing was on. Turborepo's `--summarize` records how it read the config, which is the same idea.
10. **Limits to state in the spec.** Static-graph selectors miss dynamic imports (Jest) and shallow checkouts distort change detection (Turborepo). Both argue for keeping `implement_plan`'s final full run as the safety net, as the idea says.

## Suggested shape for the open questions

- **Fan-out narrowing:** an opt-in `[tool.test_tiers]` depth key, plus an optional per-app override table in the same style as `[[tooling]]`. Selection by importing module is the later, more precise step.
- **Escalation globs:** keep `config/**`, `site_aware_models/**` and `content_base/**` as `full`, since they are already justified in comments. Turn the `conftest.py`, `urls.py` and `factories.py` built-in escalations into smaller selections (the owning app plus its direct importers), with the reason line saying so. The built-in list lives in `ESCALATION_GLOBS` in the script. Narrowing it should itself be gated by the opt-in.
- **Fix-only runs:** an opt-in does not change the output shape, so it is a separate decision for the spec to take.

status: ok
