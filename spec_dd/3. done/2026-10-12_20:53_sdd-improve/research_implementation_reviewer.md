# Research: the implementation reviewer

Owner ask (`spec_dd/2. in progress/sdd-improve/idea.md:14-16`): the reviewer that checks changes as `/sdd:implement_plan` goes should also check comments/docstrings (spec numbers slip in) and that tests are to standard.

## How batches are reviewed today

**Headline finding: there is no per-batch reviewer.** The idea's premise ("we have a subagent that reviews changes as we go") does not match `claude_plugins/sdd/commands/implement_plan.md`. Nothing in it spawns a reviewer. The owner may mean the batch sub-agent itself, or the Design check, or `ds:code-reviewer` run by hand. The spec needs to say it is *adding* a reviewer, not widening one.

What happens today:

- Batching: one batch per vertical slice, in plan order (`implement_plan.md:36`). Completion marker is a `[batch <id>] <summary>` commit; resume scan by anchored regex on `git log` (`:38-43`).
- Implementer: one `Agent` per batch, `subagent_type: "general-purpose"`, `model: "sonnet"` (`:45`). It implements the steps, runs plan verifications, runs the `targeted` test tier via `claude_plugins/sdd/commands/protected/run_test_tier.md` (`:46-49`), then commits itself with `uv run git commit` and returns `status: ok|failed|blocked` + `reason:` (`:50`).
- Only quality instruction in the brief (`:52`): comments, docstrings and test names must not mention spec, plan, research, QA plan or their numbers (`§4b`, `spec 6`, `this slice`, `batch 3`, `a later spec`, `Phase 2`, `spec_dd/` paths); "If the project has a skill for writing code comments, the batch follows it." This is an author-side rule with no independent check. It names no test standard at all.
- Reaction to status (`:63-66`): `ok` -> verify commit, next; `failed` -> reset, retry up to 2 with prior error; `blocked` -> `AskUserQuestion`.
- Only review-like step: the Design check (`:70-82`), depth 0, only for slices with `**Design states:**`. It compares screenshots to the plan's design checklist. It reads hook `Design check` from `.claude/sdd/config.md:13-15`. A miss spawns a `design fix <n>` batch (max 2, then `blocked`). It never looks at code, comments or tests.
- Step 3 (`:87-94`): full tier via `sdd:sdd-mechanic`, success criteria check, a general-purpose fix sub-agent for unmet criteria, final commit.
- What nothing looks at: code diff quality, comments/docstrings, test quality, architecture, security. `ds:code-reviewer` exists but is not called from any sdd command (grep of `claude_plugins/sdd` finds no reference; it is run by the user directly or by `fls-dev/commands/update_product_docs.md`).

Agents available:

| Agent | Tools | Model | Fit as reviewer |
|---|---|---|---|
| `ds:code-reviewer` (`claude_plugins/django-stack/agents/code-reviewer.md:22-23`) | Glob, Grep, Read, WebFetch, WebSearch (no Bash, no git) | opus, `memory: project` | Wide brief (security, perf, SOLID, plan alignment, `:63-114`). Its prompt tells it to run `git diff`/`git status` (`:36-44`) but it has no Bash, so it cannot. Opus cost per batch. Has a comment-leak bullet at `:113` already, and "Missing tests" / "test coverage and quality" at `:76,:101`, but only as nice-to-haves with no concrete test rules. This is the "too wide" shape the owner dislikes. |
| `sdd:sdd-worker` (`claude_plugins/sdd/agents/sdd-worker.md:7-8`) | Read, Glob, Grep, WebFetch, WebSearch, Write | sonnet | Read-only plus one `Write` to a path in the prompt, non-interactive, status footer. Cannot run git. Good fit for a bounded judgement review if the orchestrator hands it the diff or the file list. |
| `sdd:sdd-mechanic` (`claude_plugins/sdd/agents/sdd-mechanic.md:9-11`) | Bash, Read, Edit, Write, Glob, Skill | haiku, effort low | Can run `git diff` and `grep`. "No design judgement" (`:20`). Fits a grep pass only. |
| `general-purpose` | everything | sonnet via per-spawn param | The implementer. A reviewer here is not read-only. |

## The comment standard, as checks

Source: `.claude/skills/code-comments/SKILL.md` (the project skill; description line 3, rules `:17-190`). Rules a reviewer can apply to a diff:

