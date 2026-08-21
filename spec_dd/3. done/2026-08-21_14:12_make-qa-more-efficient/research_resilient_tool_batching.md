# Research: Resilient Tool Batching in Claude Code QA Flows

This document investigates the cascade-cancel problem identified in the `make-qa-more-efficient` idea file: "Parallel tool batches get cascade-cancelled when any one call is rejected, and `rm -rf`/`cd` trip a security hook — this caused a lot of apparent churn early on."

The findings below are grounded in the actual hook scripts, `settings.json`, and `do_qa.md` in this repo, plus Claude Code documentation and tracked issues.

---

## 1. Parallel Tool-Batch Cancellation Semantics

### What actually happens

When Claude Code issues multiple tool calls in a single assistant turn (a "batch"), and **one call is rejected or blocked** — whether by a permission prompt that is denied, a PreToolUse hook returning exit code 2, or a runtime tool error — Claude Code automatically cancels all remaining sibling calls in the same batch with the error "Sibling tool call errored".

This is a confirmed, filed bug (issue #22264). The sibling calls are not evaluated; they are dropped outright. Claude then must re-read context and retry the cancelled calls individually, adding extra round-trips, extra tokens, and extra latency.

### How a PreToolUse hook exit 2 fits in

The `security-guard.sh` hook is registered as a PreToolUse matcher for `Bash|Write|Edit`. When it exits with code 2, Claude Code:
1. Blocks the matched tool call (correct intended behaviour).
2. Returns the stderr text to Claude as an error message.
3. In the current model behaviour (tracked in issue #24327), Claude frequently pauses and waits for user input rather than autonomously retrying — treating a hook block as if it were a user denial.

When the blocked call was part of a batch, all sibling calls are already cancelled by the time Claude sees the error. This produces the churn loop observed in practice: the QA agent starts a batch, one call trips the hook, the batch collapses, Claude stalls, user must nudge it.

### Recommended avoidance strategies

- **Issue permission-prone calls solo, never inside a batch.** Any Bash call that is not pre-allowed should be a single-call turn, isolated from concurrent Playwright MCP or Read calls.
- **Pre-approve known-safe scripts via allow-list** so they never reach the permission prompt (see Section 4).
- **Never batch a Playwright MCP call with a Bash call** that has not been explicitly pre-approved — if the Bash side trips, the Playwright side is cancelled and the browser session may be in an inconsistent state.

---

## 2. The `cd` Permission-Prompt Trip

### Why it happens

Claude Code's permission system parses compound commands using shell separators (`&&`, `||`, `;`, `|`, `|&`, `&`, newline) and evaluates **each sub-command independently** against the allow-list. A rule like `Bash(cd *)` only matches a standalone `cd` invocation. If Claude writes `cd /some/path && uv run ...`, the `uv run ...` sub-command is evaluated separately and may require its own prompt.

There is also a documented subtlety: `cd` into a path inside the working directory is treated as read-only and is normally prompt-free. However, combining `cd` with `git` in the same compound command **always prompts regardless of directory**, per the permissions docs. There are also open bugs (issues #28183, #28784) where individually-allowed safe commands in a compound chain still trigger prompts with incorrect safety reasons — this is a known regression from an overly-broad security fix.

### Why it matters for QA

The `do_qa.md` Step 2 idiom `PORT=$(.claude/fls/scripts/find_available_port.sh)` followed by `uv run python manage.py runserver $PORT` is fine — no `cd` involved. But if an agent tries to navigate to a directory before running a command (a common LLM reflex), the compound command can trigger a prompt. If that prompt is batched with Playwright calls, the entire batch collapses.

### Concrete rewrites to avoid `cd` trips

| Risky pattern | Safe replacement |
|---|---|
| `cd /abs/path && uv run pytest` | `uv run pytest /abs/path` or use the script's `--rootdir` flag |
| `cd spec_dd && ls` | `ls spec_dd/` or `ls /abs/path/spec_dd/` |
| `cd $CLAUDE_PLUGIN_ROOT/scripts && ./qa_cleanup.sh` | `$CLAUDE_PLUGIN_ROOT/scripts/qa_cleanup.sh` (already the pattern in do_qa.md) |

**Rule:** all Bash calls in `do_qa` must use absolute paths or paths relative to the working directory. No `cd` before a command.

---

## 3. The `rm -rf` Hook Trip

### How the hook works

`security-guard.sh` checks the literal substring `rm -rf` in the Bash command string (line 64). If it matches, it exits 2 immediately. The hook is registered as PreToolUse for `Bash|Write|Edit`, so it fires before permission rules.

A blocking hook also takes precedence over allow rules (from the permissions docs): "A hook that exits with code 2 stops the tool call before permission rules are evaluated, so the block applies even when an allow rule would otherwise let the call proceed."

This means `rm -rf` **cannot** be allowed via `settings.json` — the hook will block it regardless.

### The fix pattern already in use: script wrapping

`qa_cleanup.sh` wraps the `rm -rf` in a committed shell script. The agent runs:
```
${CLAUDE_PLUGIN_ROOT}/scripts/qa_cleanup.sh
```
The Bash command string Claude Code sees is just the script path — no `rm -rf` literal — so the hook passes. The deletion happens inside the script's subprocess, which the hook does not inspect.

This is the correct approach: **prefer script wrapping over weakening the hook**.

### Other spots where `rm -rf` might appear

Reviewing the QA flow in `do_qa.md`:

| Step | Current command | Risk |
|---|---|---|
| Step 1 (cleanup) | `$CLAUDE_PLUGIN_ROOT/scripts/qa_cleanup.sh` | Safe — already wrapped |
| Step 2 (port) | `$CLAUDE_PLUGIN_ROOT/scripts/find_available_port.sh` | Safe |
| Step 10 (kill server) | `.claude/fls/scripts/kill_runserver.sh $PORT` | Safe |
| Step 8 (compress) | `uv run --with pillow python $CLAUDE_PLUGIN_ROOT/scripts/compress_screenshots.py` | Safe |

The QA flow itself is already clean. The churn risk is from **the QA agent deciding on its own** to remove stale files mid-run (e.g. clearing a screenshots dir before retaking a shot) or the `fls:qa-data-helper` sub-agent running cleanup commands. Both could reach for `rm -rf` directly.

### Should the security guard be loosened?

**No.** The hook is a security control and the pattern of wrapping deletions in committed scripts is strictly better:
- The script is version-controlled and code-reviewed.
- The scope of what gets deleted is explicit and bounded.
- Weakening the hook (e.g. allowing `rm -rf` under `spec_dd/screenshots`) would require the hook to correctly parse relative paths from an arbitrary CWD, which is fragile.
- The wrapping pattern scales: any new deletion operation just gets a new script.

**Recommendation:** add a `qa_clear_screenshots.sh` script alongside `qa_cleanup.sh` if the agent ever needs to clear only the screenshots directory mid-run, and reference it in `do_qa.md`.

---

## 4. Permission Allow-Listing

### How the allow-list prevents cascade-cancels

From the permissions docs: allow rules are evaluated before a permission prompt is shown. If a command matches an allow rule, Claude Code runs it immediately with no prompt. No prompt means no possible user-denial, which means no hook-or-denial event that could cancel sibling calls. Pre-approving all commands a QA run needs is the most reliable way to make the QA flow prompt-free and batch-safe.

### Current allow-list gaps (from `.claude/settings.json`)

What is currently allowed that covers QA:
- `mcp__playwright__*` — Playwright MCP is fully pre-approved.
- `Bash(.claude/fls/scripts/kill_runserver.sh:*)` — kill server is covered.
- `Bash(uv run pytest:*)` — test runs are covered.

What is **missing** from the allow-list:

| Command | Required allow-list entry |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/scripts/qa_cleanup.sh` | `"Bash($CLAUDE_PLUGIN_ROOT/scripts/qa_cleanup.sh)"` — but env-var expansion may not work in JSON; use the resolved path or a `.claude/fls/scripts/` path alias |
| `.claude/fls/scripts/find_available_port.sh` | `"Bash(.claude/fls/scripts/find_available_port.sh*)"` |
| `uv run python manage.py runserver *` | `"Bash(uv run python manage.py runserver *)"` |
| `uv run --with pillow python * compress_screenshots.py *` | `"Bash(uv run --with pillow python * compress_screenshots.py *)"` — or move to `.claude/fls/scripts/` and allow that path |
| `Agent(fls:qa-data-helper)` | `"Agent(fls:qa-data-helper)"` (if agent tool requires permission) |

Note on env-var paths in allow rules: the permissions docs note that rules are literal pattern strings. `$CLAUDE_PLUGIN_ROOT` will not be expanded at match time. Scripts called from `do_qa.md` via `${CLAUDE_PLUGIN_ROOT}/...` should be referenced in the allow-list using the resolved path relative to the project root, e.g. `"Bash(fls-claude-plugin/scripts/qa_cleanup.sh)"` (assuming CWD is the worktree root).

### Recommended full allow-list additions for QA

```json
"Bash(uv run python manage.py runserver *)",
"Bash(.claude/fls/scripts/find_available_port.sh)",
"Bash(fls-claude-plugin/scripts/qa_cleanup.sh)",
"Bash(uv run --with pillow python * compress_screenshots.py *)",
"Bash(ss -tlnp*)",
"Bash(kill *)"
```

The `ss` and `kill` entries cover what `kill_runserver.sh` does internally (it calls `ss` and `kill`), though since the script itself is already allowed this should not matter unless the agent calls `ss`/`kill` directly.

---

## 5. Resilient Batching Guidance for `/do_qa`

### Core rules

1. **Solo rule for Bash calls that are not yet pre-approved.** If a new Bash command is added to `do_qa.md` that has no allow-list entry and no script wrapper, it must be issued in its own turn, never inside a batch with Playwright MCP calls.

2. **Never batch a Playwright MCP call with a permission-prone Bash call.** Playwright calls open or interact with a browser page. If the Bash side is cancelled by cascade, the browser is left in an undefined state (page may be mid-navigation). The next Playwright call in the retry will see stale DOM.

3. **All file deletions must go through committed wrapper scripts.** No agent at any depth (depth-0 QA, `fls:qa-data-helper`, `fls:sdd-worker`) should issue `rm -rf` as a raw Bash command. If a new deletion is needed, add a script and update the allow-list.

4. **No `cd` before commands.** Use absolute paths or CWD-relative paths throughout. The `do_qa.md` already follows this; reinforce it explicitly.

5. **Server start is a solo call.** `uv run python manage.py runserver $PORT` is a long-running background process. It should always be issued as a standalone call, never batched.

6. **Sub-agent spawns (Agent tool) should be solo.** Calling `fls:qa-data-helper` via the Agent tool is a heavyweight, long-running operation. It should never be batched with Playwright or Bash calls.

### Wording to add to `/do_qa`

Add a "Batching safety rules" block near the top CRITICAL section:

```
## CRITICAL: Batching safety rules

- Never issue a Bash call in the same turn as a Playwright MCP call unless BOTH are
  pre-approved in .claude/settings.json. If either could trigger a permission prompt
  or a hook block, issue the Bash call solo first, wait for it to complete, then
  proceed with Playwright.
- Never run `rm -rf` directly in Bash. Use the provided wrapper scripts only.
- Never use `cd` before a command. Use absolute or CWD-relative paths.
- The development server start (`uv run python manage.py runserver`) must be a solo call.
- `fls:qa-data-helper` delegation must be a solo Agent call.
```

---

## Recommendations for FLS

### Things to script-wrap

- Any mid-run screenshot directory clear (currently done by `qa_cleanup.sh` at the start; if a mid-run clear is ever needed, add `qa_clear_screenshots.sh`).
- Any `rm -rf` operation that `fls:qa-data-helper` might perform (e.g. clearing temp fixture files). Give it a dedicated `qa_data_cleanup.sh`.

### Allow-list entries to add to `.claude/settings.json`

```json
"Bash(uv run python manage.py runserver *)",
"Bash(.claude/fls/scripts/find_available_port.sh)",
"Bash(fls-claude-plugin/scripts/qa_cleanup.sh)",
"Bash(uv run --with pillow python * compress_screenshots.py *)"
```

Verify resolved paths match how `do_qa.md` calls each script (with or without `${CLAUDE_PLUGIN_ROOT}`). The simplest approach is to move all QA scripts under `.claude/fls/scripts/` (which is already the pattern for `kill_runserver.sh` and `find_available_port.sh`) so a single `Bash(.claude/fls/scripts/* *)` wildcard can cover them all — but check that the wildcard semantics (spaces and `*`) actually match the call forms.

### Command wording to add to `/do_qa`

1. Add the "Batching safety rules" CRITICAL block (text above in Section 5).
2. In Step 1, add: "Run this as a solo Bash call before any other step."
3. In Step 2 (server start), add: "Run this as a solo Bash call. Do not batch with any Playwright call."
4. In Step 5 (Playwright testing), add: "Before issuing any Playwright MCP call, ensure no Bash call is pending in the same turn."
5. General note: "If a Bash command is not listed in `.claude/settings.json` allow rules, issue it solo (not in a batch with any other tool call)."

---

## References

- [Sibling tool call errored: parallel tool calls cascade-fail when one fails — Issue #22264](https://github.com/anthropics/claude-code/issues/22264)
- [PreToolUse hook exit code 2 causes Claude to stop instead of acting on error feedback — Issue #24327](https://github.com/anthropics/claude-code/issues/24327)
- [Compound commands of individually-allowed safe commands prompt with incorrect safety reason — Issue #28183](https://github.com/anthropics/claude-code/issues/28183)
- [Permission rule Bash(cd:*) allows arbitrary command execution via && chaining — Issue #28784](https://github.com/anthropics/claude-code/issues/28784)
- [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [Configure permissions — Claude Code Docs](https://code.claude.com/docs/en/permissions)
- [Parallel tool use — Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)

---

status: ok
reason: all five research sections completed with citations; concrete allow-list entries and /do_qa wording derived from actual files
