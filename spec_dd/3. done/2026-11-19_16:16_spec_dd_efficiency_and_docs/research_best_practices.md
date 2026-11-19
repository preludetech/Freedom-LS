# Research: best practices (spec_dd_efficiency_and_docs)

Inputs read: `idea.md`, `answers.md` (full suite at named checkpoints; `.drawio.svg`; flaky-test fixes land in the current branch; remove `address_pr_review` and list other candidates). I did not read the plugin source. Findings are general practice, with web sources. Where a source was only seen through search snippets, it says so.

## 1. Test selection in agentic and CI loops

### Findings
- **Run the full suite at gates, run targeted tests in the inner loop.** Fowler's and Google's long-standing model is a fast, selective loop for feedback and a full run before merge or release. This fits the answer "checkpoints named in the spec, targeted everywhere else". Tests cached by input hash (below) can make the full run cheap on repeat.
- **pytest-testmon** selects tests by coverage-based dependency tracking.
  - It stores state in `.testmondata` (relocatable with `TESTMON_DATAFILE`) and does not depend on version control.
  - Tests that failed last time always re-run.
  - It tracks project code, env vars, Python version and third-party package versions.
  - It does **not** track non-Python files (templates, static files, fixtures like txt or xml) or network services. A Django project with templates, HTMX and JSON fixtures can have a template-only change select zero tests. A full run at checkpoints covers this gap.
  - Flags: `--testmon-noselect` reorders but deselects nothing. `--testmon-forceselect` intersects with `-k`/`-m`. `--testmon-env` keeps separate data per Django settings. Using `-k`, `-m` or `--lf` forces noselect.
  - Selection can expose hidden inter-test dependencies. The docs say to fix the suite.
  - Source: https://testmon.org/
- **Alternatives.**
  - `pytest-impacted` uses a static AST import graph. A change to `conftest.py` makes all tests below it "impacted". See https://pypi.org/project/pytest-impacted
  - `pytest-picked` runs only the directly modified test files.
  - Static analysis over-selects and never under-selects through dynamic imports as often as coverage tools do, but it still misses non-Python inputs.
