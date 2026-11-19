# Research: UX patterns for SDD process docs and run feedback

Topic: `ux_patterns`. Spec: `spec_dd_efficiency_and_docs`.
Users: developers driving `claude_plugins/sdd` from the terminal, and humans reading its docs.

Sourcing note: I did not fetch pages in this run. The patterns below come from established practice and well-known documentation. The URLs are the canonical references for each point, but they are unverified here. Treat any specific claim about a tool's behaviour (draw.io, GitHub rendering) as something to confirm with a small spike before the spec relies on it.

## 1. Process-documentation patterns for developer workflows

### 1.1 One overview plus one diagram per command
- Use a two-level hierarchy, as in the C4 model's "zoom in" idea. Level 1 is a single overview of all commands and how they chain (start, spec, plan, implement, finish). Level 2 is one diagram per command showing its internals. Do not put sub-steps in the overview.
- Each per-command diagram answers one question: "what happens when I run this?" Keep it to one screen, about 15 to 25 nodes. Past that, split out a sub-diagram. A good split candidate is a shared step such as the rebase workflow, which many commands call. Draw it once and reference it from the others as a named "call" box.
- A shared step that is drawn once and linked from each caller answers the idea's question "when do things call the rebase workflow?". A caller table can back it up. The table has columns step, called by, and condition.
- Refs: https://c4model.com/ (zoom levels), https://diataxis.fr/ (keep how-to, reference and explanation distinct, so diagrams go in explanation or reference and not inside step-by-step instructions).

### 1.2 Swimlanes for actors
- Lanes suit this process because several actors hand work to each other. Suggested lanes, top to bottom:
  1. Human (approvals, questions)
  2. Orchestrator (main agent)
  3. Subagents (workers, one box per fan-out, drawn as a stacked or multi-instance shape)
  4. Hooks (pre-commit, session or tool hooks)
  5. Git / CI (commit, rebase, push, merge)
- Time flows left to right. The lane shows who does the step. Arrows crossing lanes are the handoffs, so label them with the artifact passed (for example "plan.md", "report file").
- Mark fan-out and fan-in explicitly: a fork bar, N parallel worker boxes, then a join bar. This is where "main agent splits into subagents" becomes visible.
- Ref: BPMN pools and lanes, https://www.omg.org/spec/BPMN/2.0/ and the draw.io swimlane shapes, https://www.drawio.com/blog/swimlane-diagrams.

### 1.3 Hook points and decision diamonds
- Hooks are events, not steps. Draw them as a distinct shape and colour (for example a hexagon or a dashed-outline box in the Hooks lane) attached to the step that triggers them with a dashed connector. Label with the hook name and what it can do (block or warn).
- Decision diamonds hold a question, with labelled exits ("yes" and "no", or the condition). Give every diamond an else-branch. For this spec the high-value diamonds are:
  - "Diff touches only spec files?" (skip the test run)
  - "Main moved?" (rebase and continue, or stop only if the change is incompatible)
  - "Tests flaky?" (diagnose in a subagent, fix on the current branch)
  - "Main pushed?" (push it and carry on)
- Put the terminal states (done, stopped, needs human) in a visibly distinct shape. "Stops and asks the human" should be rare and obvious on the diagram. That shows how far the "solve it yourself" principle is followed.
- Mark test runs with a badge for the tier (targeted, package, full). The diagram then shows the test cadence the spec decides on, and a reader can see at a glance where the full suite runs.

### 1.4 Legend
- Every diagram needs a legend, either embedded in the diagram or as a shared legend image reused everywhere. Legend entries: lane colours, step box, decision diamond, hook marker, fan-out bar, "calls another workflow" box, test-tier badge, terminal states.
- Reuse one shape and colour vocabulary across all diagrams. Copy the legend from a shared template file instead of redrawing it per diagram.
- Also give a text alternative: a numbered list or table under each diagram with the same steps. This helps accessibility, search, diffing, and the agents that read the markdown and cannot see the image.
- Ref: general diagram guidance at https://www.drawio.com/doc/ and Google developer docs style on images and alt text, https://developers.google.com/style/images.

