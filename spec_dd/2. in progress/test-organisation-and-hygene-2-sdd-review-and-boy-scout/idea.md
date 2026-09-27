# SDD review and boy-scout for test organisation

Spec 2 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first. It holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Wire the two test-organisation rules from `test-organisation-and-hygene-1-testing-standards` into
`implement_plan` itself. New work is then written and reviewed to the standard, instead of adding to
the pile the other twelve specs clean up.

Three pieces:

1. `implement_plan`'s batch worker gets its own agent file in `sdd`, replacing today's bare
   `subagent_type: "general-purpose"` spawn. `implement_plan` tells it to load the project's testing
   skills, here `ds:testing` and `fls-dev:testing`, before it writes any code.
2. A test-organisation review checks each batch's test placement and cross-app test imports against
   `docs/app_structure.md`. It uses the same fan-out shape as `plan_from_spec.md` Step 6.
3. A boy-scout agent runs per batch, scoped to the files that batch's own `[batch N]` commit touched.
   It tidies test organisation in them and flags code that is plainly broken, without fixing it.

## Why

`implement_plan.md`'s batch worker is a bare `general-purpose` subagent today. It has no `skills:`
slot, so the two rules reach it only if a skill happens to auto-trigger. Nothing in the SDD flow
reviews implemented code or tests once a spec is built. `plan_from_spec` Step 6 reviews the plan
text, not the code it produces, and `/ds:security-review` covers only security. Without this spec,
every future spec builds up the same disorganisation the other twelve specs in this effort exist to
remove.

## What is settled

### Loading the testing skills

- The two rules and the conftest/fixture/factory layering material live in `ds:testing`. This spec
  does not restate or re-derive them. It only loads and checks them inside `implement_plan`.
- The project names its testing skills in a new `## Testing Skills` section of
  `.claude/sdd/config.md`. The section is blank by default and follows the pattern of
  `## Rebase Hooks` and `## Vocabulary Sources`. `implement_plan` reads it at depth 0 and tells
  every agent it spawns for this work to invoke those skills first. No file that `sdd` ships names
  `ds` or `fls-dev` skills, so the coupling `claude_plugins/sdd/README.md` records does not grow.
  Frontmatter can't do this job. `skills:` is a fixed list, and the `Agent` tool takes no skills
  when it spawns an agent. See `research_agent_skill_preload.md`.
- The batch implementer and the boy-scout each get a new agent file in `sdd`, because both need
  `Bash` and `Edit` and no named agent can be widened when it is spawned. The reviewer is a plain
  `sdd:sdd-worker`, because it only reads and writes one `.sdd-work/` file. See
  `research_agent_file_shape.md`. The per-spawn `model: "sonnet"` in `implement_plan` still
  applies.

### The review

- The review is a fan-out unit inside `implement_plan`. One `sdd:sdd-worker` checks both rules,
  since both read the same diff against the same table, and writes a `.sdd-work/` file with a
  `status:` footer. It is not a new `todo.md` line or an entry in `setup_todo_list.md`'s template.
- It checks the diff against the Runtime-deps and Test-only-deps columns of `docs/app_structure.md`,
  the table `plan_structure_review.md` already parses. It invents no new dependency data.
- It runs after each `[batch N]` lands and before that batch's boy-scout, so later batches never
  build on a misplaced test. `implement_plan`'s Step 3 adds one final check over the whole spec's
  diff, which catches patterns only visible across batches, such as the same new cross-app edge
  appearing three times.
- The batch's own organisation mistakes always get fixed, and the boy-scout's budget does not cap
  them. A fix agent corrects a mechanical finding in its own commit. A finding that needs a
  judgement call, such as whether one app should now depend on another, goes to the user at once
  through `AskUserQuestion`.

### The boy-scout

- It is scoped to exactly one batch's own `[batch N]` commit, found from that commit alone
  (`git show --name-only`). It never runs a wider scan. Tool grants cannot enforce that file list,
  so the brief carries the list and a mechanical check confirms the boy-scout's commits stayed
  inside it.
- It fixes test organisation only: moving or renaming a touched test file to mirror the app
  hierarchy, removing an existing cross-app test dependency, splitting a touched test module that
  has grown too big. It changes no assertions and touches no file outside the batch's commit.
