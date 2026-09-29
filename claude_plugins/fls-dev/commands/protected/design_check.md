---
description: Helper — screenshot the running app for the design states a slice builds
allowed-tools: Read, Glob, Grep, Bash, Agent, ToolSearch, mcp__plugin_ds_playwright__*
---

This is a helper command, followed inline by the design check in `claude_plugins/sdd/commands/implement_plan.md`. It runs at **depth 0**, inline, on the caller's model and tool grants, so its `Agent` spawn is legal.

Inputs from the caller: `<spec-dir>`, `<plan-path>` and the design state ids. A design state id is a `<section-id>__<artboard-id>__<width>` triple from the plan's design transcription.

Rules 1, 3 and 4 of `claude_plugins/fls-dev/commands/do_qa.md` apply throughout this file: the Playwright MCP server to use, the batching rules that keep a `Bash` call and a Playwright call out of the same turn and keep every `Agent` spawn solo, and passing paths rather than payloads between steps. Read them there rather than here.

## Step 1: Server

Start the server and confirm it is serving this branch the way `do_qa.md` Steps 3 and 4 do (an unused port, a solo backgrounded `runserver`, the `debug-branch-badge` check). Log in, when a state needs it, the way `do_qa.md` Step 5 does.

Done when the badge names the current branch.

## Step 2: Data

For each design state, read its "how to reach it" line in the plan's design transcription. Set up the data it names the way `do_qa.md` Rule 2 does: `fls-dev:qa-data-helper`, as a solo `Agent` spawn.

Done when every state's "how to reach it" line resolves to a URL that renders the state's data.

## Step 3: Screenshots

For each design state: resize to its width by 900, navigate, and take a full-page `browser_take_screenshot` with this absolute `filename`:

```
<project root>/.sdd-work/design_check_<section-id>__<artboard-id>__<width>.png
```

After the first screenshot, confirm the file exists at that path. `do_qa.md` Step 7 explains why: the unpinned server has written custom filenames elsewhere. When the file is missing, find where it went, delete it, and return `status: failed` naming the location.

Done when every state has a file at its path.

## Step 4: Clean up

Run this on every path out of this file, including a Playwright error partway through Step 3.

```
.claude/ds/scripts/kill_runserver.sh <PORT>
```

## Return contract

```
status: ok|failed · screenshots: <state-id>@<width>=<path>; … · reason: <short>
```
