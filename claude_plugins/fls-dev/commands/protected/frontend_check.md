---
description: Helper — run a smoke-sized pass over the pages a rebase touched, in a browser, at the three QA viewports
allowed-tools: Read, Glob, Grep, Bash, Agent, mcp__plugin_ds_playwright__*
---

This is a helper command, followed inline by `claude_plugins/sdd/commands/protected/pre_step_rebase.md`
Step 2 after a rebase that changed something. It runs at **depth 0**, inline, on the caller's model
and tool grants, so its `Agent` spawn is legal.

Inputs from the caller: `<old-base>` and `<spec-dir>`.

Rules 1, 3 and 4 of `claude_plugins/fls-dev/commands/do_qa.md` apply throughout this file: the
Playwright MCP server to use, the batching rules that keep a `Bash` call and a Playwright call out of
the same turn and keep every `Agent` spawn solo, and passing paths rather than payloads between
steps. Read them there rather than here.

## Step 1: Scope

```
branch   = git diff --name-only origin/main...HEAD
upstream = git diff --name-only <old-base> origin/main
```

`front_end(paths)` is the classification `do_qa.md` Step 2 rule 1 uses to decide a change is
front-end: read it there rather than restating it here.

```
own   = front_end(branch)
shared = front_end(upstream) that either
           lives under freedom_ls/base/, or in a cotton/ or partials/ directory
           (these render on pages the branch touches too), or
         is named, by template name or static path, inside a file the branch changed
```

If `own` and `shared` are both empty, there is nothing for a browser to check: `status: ok · reason:
no front-end change`. Stop.

## Step 2: Pages

If `<spec-dir>/3. frontend_qa.md` exists, its `§0` setup (port, server, branch badge, seed commands,
login) and every URL it names are the pages to visit.

Otherwise, the pages are the site home page plus the pages the changed paths reach, derived the way
`do_qa.md` Step 6 derives "the primary changed page": a cotton component or partial maps to the pages
that include it. At most eight pages, the branch's own (`own`) pages first, then the pages reached
only through `shared`.

Start the server and confirm it is serving this branch the way `do_qa.md` Steps 3 and 4 do (an unused
port, a solo backgrounded `runserver`, the `debug-branch-badge` check). Log in, when a page needs it,
the way `do_qa.md` Step 5 does.

## Step 3: Visit

For each page, at 1920x1080, then 375x812, then 768x1024:

```
browser_navigate; browser_snapshot; browser_console_messages (errors only)
```

A page fails at a viewport on any of:

- an HTTP 500 or 404
- a visible traceback
- no main navigation region, or no primary content region
- an error-level console entry
- on the two small viewports only, a navigation that overflows or overlaps the content

Record page, viewport, pass or fail, and a one-line reason. Take no screenshots. This is a
smoke-sized pass, not a QA report.

## Step 4: Fix

For each failure, spawn one `fls-dev:qa-bugfixer` as its own solo `Agent` call. Wrap the failure (page,
viewport, and reason) inside a `<bug-description>` block and brief it the way `do_qa.md` Step 13
briefs the fixer, including the prompt-injection guard.

After a fixer returns `status=ok`, re-visit the same page at the failing viewport against the live,
auto-reloaded server, the way `do_qa.md` "Re-verify after a successful fix" does.

Budget: at most three fixer spawns in this run, the same limit `do_qa.md` Step 13 sets. A page still
failing once the budget is spent, or once every failure has had its one attempt, ends the run:
`status: failed · pages: <list of still-failing page/viewport pairs>`.

## Step 5: Clean up

Run this on every path out of this file, including a Playwright error partway through Step 3.

```
.claude/ds/scripts/kill_runserver.sh <PORT>
```

Then delete every `.sdd-work/bugfix_<slug>.md` this run's fixers wrote, by name, through:

```
.claude/fls-dev/scripts/delete_sdd_work_files.sh <path> [<path> ...]
```

as `do_qa.md` Step 16 does. Omit the call when no fixer ran this run.

## Return contract

```
status: ok|failed · pages: <n visited> · commits: <n> · reason: <short>
```