- Its guardrails are the effort's assumption, not this spec's to reopen. Only mechanical,
  behaviour-preserving moves are allowed. The budget is about 3 test files moved and 1 cross-app
  dependency removed per branch. It covers mess that was already in the touched files, and it is
  counted from earlier boy-scout commit subjects in `git log`, so it survives crashes and rebases.
  Past the budget, the boy-scout records a follow-up against the matching cleanup spec in the
  roadmap (specs 4-15), or a new idea under `spec_dd/1. next/` once no cleanup spec covers that
  app.
- It makes its own labelled commits, separate from the batch's commit: the move in one commit and
  the accompanying edit in the next, so git's rename detection survives a rebase.
- Every commit a batch produces carries its number. The implementation stays `[batch N] <summary>`.
  A review fix is `[batch N review-fix] <summary>`. The boy-scout's pair is
  `[batch N boy-scout] move <what>` then `[batch N boy-scout] edit <what>`. The existing resume
  scan matches `[batch N]` exactly, so the follow-on commits don't confuse it, and
  `pre_step_rebase` still reads a batch's progress from its number. Its wording about `[batch N]`
  commits needs updating to say a batch can now have more than one commit.
- Resume keys on these prefixes, never on SHAs, because `pre_step_rebase` rewrites every SHA. A
  batch can now be implemented but not yet reviewed or tidied, and resume runs only the missing
  step. See `research_review_cadence.md`.

### Talking to the user, not the PR

- Everything goes to the user in the conversation. Nothing extra goes into the GitHub PR.
- Broken code the boy-scout flags goes to the user as soon as that batch's boy-scout returns, up to
  four items per `AskUserQuestion`, each with the boy-scout's recommendation. The user picks one of
  three answers. "Not a bug" adds a code comment at that spot saying why, so nobody flags it again.
  "Fix it now" and "record a follow-up" do what they say. The boy-scout never suppresses its own
  flag. See `research_flagged_bug_reporting.md`.
- `boy_scout_record.md` in the spec directory keeps a short record of what came out of the
  boy-scout and the review: what was tidied, what was deferred and where the follow-up went, each
  flagged item with the user's verdict, and any review fixes. `implement_plan` appends to it per
  batch and commits it with the batch's follow-on commits. At the end of `implement_plan` the user
  gets a summary of it in the conversation.

### Spec 3

- Whichever of this spec and `test-organisation-and-hygene-3-enforcement-checks` lands second makes
  the review run the other's checks. If spec 3's pre-commit and CI checks land first, this spec's
  review calls them. If this spec's review lands first, spec 3 wires its mechanical checks into it.

## Out of scope

- Pre-commit or CI enforcement of either rule (`test-organisation-and-hygene-3-enforcement-checks`).
- Cleaning up any app's existing tests (specs 4-15).
- The boy-scout fixing anything beyond test organisation, or any big-bang cleanup.
- Gating "every module has a test", or reviewing general test quality (assertions, redundancy,
  coverage).

## Resources

All in this spec's directory:

- `research_sdd_standards_hooks.md`: how each SDD phase loads skills today and where the new
  agent files, the review fan-out and the boy-scout step hook in.
- `research_boy_scout_rule.md`: the Boy Scout Rule sources and the size, commit-shape and
  rebase-safety guardrails.
- `research_agent_skill_preload.md`: what Claude Code allows for preloading skills, and the options
  for naming skills per project.
- `research_agent_file_shape.md`: tools, model tier and naming for each of the three agent roles,
  and why tool grants cannot enforce the file limit.
- `research_review_cadence.md`: per-batch and end-of-spec cadence, resume states, how the budget is
  tracked, and how all of this interacts with rebase.
- `research_flagged_bug_reporting.md`: where flagged bugs go and who decides, including suppression
  practice and how agents that suppress their own findings go wrong.

Also `claude_plugins/sdd/commands/implement_plan.md`, `plan_from_spec.md` Step 6,
`claude_plugins/fls-dev/agents/qa-bugfixer.md`, `claude_plugins/sdd/skills/claude-code-authoring/`
and `docs/app_structure.md`.