### 1.5 Keep diagrams next to the doc they illustrate
- Colocate the diagram file with the doc: `commands/implement.md` sits beside `commands/implement.drawio.svg`, or in a sibling `diagrams/` folder one level down. Avoid a distant central `docs/images/` folder, because it drifts out of date.
- Same base name as the doc, so a rename or deletion touches both.
- Embed at the top of the doc (after the one-line summary) with alt text and a link to the source file for editing.
- Add a short "diagram last verified against" note, or a PR checklist item, so a command change prompts a diagram change. A cheap check is a test or hook that fails when a command file changes and its sibling diagram does not. Weigh that against noise, since not every doc edit changes the process.

### 1.6 draw.io `.drawio.svg` in markdown
- `.drawio.svg` is a normal SVG that also carries the draw.io diagram XML in it. It renders as an image anywhere SVG does, including GitHub markdown. Opening it in draw.io desktop or diagrams.net edits the full diagram. A separate export step is not needed.
- Embed with plain markdown: `![Implement flow](implement.drawio.svg)`. Use a relative path.
- Practical cautions to verify in a spike:
  - Text in shapes should use plain SVG text. If "Allow HTML labels" is on, draw.io may write `foreignObject`, which GitHub's SVG sanitiser and some viewers drop, so labels disappear. Disable HTML labels, or use the export option that includes a text fallback (the "Include a copy of my diagram" option and the "Text settings: Plain" choice are worth checking).
  - Dark mode: set a background, or use colours that work on both light and dark GitHub themes. A transparent SVG with black text vanishes in dark mode.
  - Diff noise: the embedded XML is compressed by default. Turn off compression (File, Properties, Compressed) so git diffs are reviewable and merges are possible.
  - Size: keep the file small and the canvas cropped. Set a sensible width so it is legible without zooming. Wide swimlanes are hard to read on a narrow page. Prefer vertical flow with horizontal lanes only if the page width demands it.
  - Links inside the diagram: draw.io supports links on shapes, and relative links to the docs of called workflows are useful. They may not be clickable when GitHub renders the SVG as an `<img>`.
  - Agents cannot read the SVG semantically. Always keep the text equivalent (see 1.4).
- Refs: https://www.drawio.com/blog/embed-diagrams-in-markdown (or search "draw.io svg embed markdown"), https://www.drawio.com/doc/faq/export-to-svg, https://github.com/jgraph/drawio-github (draw.io GitHub integration notes), https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#images.
- Alternative worth one line in the spec: GitHub renders Mermaid code blocks natively, which is text, diffable and readable by agents (https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams). The answers file already chose `.drawio.svg`, so Mermaid is only a fallback or a source for the text equivalent. Mermaid has no swimlane support, which is a reason the `.drawio.svg` choice is sound for this need.

## 2. CLI and agent run feedback patterns