1. **Planning-document pointers** (`:17-77`): section numbers, spec/slice/batch/phase numbers, relative references, QA references, `spec_dd/` paths, in comments, docstrings, template comments, CSS headers, test docstrings and test names (`:19-20`, `:81`). Fix: replace with the fact it stood for; delete if only a citation.
2. **Implementation-history narration** (`:94-103`): `# §4c additions`, "the block below preserves ...". Delete.
3. **Restating the code** (`:108-130`), including listing Tailwind classes in template comments. Short region labels are fine.
4. **Test group dividers** headed with a section number (`:134-145`).
5. **Protected comments** (`:164-178`): `TODO` / `@claude` are never deleted. A stale citation inside one is replaced by the concrete detail. A reviewer must not report "delete this TODO".
6. Regression test names/docstrings describe the broken behaviour, not the bug ID (`:79-90`).

Greppable (run only on lines the diff added; scope `*.py`, `*.html`, `*.css`, `*.js`, plus test names):

- Section marks: `§`
- Numbered planning nouns: `\b[Ss]pecs? [0-9]`, `\b[Ss]lice [0-9]`, `\b[Bb]atch [0-9]`, `\b[Pp]hase [0-9]` (false positives exist, see Evidence)
- Relative planning phrases: `\b(this|a later|the next|the) (spec|slice|batch)\b`, `\bspec requires\b`, `\bper (the )?(spec|plan)\b`, `\bplan §`
- QA IDs: `QA [Bb]ug|QA §|\bQA bug\b|qa_report|frontend_qa`
- Paths: `spec_dd/`, `\b[0-9]+[a-z]?\. (spec|plan|frontend_qa)\.md`
- Test-name leaks: `def test_.*(spec|slice|qa_bug|bug_[0-9])`
- Class-list comments in templates: `\{% comment %\}.*\b(bg|text|border|px|py|rounded)-`

Needs judgement: restating the code; implementation-history narration without a number ("added for the new flow", "now also"); "could a stranger act on this?"; whether a TODO rewrite kept the detail. Roughly: item 1 is about 90% greppable, items 2 and 3 are judgement.

## The test standard, as checks

Sources: `claude_plugins/django-stack/skills/testing/SKILL.md` (generic, `:18-129`), `claude_plugins/fls-dev/skills/testing/SKILL.md` (FLS overlay), `claude_plugins/django-stack/resources/test_tiers.md` (how to run, not what to write). Rules checkable on a diff:

Greppable on added test lines:

- Placement and mirroring: `<app>/<module>.py` -> `<app>/tests/test_<module>.py` (`ds testing:22`; FLS `:17-33`). Already enforced by pre-commit `test-mirroring` (`.pre-commit-config.yaml:80-84`) and `lint-imports` (`:74-79`). Not a reviewer concern.
- Factories only: no `\.objects\.create\(` / `get_or_create(` in test bodies (`ds testing:29`). Regex: `\.objects\.(create|get_or_create|bulk_create)\(`. Exceptions need judgement (`course_with_topic` fixture is `.items.create`, FLS `:77`).
- `reverse()` not hardcoded URLs (`:30`): `client\.(get|post)\(\s*["']/`.
- Site-aware: a test touching a site-aware factory/model must take `mock_site_context` (FLS `:83-96`): test functions using `*Factory()` with no `mock_site_context` and no fixture that depends on it. Heuristic only, needs a fixture-chain look.
- Marker taxonomy (FLS `:98-120`): allowed markers are `playwright`, `fls_internal`, `ci_only`, `dev_tooling`, `weasyprint`; unmarked = portable. Greppable: any `pytest.mark.<x>` outside `{django_db, parametrize, playwright, fls_internal, ci_only, dev_tooling, weasyprint, skipif, skip, xfail, usefixtures, filterwarnings}`; `pytest.mark.order` is banned (`ds:33`); new `fls_internal` marks are a "reach last" smell (judgement, FLS `:120`).
- Hygiene in non-browser tests (`ds:31,:107`): no `if|for|try` in the body. Regex on test bodies, excluding `playwright`-marked files.
- Weak assertions: a test whose only assertion is `status_code == 200` (`ds:137`). `assert .*status_code == 200$` as the sole assert; 302 hits in 52 files today, so only flag when it is the only assertion.
- Config / copy assertions: `assert settings\.`, CSS class assertions (`assert "bg-`), long string literals (`ds:112-114`).
- Names: `def test_` lacking a `<subject>_<condition>_<expected>` shape is not greppable; names containing "and" (`ds:87`) are: `def test_\w*_and_\w*`.
- Mocks: more than two `patch(`/`mock` per test (`ds:95`); `patch("freedom_ls.` targets own code rather than a boundary.
- Auth: `patch.*request.user` (`ds:125`).
- Time: `datetime.now()`/`timezone.now()` assertions without `time_machine` (`ds:35`).
- Network: sockets blocked by `pytest-socket` anyway.
- Missing `__init__.py` in new test dir (FLS `:25`): file-existence check.

Needs judgement:

