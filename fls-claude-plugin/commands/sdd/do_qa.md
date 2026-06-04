---
description: Execute a frontend QA test plan using Playwright MCP
allowed-tools: Read, Write, Glob, Bash, Agent, mcp__playwright*
---

Act like a human QA expert. Execute the given test plan. This command runs at **depth 0**, so its `fls:qa-data-helper` delegation and the Step 7 desktop-testing exploration spawn are legal. See the `claude-code-authoring` skill for the model behind this.

---

## Table of contents

1. [Clean up last QA run](#step-1-clean-up-last-qa-run)
2. [Diff-scoping gate](#step-2-diff-scoping-gate) ← NEW
3. [Find an unused PORT and start the dev server](#step-3-find-an-unused-port-and-start-the-dev-server)
4. [Check that runserver is pointing at the right branch](#step-4-check-that-runserver-is-pointing-at-the-right-branch)
5. [Login](#step-5-login)
6. [Smoke gate](#step-6-smoke-gate) ← NEW
7. [Desktop testing](#step-7-desktop-testing)
8. [Mobile testing](#step-8-mobile-testing)
9. [Tablet testing](#step-9-tablet-testing)
10. [Collect screenshots into the spec dir](#step-10-collect-screenshots-into-the-spec-dir) ← NEW
11. [Compress screenshots](#step-11-compress-screenshots)
12. [Generate a report](#step-12-generate-a-report)
13. [Clean up the dev server](#step-13-clean-up-the-dev-server)
14. [Update the todo list](#step-14-update-the-todo-list)

---

# Useful info

- To run the server: `uv run python manage.py runserver $PORT`
- If another process is using the port you would like, then try another
- Base url: http://127.0.0.1:$PORT/
- Read `.claude/fls/config.md` for admin credentials

---

# CRITICAL: rules that apply throughout this command

These rules apply at **every** step — stated once here; later steps refer back to them.

## Rule 1 — You MUST use Playwright MCP

If you can't use it: explain why, explain how to fix the error, and **do not continue with the tests**. Before doing anything else, use Playwright to open the base url and make sure it works.

## Rule 2 — Test data comes from `fls:qa-data-helper`

**Test data is created by the `fls:qa-data-helper` agent — NOT by you.** If a test cannot be executed because the dev database lacks the required data (e.g. a paginator can't be exercised because there aren't enough rows, a panel can't be tested because no instance of the relevant model exists, a flow can't be walked because a user/cohort/course is missing), you MUST delegate to the **`fls:qa-data-helper`** agent via the `Agent` tool.

Do NOT:
- Run `manage.py shell` yourself to create data
- Run ad-hoc ORM scripts yourself to create data
- Mark a test as `PARTIAL` / `N/A` / `NOT EXECUTED` because of missing data without first invoking `fls:qa-data-helper` to fix the gap
- Skip a test that `fls:qa-data-helper` could unblock

Do:
- Spawn the `fls:qa-data-helper` agent and tell it exactly what data shape you need (entity counts, relationships, which Site, which fixtures it should attach to)
- Wait for it to confirm the data exists, then re-attempt the test
- Only mark a test PARTIAL / skipped if `fls:qa-data-helper` itself reports the scenario is impossible to set up

## Rule 3 — Batching safety rules

These rules prevent the most common prompt/permission cascade-cancels and stalls:

**3a. Never mix a `Bash` call with a Playwright MCP call in the same turn** unless both are
pre-approved in `.claude/settings.json`. If either could trigger a permission prompt or trip a
pre-tool hook, issue the `Bash` call **solo** first, wait for it to complete, then proceed with
Playwright. A single denied sibling cancels the entire batch — losing all results from that turn.

**3b. Never run a raw recursive force-delete directly.** Only use committed wrapper scripts
(`qa_cleanup.sh`, `qa_collect_screenshots.sh`). A raw recursive removal (the flag combination
`rm` + a recursive flag + a force flag) would be blocked by the `security-guard` Write hook
and would stall any batch containing it. Describe the dangerous delete in prose; never paste
the literal flag string in this file.

**3c. Never `cd` before a command.** Use absolute paths or CWD-relative paths. A compound like
`cd X && git …` always triggers a permission prompt and collapses any batch it is in.

**3d. The dev-server start (`runserver`) is always a solo call.** Never batch it with any other
tool call in the same turn.

**3e. Any `Agent` spawn is always a solo call.** This applies to all agents: `fls:qa-data-helper`,
`fls:sdd-worker`, `fls:sdd-mechanic`, and `fls:qa-bugfixer`. Never batch an `Agent` call with
a `Bash` or Playwright call in the same turn.

---

# Instructions

## Step 1: Clean up last QA run

Remove artifacts from the previous QA run (the `qa_report.md` and `screenshots/` directory in the
current directory). Use the stable project-relative wrapper path:

`.claude/fls/scripts/qa_cleanup.sh`

No pre-emptive server kill is needed here: Step 3 always selects an unused port, and Step 13 kills
the server this run started. A stale server left by a crashed earlier run is harmless — it just
occupies a port Step 3 will skip.

---

## Step 2: Diff-scoping gate

Run the following **solo** Bash call (git diff is allow-listed; keep it solo — do not batch with
any Playwright call):

`git diff main...HEAD --name-only`

Classify the changed files using this table:

| Class | Trigger condition |
|---|---|
| `FULL` | Any changed path matches `templates/`, `*.html`, `*.css`, `*.js`, or `static/` |
| `ADMIN_ONLY` | Every changed path is under `admin.py` or an `admin/` surface only (no template/css/js) |
| `BACKEND_ONLY` | Changed paths are only `*.py` (views, models, logic) with no template, CSS, or JS |
| `FULL` | Safe default — anything that does not clearly match ADMIN_ONLY or BACKEND_ONLY |

**Classification rules (apply in order):**
1. If any changed path contains `templates/`, ends in `.html`, `.css`, `.js`, or contains `static/` → `CLASS = FULL`.
2. Else if every changed path is `admin.py` or inside an `admin/` directory → `CLASS = ADMIN_ONLY`.
3. Else if every changed path ends in `.py` and no path matches templates/static/css/js → `CLASS = BACKEND_ONLY`.
4. Else → `CLASS = FULL` (safe default — never under-test on misclassification).

**What each class runs:**
- `FULL` → desktop (Step 7) + mobile (Step 8) + tablet (Step 9).
- `ADMIN_ONLY` → desktop only (Step 7); skip Steps 8 and 9.
- `BACKEND_ONLY` → single-viewport smoke pass only (Step 7 abbreviated to smoke-level checks); skip Steps 8 and 9.

**This gate MUST be explicit and reported.** Record the classification and the list of changed files
that triggered it (keep a running note in working memory or a scratch file), so `qa_report.md` states:
- Which class fired.
- What was therefore NOT run (e.g. "Mobile and tablet passes skipped — ADMIN_ONLY classification").

No silent scoping: omitting the classification from the report is a failure mode.

---

## Step 3: Find an unused PORT and start the dev server

Find an unused PORT. Issue this as a **solo** Bash call:

`PORT=$(.claude/fls/scripts/find_available_port.sh)`

Then start the dev server. **This must be its own solo call — never batch runserver with any other
tool:**

`uv run python manage.py runserver $PORT`

**CRITICAL** There might be other servers running, and those might be associated with different
branches or applications. It is CRITICAL that you do not use existing processes. Launch your own
`runserver` at your own port!

---

## Step 4: Check that runserver is pointing at the right branch

Go to the base url at http://127.0.0.1:$PORT/ using the Playwright MCP (if Playwright MCP is
unavailable, follow Rule 1 in the CRITICAL section above and STOP).

Look for the debug-branch-badge on the bottom left of the page. It has the id `debug-branch-badge`.
It should name the current branch.

If the debug-branch-badge names a branch other than the one we are on then that means that there is
a PORT collision and some other process is using the PORT we chose. If this happens, return to Step 3.

---

## Step 5: Login

If you don't need to log in, go to Step 6.

Navigate to the base url and log in using the credentials above. Confirm you are logged in before
proceeding.

---

## Step 6: Smoke gate

Before running the full matrix, load the two most critical pages:

1. The site home page (http://127.0.0.1:$PORT/).
2. The primary changed page — the main URL most directly affected by this diff (derive it from the
   test plan or from the changed file paths identified in Step 2).

For each page:
- Take a snapshot (`browser_snapshot`).
- Check for HTTP 500 / 404 responses, Python tracebacks visible on screen, or missing critical
  elements (e.g. the main navigation, the primary content area).

**On smoke failure (any page returns 500, 404, or shows a traceback / critical missing element):**
- **Abort the remaining matrix immediately.** Do not proceed to Steps 7–9.
- Jump directly to Step 12 (Generate a report).
- Write a report that records:
  - Which page failed the smoke gate and why (exact error, URL, screenshot).
  - That the full matrix was NOT run because of the smoke failure.
  - The diff-scoping classification from Step 2.
- Then proceed to Steps 13–14 (cleanup and todo update) as normal, adding a failing-test `add:` entry.

**On smoke success:** continue to Step 7.

Record the smoke gate outcome (pass/fail + which pages were loaded) alongside the diff-scoping
classification from Step 2, so the report (Step 12) can include both.

---

## Step 7: Desktop testing

Use the Playwright MCP server tools (`browser_navigate`, `browser_snapshot`, `browser_click`,
`browser_type`, `browser_take_screenshot`, etc.) to manually walk through the test plan.
DO NOT write test scripts — interact with the site directly using the MCP tools, just as a human
tester would.

Set the browser to a desktop resolution of 1920x1080.

Take screenshots of relevant functionality. Name screenshots with this pattern:
`desktop_<test-id>_<short-description>.png` (e.g. `desktop_1.1_cohort_list.png`).

**Per-run capture check (mandatory — see Task A in the implementation plan):** Early in this step,
do a one-shot `browser_take_screenshot` and confirm a file actually appears in the capture buffer
while **no image bytes return** in the tool response. If image bytes are returned (i.e.
`--image-responses omit` appears broken in the resolved `@latest`), or if no file is written at all,
stop and report the issue — do not trust the rest of the run until this is resolved. If `--output-dir`
appears broken in the resolved version, discover where the server actually wrote the files and record
that path; the collect step (Step 10) will need to collect from there.

If anything unrelated to the current feature under test seems out of place or broken, spawn **one
`fls:sdd-worker`** to explore it (non-interactive; it returns a structured `status`/`reason`). This
is a single ad-hoc probe — no scratch-file resume is needed — but it follows the "one subagent per
unit + structured return" shape so no fan-out site is left ad-hoc. **This spawn is a solo call.**

If you are unable to run a test due to missing or incorrect data, follow Rule 2: delegate to
`fls:qa-data-helper` rather than creating the data yourself or skipping the test. **This spawn is
also a solo call.**

Skip this step (or run only abbreviated smoke-level checks) if `CLASS = BACKEND_ONLY` (Step 2).

---

## Step 8: Mobile testing

**Skip this step if `CLASS = ADMIN_ONLY` or `CLASS = BACKEND_ONLY` (Step 2).**

Don't do mobile tests if we are checking the django admin interface. Only do mobile tests for custom
frontend code.

Resize the browser to 375x812 (iPhone-sized viewport).

You do NOT need to re-run every test from Step 7. Focus on:
- Navigation and menu behaviour (hamburger menus, drawers, etc.)
- Layout and readability — do elements overflow, overlap, or become unusable?
- Touch-target sizing — are buttons and links large enough?
- Any test from Step 7 that involves tables, forms, or multi-column layouts

Name mobile screenshots with the pattern: `mobile_<test-id>_<short-description>.png`.

---

## Step 9: Tablet testing

**Skip this step if `CLASS = ADMIN_ONLY` or `CLASS = BACKEND_ONLY` (Step 2).**

Don't do tablet tests if we are checking the django admin interface. Only do tablet tests for custom
frontend code.

Resize the browser to 768x1024 (iPad-sized viewport).

As with mobile testing, you do NOT need to re-run every test. Focus on:
- Navigation and menu behaviour — does the tablet get the desktop nav or mobile nav? Does it work correctly?
- Multi-column layouts, tables, and grids — do they adapt sensibly at this width?
- Sidebars and panels — are they still usable or do they crowd the main content?
- Forms and modals — do they render at a reasonable width?

Name tablet screenshots with the pattern: `tablet_<test-id>_<short-description>.png`.

---

## Step 10: Collect screenshots into the spec dir

Screenshots are captured by the Playwright MCP server into `${CLAUDE_PROJECT_DIR}/qa-screenshots/`
(a fixed path set at server launch via `--output-dir`; it cannot be overridden per-call). The
`qa_report.md` file links screenshots as `![](screenshots/…)` relative to itself, inside the spec
dir. This step **moves** the run's screenshots from the capture dir into `<spec-dir>/screenshots/`
so those links resolve.

Call the committed collect script with the spec dir as argument — **this is a solo Bash call**:

`.claude/fls/scripts/qa_collect_screenshots.sh <spec-dir>`

Where `<spec-dir>` is the directory containing the test plan and where `qa_report.md` will be
written (i.e. the same directory as this run's test plan file).

The script:
1. Validates that `<spec-dir>` is inside `${CLAUDE_PROJECT_DIR}` (exits non-zero otherwise).
2. Creates `<spec-dir>/screenshots/` if it does not exist.
3. Moves every file from `${CLAUDE_PROJECT_DIR}/qa-screenshots/` into `<spec-dir>/screenshots/`.
4. Removes the now-empty `${CLAUDE_PROJECT_DIR}/qa-screenshots/` directory (a safe `rmdir` on an
   emptied directory — not a recursive delete).

**If the script exits non-zero:** check whether screenshots landed somewhere else (e.g. if
`--output-dir` is broken in the resolved `@latest` as noted in Step 7's per-run capture check).
Discover the actual write location and adjust the collect call accordingly.

After this step, `<spec-dir>/screenshots/` should contain all screenshots from this run.

---

## Step 11: Compress screenshots

Compress all screenshots to reduce file sizes:

`uv run --with pillow python ${CLAUDE_PLUGIN_ROOT}/scripts/compress_screenshots.py`

---

## Step 12: Generate a report

Create a new file called `qa_report.md` in the same directory as the test plan file.

The report MUST include:

**Methodology section:**
- The diff-scoping classification from Step 2 (e.g. `CLASS = FULL`) and the changed files that
  triggered it.
- What was therefore NOT run (e.g. "Mobile and tablet passes skipped — ADMIN_ONLY classification").
  If everything was run, say so explicitly.
- The smoke gate outcome from Step 6 (pass/fail, which pages were loaded). If the smoke gate failed
  and aborted the run, state this prominently.
- A note that screenshots were moved from `${CLAUDE_PROJECT_DIR}/qa-screenshots/` into
  `<spec-dir>/screenshots/` by the collect step.

**For each error:**
- Give it a title.
- Include relevant screenshots using markdown image syntax: `![](screenshots/<filename>.png)`
- Mention the test that failed.
- Say what the expected behavior was, and what the actual behavior was.

**General notes:**
- If anything was not tested for any reason, or if there were any difficulties, explain.
- If anything unrelated to the current tests or tangential to the functionality under test seemed
  out of place, include it in the report.

---

## Step 13: Clean up the dev server

Kill the development server you started:

`.claude/fls/scripts/kill_runserver.sh $PORT`

---

## Step 14: Update the todo list

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory (same directory as `qa_report.md`)
- `tick:"Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `fls:qa-data-helper` agent)"`
- For each failing test recorded in `qa_report.md`, pass one `add:"QA|user + cmd|Fix QA bug: <short title from the report> (TDD — failing test first, then fix)"`.
- For each test that was skipped because of missing data, pass one `add:"QA|cmd|Use the `fls:qa-data-helper` agent to create missing data for <short description>, then re-run `/do_qa`"`.
- If the smoke gate failed (Step 6), pass one `add:"QA|user|Fix smoke gate failure: <short description of the failure> before re-running `/do_qa`"`.
- If no bugs were found, no tests were skipped, and the smoke gate passed, omit `add:`.
