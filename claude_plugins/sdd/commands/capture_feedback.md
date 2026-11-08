---
description: Capture feedback on how a page looks, behaves or reads into the rule files the project configures and the spec documents it overrides, then commit
allowed-tools: Read, Edit, Write, Grep, Glob, AskUserQuestion, Skill, Agent
argument-hint: "[the feedback; blank takes the latest feedback in this conversation]"
---

Runs at depth 0. The skill does the work; this command is the by-hand handle for when the skill
did not fire on its own, and it commits what the skill changed.

## Step 1: Capture

Invoke `sdd:capture-feedback` with the `Skill` tool, with `args: "$ARGUMENTS"`, and follow it to
the end. It ends with `changed: <paths>` or `changed: none`.

## Step 2: Commit

With `changed: <paths>`, delegate to `sdd:sdd-mechanic`: read
`${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md` and follow it with `<summary>`:
`capture feedback: <n> rules`, staging exactly those paths and nothing else. `changed: none`
commits nothing.

## Step 3: Report

Repeat the skill's report, then the commit hash or "no commit".