Principle: a long run feels clear when the user can always answer "what is it doing, why, how far along, and what will it do next". The best-known guidance is the Command Line Interface Guidelines (https://clig.dev/) and the GitHub CLI and Cargo output conventions.

### 2.1 Progress steps
- Announce a numbered plan once at the start: "Step 1/6: rebase on main". The user then knows the total and can estimate the wait. Update with a one-line status per step on completion.
- One line per state change, not a stream. Fixed prefix tokens make the output scannable and greppable (for example `[ok]`, `[skip]`, `[fix]`, `[stop]`).
- For long fan-outs (many subagents), show a counter ("3 of 5 workers done") and name which are outstanding. Avoid silent gaps longer than a few minutes.
- Show elapsed time per step. Cargo, pytest (`--durations`) and GitHub Actions all do this, and it helps users judge when something is stuck and where the time goes. That is directly relevant to the idea's "this takes really long" complaint.
- Refs: https://clig.dev/#output, https://docs.github.com/en/actions (job step timing display), https://doc.rust-lang.org/cargo/ (build status line).

### 2.2 State why a step is skipped
- A skipped step with no reason looks like a bug or a forgotten step. Always print the skip and the rule that caused it, in a fixed shape:
  `[skip] full test suite: diff touches only spec_dd/ files (no code changed since last green run at <sha>)`
- A good skip message names: the step, the decision rule, the evidence (changed files, a commit SHA), and how to override ("run with --full to force").
- Same idea as CI path filters (GitHub Actions `paths-ignore`, Bazel and Nx "affected" runs, which print which targets were affected and why). Nx's "affected" output is a good model: it lists what was selected and the reason. Ref: https://nx.dev/ci/features/affected and https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#onpushpull_requestpull_request_targetpathspaths-ignore.
- Record skips in the final summary too, so the user sees "what did NOT run" in one place. This matters for trust: skipping must never look like passing. Use distinct words: "skipped" is not "passed".

### 2.3 Report test tier and duration
- Name the tier in every test line: `tests (targeted: 14 files, 38s): pass`, `tests (full suite: 2,140 tests, 7m12s): pass`.
- Show what the tier was chosen for, in a few words: "targeted: changed apps = learner_interface".
- Record "last full green" (SHA, time) in a visible place (the todo or a status file). Later steps can then say "full suite already green at <sha>, only spec files changed since, skipping". This gives the skip rule in 2.2 evidence that a human can check.
- At the end of a run, print a table of test runs: tier, count, duration, result, trigger. It makes repetition visible: if the full suite appears four times, the table shows it. It also serves as the audit trail for the "sensible checkpoints" decision in the answers file.
- On failure, show the first failing test names and the re-run command, not the whole log. Link or point to the log file for the rest.
- Refs: pytest durations https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration, pytest-testmon / pytest-picked style selection for targeted runs https://testmon.org/.

### 2.4 Auto-recovery messages versus stopping
- Rule of thumb: recover automatically when the fix is safe, reversible and within the task's scope. Stop when the action is destructive, outside scope, ambiguous, or the same recovery already failed. This follows the idea ("just push the main branch", "rebase when main moves").
- Auto-recovery message shape: say what was wrong, what was done, and the result, in one or two lines, at a lower severity than errors.
  `[fix] main not pushed to origin: pushed main (3 commits). Continuing.`
  `[fix] main moved (abc..def): rebased, no conflicts, changes are spec-only so QA not repeated.`
- Bound the retry. State the attempt count ("flaky test, attempt 2 of 3") and what escalates. An unbounded silent loop is worse than a stop.
- For flaky tests: report that a test failed, then passed on a rerun in isolation, with the test id. Never hide it. Flakiness is a finding that should land in the summary even after a fix (the answers say the fix lands on the current branch, so name the commit).
- When stopping, make the stop message actionable. State: what blocked, what was tried, the exact state left behind (clean tree, branch, SHA), and the one or two options for the human. "Stopped: rebase conflict in X, tried auto-resolve (failed), tree is mid-rebase; run `git rebase --abort` to restore, or resolve and rerun." A stop with no next step is the "randomly stops" complaint in the idea.
- Distinguish severities visually and in wording: info, recovered (`[fix]`), skipped (`[skip]`), needs human (`[stop]`). Keep the set small.
- Refs: https://clig.dev/#errors (make errors actionable, put the important part last), https://clig.dev/#robustness-guidelines.

### 2.5 End-of-run summary
- Finish with a short fixed-format summary: what was done, what was skipped and why, what auto-recovered, what needs the human. Put the most important line (success, or the blocking item) last, where the eye lands in a terminal. This matches clig.dev's advice to put key information at the end of output.

## 3. Readable for humans, compact for agents

### 3.1 Summary first (inverted pyramid)
- Start each doc with a two or three line statement: purpose, when to use, and what it produces. Humans decide in seconds whether to read on. Agents can stop loading once they have what they need.
- Use progressive disclosure. The main command file holds the decision-critical flow. Detail (long examples, rare edge cases, rationale) lives in linked reference files that are read on demand. Anthropic's own skill guidance recommends this structure: a short entry file that links to detail loaded only when needed (https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices, section on progressive disclosure and keeping SKILL.md under about 500 lines).
- Order sections by decision frequency, not by chronology of the author's thinking.

### 3.2 Tables over prose for rules
- Rules with conditions (test tier by trigger, when to rebase, when to stop) compress well into a table: columns condition, action, reason. A table is about one third the tokens of the equivalent paragraphs and is easier to scan and diff. Use bullets for short independent rules.
- Keep the "why" short and in one place, not repeated in every step. Repeated rationale is the cheapest token saving that costs no quality.
- Avoid ASCII art and long decorative formatting in agent-facing text. A diagram image costs a human nothing in tokens and costs the agent nothing if the agent file does not load it. That argues for diagrams living beside the doc as separate files, not inlined in the instruction text the agent loads. The text steps stay as the agent's source of truth.

### 3.3 Link out, do not copy
- One canonical home per rule. Other docs link to it ("see rebase workflow") instead of restating. Duplicated blocks across commands drift and cost tokens every time more than one is loaded. This is also the existing project convention: avoid repeating code.
- Use stable heading anchors and relative links so an agent can fetch just the section it needs.
- Share common steps as a single skill or include (the rebase workflow, the test-tier policy), referenced by name from each command.

### 3.4 Compaction techniques that do not cost quality
- Cut the explanations of things the model already knows (what git rebase is). Keep project-specific decisions and constraints. Anthropic's skill guidance says "assume Claude is already smart" and to challenge each paragraph's token cost.
- Prefer imperative, specific rules with a concrete example over long hedged paragraphs. One good example beats three sentences of description.
- Remove dead branches: steps no one uses (such as `address_pr_review`) cost tokens on every load of the index. Audit descriptions too, because command and skill descriptions are loaded into context every session even when the body is not.
- Measure first. Count tokens per file (a simple character-count or tokenizer script) and rank. Fix the top few files that dominate. Re-measure after to confirm the saving, and compare behaviour on a few real runs so quality is not traded away.
- Keep a "human layer" and an "agent layer" with one source: summary, diagram and rationale for humans in the docs, and the compact step table the agent loads. They must not diverge, so generate or cross-check where possible, or keep the rationale in a clearly marked section the agent can skip.
- Refs: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices, https://www.anthropic.com/engineering/writing-tools-for-agents, https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents.

## 4. Suggestions for the spec (UX-level only)

1. Diagram set: one overview plus one per major command, `.drawio.svg`, uncompressed, plain-text labels, colocated with the command doc, shared legend, text step list under each. Lanes: Human, Orchestrator, Subagents, Hooks, Git. Shared "rebase workflow" diagram referenced by callers.
2. A fixed status vocabulary in command output (`[ok]`, `[skip]`, `[fix]`, `[stop]`), one line each, always with reason and, for tests, tier plus duration.
3. A "last full green at SHA" marker, plus a skip rule that cites it. This turns the "don't use tests like a hammer" goal into something the user can see and check.
4. Stop messages must state state-left-behind and next options. List the cases where stopping is allowed, and make everything else auto-recover with a bounded retry.
5. End each run with a summary table: test runs (tier, duration, trigger), skips with reasons, auto-fixes, items for the human.
6. Docs: summary first, rule tables, link to one canonical home per rule, measure tokens per file before and after.

## Risks and open questions
- Skipped tests that look like passes erode trust. The wording must keep them distinct.
- Diagrams drift from the commands. Decide whether a lightweight check is worth it.
- GitHub rendering of `.drawio.svg` text needs a spike (HTML labels, dark mode).
- Whether Claude Code's terminal output can show structured prefixes consistently is up to the command prose. Nothing here needs new tooling.

status: ok