- Tests behaviour not implementation; tautological expected values (`ds:47-83`); one behaviour per test; AAA order; negative-existence assertions; validation tested both ways; parametrise vs separate; "is the assertion meaningful"; mocks at boundaries only; a wide-scope fixture handing back mutated state; whether new behaviour in the diff has a test at all.

Bottom line: "to standard" is a short cheap list (maybe 8 mechanical rules) plus 5 judgement questions drawn from `ds:testing` "Best practices" and its anti-pattern cheatsheet (`:131-142`). A reviewer can be told to apply the skill's own cheatsheet table and nothing wider.

## Evidence of leaks

Snapshot of `freedom_ls/` (`*.py`, `*.html`, `*.css`, `*.js`) with the combined regex `§|[Ss]pecs? [0-9]|this slice|[Ss]lice [0-9]|QA [Bb]ug|spec_dd|[Pp]hase [0-9]|later spec|this spec\b|batch [0-9]`:

- 5 raw hits, all in one file, all false positives: `freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py:37,40,44,47,50` ("Phase 1..5" are real algorithm phases). 0 hits for `§` and `spec_dd` anywhere.
- Looser search `(#|""").*\b(spec|slice)\b` in `*.py`: 71 raw lines in 13 files, nearly all legitimate ("a spec dict", "slice of the query string", "CSS spec" at `freedom_ls/accounts/email_utils.py:226`). One real leak: `freedom_ls/qa_helpers/toast_views.py:6` ("Remove once the toast spec QA is complete"; also a `QA-TEMP:` header, line 1).
- So the committed tree is almost clean. The rule in the skill plus the `implement_plan.md:52` brief line, plus past cleanup, have worked at the end state. Two readings: (a) leaks are now rare, so the widened review is cheap insurance; (b) the grep is only a snapshot and cannot show how many leaks a reviewer *would have caught in flight* before a later cleanup. Counting that needs git history (`git log -S` / `git log -G'§|spec [0-9]'` on `freedom_ls/`), which this unit did not have Bash for.
- Planning-side evidence that the problem existed: 10+ done plans mention `code-comments` or a comment-cleanup step (e.g. `spec_dd/3. done/2026-10-11_06:57_educator-interface-6-cohort-administration/2. plan.md`, `.../2026-10-10_08:57_user-communication-3-messaging-policy/2. plan.md`, `.../2026-10-02_07:10_new-content-type-articles/idea.md`). They show leaks were found and fixed after the fact, as extra work in later specs. I did not open them to count instances.
- Test-quality baseline today: `\.objects\.create(` in test files: 42 hits in 26 files (`freedom_ls/learner_management/tests/test_models.py` has 5, `freedom_ls/accounts/tests/management/commands/test_setup_initial_prod_data.py` has 5); `status_code == 200` line-ending asserts: 302 hits in 52 files (`freedom_ls/course_applications/tests/test_views.py` 10). Many are legitimate (`create` on non-factory-able through models, 200 alongside other asserts), so these regexes need "added lines only" scoping and a judgement pass, not a blanket gate.
- Note the idea's other premise, that `ds:code-reviewer` already carries the comment check: it does (`code-reviewer.md:113`), but only if someone runs it. No sdd command does.

## Recommended shape

Recommend a hybrid of (i) and (ii), with (iii) ruled out for now:

**Add one post-batch review step in `implement_plan.md`**, between the batch returning `ok` (committed) and starting the next batch. Two stages, both bounded to the batch's own diff (`git diff <batch-commit>^..<batch-commit>`; the `[batch <id>]` commit is the unit, which suits the resume scan too):

1. **Mechanical stage (`sdd:sdd-mechanic`, haiku).** Run the greppable regexes from the two sections above on added lines only; return `path:line: <rule>: <text>` lines or "none". No judgement, no edits. This also matches the owner's "typically too wide, wastes time" worry: it is seconds and tokens measured in hundreds.
2. **Judgement stage (`sdd:sdd-worker`, sonnet, read-only plus one Write).** Only runs if the diff has `*.py` / `*.html` comments or test files. Brief = the two skill files by path (never pasted), the diff's file list, the mechanical stage's output, and a closed checklist: the comment-skill's six rules and the test skill's cheatsheet rows plus the five judgement questions. It is told explicitly not to review security, performance, architecture or design, to flag nothing in unchanged lines, and to return findings in a fixed shape. Writes its list to a file in the spec dir (e.g. `<spec-dir>/batch_review_<id>.md`, overwritten per batch; deleted on pass, like the Design check screenshots) and ends with `status: ok|failed|blocked`.
   - Alternative to save a spawn: fold stage 1 into the same sonnet worker. Cost is a few extra tokens. Folding is simpler to specify; keeping the mechanic means the greps cannot be "reasoned away" by the reviewer. I would keep it as one worker and have the orchestrator tell it the regexes, unless token cost matters more than reliability. Decide in the spec.