- **pytest cache flags** (built in, from pytest docs: https://docs.pytest.org/en/stable/how-to/cache.html; I did not fetch this page, so it is from memory).
  - `--lf` re-runs only the last failures.
  - `--ff` runs failures first and then everything.
  - `--nf` runs new tests first.
  - `--sw` (stepwise) stops at the first failure and resumes there.
  - Use `--lf` to confirm a fix, then a broader tier to confirm nothing else broke. `--lf` alone is not evidence of a green suite.
- **Cache a green result keyed by tree hash (content addressing).**
  - Bazel replays a test result when the test and all its inputs are unchanged. By default it caches passes only, and `--cache_test_results=no` forces a fresh run, which suits flaky debugging.
  - Sources: https://bazel.virtuslab.com/book/1~2~1/ and https://blog.engflow.com/2024/05/13/the-many-caches-of-bazel/
  - Aspect's post argues against re-running everything just because the cache hides the cost: https://aspect.build/blog/selective-testing-with-cache-diff.md
  - Applied to SDD: record `git rev-parse HEAD^{tree}` plus the test command and tier on a green full run, for example in a gitignored file or a git note. If the current tree hash matches a recorded green, skip the run. Because it keys on the tree and not the commit, a rebase that changes only history, or a commit that only reshapes history, still hits. Include in the key anything outside the tree that affects results: the lockfile is in the tree, but also the Python version and DB settings.
  - Cache only passes. Never cache a failure as a skip.
- **Path filters for docs-only diffs.**
  - Skip tests when every changed path is in an allow-list of non-code paths, such as `spec_dd/**` and `*.md`. Decide this from `git diff --name-only <merge-base>..HEAD`.
  - Be conservative: any path outside the list means run. Treat plugin command files (`claude_plugins/**`) as non-product only if no product code imports them.
  - In GitHub Actions, a workflow-level `paths-ignore` leaves required checks pending and blocks merge, because no job is ever created. Gate at **job level** with a "changes" job instead, or add a same-name stub. Mergify warns that a stub forced green can pass without testing anything. Sources: https://docs.github.com/en/enterprise-server@3.0/github/administering-a-repository/defining-the-mergeability-of-pull-requests/troubleshooting-required-status-checks , https://mergify.com/blog/path-filters-are-not-a-ci-gate , https://www.pantsbuild.org/blog/2022/10/10/skipping-github-actions-jobs-without-breaking-branch-protection
  - The same pitfall applies to the SDD rebase: "skip" must be an explicit recorded decision ("no code changed since green tree X"), not an absent result.
- **Rebase specifically.** After a rebase, a diff against the previous green tree tells you what changed.
  - If main moved only in docs or spec files and our branch is unchanged, the tree differs only in non-code paths and the earlier green holds.
  - If main's changes touch code, run targeted tests for the files the incoming commits touched, plus ours, and run the full suite only at the final checkpoint.
  - A rebase that conflicts, or that touches migrations, settings or dependencies, is a reason to escalate to a full run.

### Checkpoint strategy (suggested shape)
1. Inner loop (per subagent or task): tests for touched files or the touched app, with `--lf` to confirm fixes. Optionally testmon, with the non-Python caveat.
2. Per-phase tier: the touched app(s) plus anything importing them.
3. Pre-handoff (end of implement, before QA): one full run.
4. Post-rebase: path-filter and tree-hash check, then targeted or none.
5. Pre-merge or finish: reuse the pre-handoff green if the tree hash matches. Otherwise run the full suite once.
Every full run records its tree hash and result so later steps can skip it.

## 2. Token efficiency in skills, commands and agent prompts

- **Anthropic skill authoring guide** (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):
  - "Concise is key": the context window is a public good. Ask of each paragraph, "Does this paragraph justify its token cost?" and assume Claude already knows general concepts.
  - Keep the SKILL.md body **under 500 lines** and split into separate files as it nears that. This is a target, not a hard cap.
  - Progressive disclosure: only name and description load at startup. SKILL.md loads when relevant, and bundled files load only when read. Unread reference files cost nothing.
  - Keep references **one level deep** from SKILL.md. Nested references get partially read (`head -100`).
  - Give reference files over 100 lines a table of contents at the top.
  - Match specificity to fragility ("degrees of freedom"). Fragile, ordered operations get exact steps or scripts. Open-ended judgment gets short guidance.
  - **Prefer scripts for deterministic operations**: "save tokens (no need to include code in context)", more reliable, and only the output consumes tokens. State whether Claude should run or read the script. This applies directly to SDD steps such as "decide whether to run tests", "check the tree hash" and "find unpushed branches", which are better as one small script than as prose.
  - Use checklists and validate-then-fix loops for multi-step workflows. Use consistent terminology. Avoid offering many options. Put workflows that are large or branchy in separate files and load them by task.
  - Descriptions are always loaded, so they must be short, specific and third person.
  - Build evaluations first and write minimal instructions that close observed gaps.
- **Claude Code best practices** (https://code.claude.com/docs/en/best-practices):
  - "Keep CLAUDE.md short": every line costs attention on every task. Keep only what Claude cannot infer from code: exact test commands, misleading places, off-repo decisions, and anything corrected twice.
  - Anything that must happen every time belongs in a hook, not in CLAUDE.md. This is useful for the "where hooks fit" diagrams.
  - Subagents keep noisy output out of the main context, but each one costs its own tokens. A fresh subagent has to re-gather context, so it can be slower than inline work. Use them for parallelism, noisy output and independent review, not by default.
  - `/usage` breaks cost down by skill, subagent, plugin and MCP server, so measure before cutting.
- **Prompt caching** (https://platform.claude.com/docs/en/build-with-claude/prompt-caching; I did not fetch this page, so it is from memory): caching works on a stable prefix. Keep stable content (command prose, shared preamble) first and variable content (the spec text, the diff) last. A cached prefix is cheaper and faster to re-read. Editing text near the top of a frequently loaded file invalidates the cache for everything after it. Fanning out N workers that share an identical preamble benefits from this.
- **Practical audit approach**:
  1. Rank every command and skill by lines (`wc -l`) and by how often it loads.
  2. For the top files, split rarely used branches into one-level-deep reference files that the main file names.
  3. Delete explanations of things Claude already knows. Do not delete rationale that a human reviewer needs. Move it to the human-facing docs and diagrams.
  4. Pass subagents the paths to read, not pasted file contents. Ask workers for a short structured return, with detail written to files.
  5. Convert repeated shell snippets in prose into scripts.
- **Human readability.** The guidance is compatible with it: a short overview file, then one-level links and a diagram for the flow. Keep human-only prose (diagram explanations, rationale) in `docs/` or the commands README, which are not loaded into agent context.

## 3. Documenting multi-step agent workflows with diagrams

- **`.drawio.svg`**: a valid SVG that also embeds the draw.io diagram XML. It renders as an ordinary image in GitHub markdown (`![alt](path/x.drawio.svg)`) and can be reopened and edited in draw.io, VS Code (hediet.vscode-drawio) or the desktop app. Source: https://www.drawio.com/docs/integrations/github/diagrams-in-github-markdown/ (seen via search snippet). draw.io says SVG, PNG, HTML and XML formats are supported for embedding and editing. I did not verify a direct "edit" button on github.com for `.drawio.svg`. Plan on editing locally.
- **Conventions that help**:
  - One diagram per command (implement, rebase, finish-worktree and so on) plus one overview. Keep each readable at about 10 to 15 nodes. Use swimlanes for main agent, subagents, hooks and git or test tools, so the "who does what" and "where hooks fire" questions are answered by position.
  - Use consistent shapes: a decision diamond for branches such as "main moved?" and "docs-only?", and a distinct style for hooks and for test tiers, for example full suite in one colour.
  - Reference sub-workflows rather than inlining them. A "rebase" box links to the rebase diagram.
  - Add alt text and a one-paragraph text summary beside each image. This also helps accessibility and diffs, and agents can read the text.
  - Make the SVG self-contained: draw.io can embed fonts and images. Avoid external references that GitHub's image proxy would block.
- **Keeping diagrams in sync with text**:
  - The XML is stored in the SVG `content` attribute, so diffs are noisy, and compressed XML is unreadable in review. Save as **uncompressed** XML (File, Properties, uncheck Compressed) so git diffs show node text changes. See https://www.drawio.com/doc/faq/export-to-xml
  - Put the node and step names in the diagrams exactly as they appear in the command headings, so a grep for a step name finds both.
  - Add a README note (or a check) listing which command file each diagram covers. Add a PR checklist item "diagram updated" for command changes. A cheap automated check can extract label text from the SVG and confirm every step heading in the command file appears, or the reverse.
  - Keep the diagram's scope at the control flow. Details stay in the text so the two have different jobs and drift less.
- **Generating draw.io XML programmatically**:
  - draw.io publishes guidance for AI or script generation: use **uncompressed** `mxGraphModel`/`mxfile` XML. Two structural cells, `<mxCell id="0"/>` and `<mxCell id="1" parent="0"/>`, are mandatory. Content cells are `mxCell` with `vertex="1"` or `edge="1"`, and edges need valid `source` and `target` ids. Escape the XML properly when embedding it in an attribute or JSON. Sources: https://www.drawio.com/doc/faq/ai-drawio-generation , https://www.drawio.com/doc/faq/drawio-style-reference , https://www.drawio.com/docs/reference/diagram-generation/
  - For `.drawio.svg` from a script: write the `.drawio` XML, then either (a) export with the draw.io CLI (`drawio -x -f svg --embed-diagram -o out.drawio.svg in.drawio`; I recall the `--embed-diagram` flag but did not re-verify it), or (b) hand-build an SVG whose root has `content="<escaped mxfile>"` plus drawn shapes. Option (b) needs a draw.io round-trip check, because the search results did not confirm that the editor accepts an uncompressed `content` attribute in every version. Open one generated file in draw.io before committing to this route.
  - Writing the XML by hand has a layout cost, because coordinates are manual. A generator script with a small node and edge spec, or a one-off authoring pass followed by a visual check in draw.io, is more maintainable than editing coordinates in prose. Verify rendering by viewing the produced SVG.
  - Generated diagrams should still be hand-checkable in draw.io. Do not commit unreadable, generated, overlapping layouts.

## 4. Autonomous recovery in agent workflows

### Self-healing on recoverable git states
- **General principle** (Anthropic skill guide, "Solve, don't defer"): handle error conditions in the script rather than failing and leaving Claude to work it out. See https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices . Classify every stop condition as **recoverable and safe** (fix and continue), **recoverable but risky** (needs consent), or **terminal** (report).
- **Safe to auto-heal** (idempotent, non-destructive, reversible):
  - Branch has no upstream or is unpushed: `git push -u origin <branch>`. The user's idea says explicitly "just push the main branch".
  - Local branch behind its remote with no local divergence: fast-forward.
  - Main moved: fetch, rebase (or merge as the project prescribes), re-check, and loop. The idea says to keep going each time main moves.
  - Stale worktree metadata: `git worktree prune`.
  - Push rejected as non-fast-forward after a rebase: use `--force-with-lease` only on the feature branch the workflow owns. Never on main.
- **Needs a stop or consent**: conflicts that are not mechanical, diverged main with unpushed commits from someone else, force pushes to shared branches, deleting unmerged branches. The project's CLAUDE.md says to keep other processes' commits and not to rewrite history unless asked, so healing must never reset, squash or drop commits.
- **Bound the loop.** Cap the rebase-and-retry loop (for example N iterations) and re-check main each time. A moving main is normal, so the loop terminates when a pass finds main unchanged. If the incoming changes touch the same files, a migration or dependencies, treat it as a possible incompatible change and trigger a new QA run, as the idea asks. Define "incompatible" with concrete rules, for example overlapping files, migration conflicts or lockfile changes, so that agents decide the same way each time.
- **Report what was healed.** Log each auto-action in the final summary ("pushed main to origin"), so the human sees it without having been blocked.

### Flaky tests
- **Rerun to confirm, but as diagnosis.**
  - A single failure is not proof of flakiness. Re-run the failing test in isolation, then in the suite order, and with `-p no:randomly` or a fixed seed if a random-order plugin is installed.
  - If it passes in isolation and fails in the suite, suspect order dependence or shared state. If it fails consistently, it is a real regression.
  - If the failing test is unrelated to the diff, compare against main (a clean checkout or a worktree) to see whether it fails there too.
  - Cap retries and record the outcome. Retries must not be the fix: "your CI retries are hiding real bugs" (https://devops.com/your-ci-retries-are-hiding-real-bugs, via search snippet).
- **Common causes to hand the diagnosing subagent** (Fowler, https://martinfowler.com/articles/nonDeterminism.html): lack of isolation (shared DB state, singletons, order), asynchronous waits (bare sleeps), remote services, time, and resource leaks. For a Django and HTMX project, add DB transaction leakage, browser or Playwright timing, and factory randomness. These make a good checklist in the subagent's brief.
- **Quarantine versus fix.**
  - Fowler: quarantine is temporary. Put non-deterministic tests in a separate area so healthy tests stay trustworthy, cap it (a count or about a week), and "you still have to fix them soon". A flaky test is not a useful regression check.
  - The user's answer is to fix the flaky test in the current branch with a subagent. So the order is: confirm by rerun, then diagnose and fix, then verify with repeated runs (for example `pytest --count` or a loop of N, if `pytest-repeat` is available, or `--lf` several times). Quarantine, such as an explicit skip marker with a TODO and an issue, should be the fallback only if the fix is not found within a bounded effort, and it should be reported, not silent. Per project rules, TODO comments are never deleted.
  - Do not auto-skip or delete a test to get green. Treat that as a risky action that needs the user.
  - Scope guard: a flaky fix commit should be a separate, clearly named commit, so a reviewer can see it was not part of the spec's feature.
- Other sources (seen via search snippets): https://www.minware.com/guide/best-practices/flaky-test-quarantine , https://trunk.io/blog/eradicating-flaky-tests

## Source reliability notes
- Fetched directly: Anthropic skill best practices, Claude Code best practices, testmon.org, Fowler's non-determinism article.
- Search snippets only: GitHub required-check pitfalls (docs.github.com, Mergify, Pants), Bazel caching, draw.io GitHub embedding and AI generation pages, devops.com retries article, quarantine blogs. Check the wording of those before quoting.
- From memory (not fetched): pytest cache flags, prompt caching prefix guidance, draw.io CLI `--embed-diagram`.

status: ok
