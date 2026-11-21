# Answers: faster-test-runs-8-narrower-targeted-tier

Asked by `/sdd:start` before the spec was written.

- Q: Should the narrower selection be the `ds` selector's default for every project, or something a project switches on in `[tool.test_tiers]`? → A: Opt-in per project. The current wide behaviour stays the default; FLS turns narrowing on in `pyproject.toml`, and downstream projects are unaffected until they choose it. (asked up front)
- Q: How should a change in a widely imported app stop selecting every importing app's whole tests directory: module-level importers, an import depth cap, or a per-app setting? → A: Module-level importers. A per-module import graph built with `ast` (stdlib only); a change selects the test files whose imports reach the changed module, at any depth. (asked while research ran)
- Q: Should `finish_worktree`'s checkpoint use the narrower rules? → A: No. The checkpoint keeps today's wide rules, since it is the last local run before main; narrowing applies to batch-level runs only. (asked while research ran)