**Findings flow into the existing fix-batch mechanism**, mirroring the Design check (`implement_plan.md:76-82`): findings list -> spawn one fix batch (`general-purpose`, `sonnet`) -> commits `[batch <id>] review fix <n>` (counts as the batch's commit for the resume scan, like `design fix`) -> `targeted` tier runs (`:68`) -> re-run the review on the fix commit only. Cap at 2 fix batches like the Design check, then continue with the leftovers recorded in the Step 3 summary instead of `blocked`, so the run does not stall waiting for the user (the goal of the whole idea). Fix batches never ask the user (matches `:72`).

Why not the others:

- (i) alone, widening `ds:code-reviewer`: opus, memory on, no Bash, wide brief; this is the "too wide" review. It is also a `ds` agent and `sdd` cannot depend on its project rules directly. Leave it for the human-run review, and leave `:113`.
- (iii) pre-commit hook: already the right home for pure greps and costs nothing in tokens. What exists: `.pre-commit-config.yaml` has ruff, mypy, bandit, `app-map-fresh`, `lint-imports`, `test-mirroring`; `.claude/ds/scripts/` has `select_tests.sh` and friends but no comment or test linter. A `ds`-level script is not blocked by the generic rule if it reads its patterns from config, but regexes on prose (`this slice`) will false-positive on legitimate code (`sync_role_permissions.py:37`, `email_utils.py:226`) and block commits of unrelated work by other processes in a shared worktree (`CLAUDE.md` Committing note). A blocking hook is the wrong failure mode. Suggest a later optional follow-up: a non-blocking `scripts/check_comment_leaks.py` that the mechanic stage calls, so the regex list lives in one file, not the command text. That removes the duplicate list in two places.

**Generic/overlay rule.** `implement_plan.md` is generic and must not name `code-comments` or `fls-dev:testing`. It already reads hooks from `.claude/sdd/config.md` by section (`Rebase Hooks`, `Design Hooks`, `Test Hooks`, `Vocabulary Sources`). Propose a new section:

```
## Review Hooks

- Comment standard: .claude/skills/code-comments/SKILL.md
- Test standard: claude_plugins/fls-dev/skills/testing/SKILL.md
```

Hook names: `Comment standard` and `Test standard`. Each is a path to a skill file (the same kind of value `Test tiers` holds at `.claude/sdd/config.md:19`). `Test standard` could list more than one file (comma-separated or bullets); in FLS the overlay skill says "read `ds:testing` first" (`fls-dev testing:9`), so one path suffices. A blank value or absent section skips that half of the review ("review skipped: no Comment standard hook" recorded for the Step 3 summary, as the Design check does at `:74`). The greppable regex list is generic planning-noise vocabulary (spec, slice, batch, QA bug, section signs, `spec_dd/`), which is SDD's own vocabulary, so it belongs in the command or a sdd resource file, not in config. The marker whitelist is project-specific: it lives in the project's test skill, so the mechanic should only run the project-neutral greps (`.objects.create(`, control flow in tests, `status_code == 200` as the sole assert) and leave marker checks to the judgement stage reading the skill.

Also update `implement_plan.md:52`: keep the author-side rule, but add the test standard to the brief by hook (same "if the project has a skill..." wording) so the implementer avoids the leak first; the reviewer is the second line.

Fail-safe points the spec should state:

- review runs per batch, on that batch's commit only, never on the whole branch;
- reviewer does not run tests (the tier already did);
- a `TODO` / `@claude` flagged for a citation is rewritten, never deleted (skill `:164-178`);
- reviewer output counts are logged for the Step 3 summary ("review: N findings, M fix batches");
- the review must not review Design-check screenshots; Design check order relative to the review needs a decision (suggest: review first, Design check on the final fixed state).

## Open questions for the owner

1. The idea says a reviewer subagent already exists. `implement_plan.md` has none. Do you mean (a) add a new per-batch reviewer, or (b) widen `ds:code-reviewer` that you run by hand? This research assumes (a).
2. After the reviewer finds issues, should the run always spawn a fix batch, or fix only findings above a threshold (comment leaks and test-rule breaks yes; style nits no)? Recommended: both checks produce fix batches, nothing else does.
3. When fixes remain after 2 attempts: continue and report in the final summary (recommended, keeps the run going) or stop `blocked` like the Design check?
4. One sonnet worker for greps and judgement, or a haiku mechanic first? Mechanic-first is more reliable on the greppable items; one worker is simpler.
5. Is a non-blocking script for the leak regexes (shared with a future manual `/ds:` command or CI) wanted now, or later?
6. Is the test standard's scope "the skills only" (recommended), or should the reviewer also check that each new behaviour in the slice has a test (a coverage-of-plan check that touches plan alignment, which is wider)?

status: ok
