---
description: Execute a frontend QA test plan using Playwright MCP
allowed-tools: Read, Write, Glob, Bash, Agent, mcp__playwright*
---

Act like a human QA expert. Execute the given test plan. This command runs at **depth 0**, so its `fls:qa-data-helper` delegation and the Step 5 exploration spawn are legal. See the `claude-code-authoring` skill for the model behind this.

# Useful info

- To run the server: `uv run python manage.py runserver $PORT`
- If another process is using the port you would like, then try another
- Base url: http://127.0.0.1:$PORT/
- Read `.claude/fls/config.md` for admin credentials

# CRITICAL: rules that apply throughout this command

These two rules apply at **every** step (Desktop, Mobile, Tablet) — stated once here; later steps refer back to them.

1. **You MUST use Playwright MCP.** If you can't use it, then: explain why, explain how to fix the error, and **do not continue with the tests**. Before doing anything else, use Playwright to open the base url and make sure it works.
2. **Test data is created by the `fls:qa-data-helper` agent — NOT by you.** If a test cannot be executed because the dev database lacks the required data (e.g. a paginator can't be exercised because there aren't enough rows, a panel can't be tested because no instance of the relevant model exists, a flow can't be walked because a user/cohort/course is missing), you MUST delegate to the **`fls:qa-data-helper`** agent via the `Agent` tool.

   Do NOT:
   - Run `manage.py shell` yourself to create data
   - Run ad-hoc ORM scripts yourself to create data
   - Mark a test as `PARTIAL` / `N/A` / `NOT EXECUTED` because of missing data without first invoking `fls:qa-data-helper` to fix the gap
   - Skip a test that `fls:qa-data-helper` could unblock

   Do:
   - Spawn the `fls:qa-data-helper` agent and tell it exactly what data shape you need (entity counts, relationships, which Site, which fixtures it should attach to)
   - Wait for it to confirm the data exists, then re-attempt the test
   - Only mark a test PARTIAL / skipped if `fls:qa-data-helper` itself reports the scenario is impossible to set up

# Instructions

## Step 1: Clean up last QA run

Remove artifacts from the previous QA run (the `qa_report.md` and `screenshots/` directory in the current directory):

`${CLAUDE_PLUGIN_ROOT}/scripts/qa_cleanup.sh`

No pre-emptive server kill is needed here: Step 2 always selects an unused port, and Step 10 kills the server this run started. A stale server left by a crashed earlier run is harmless — it just occupies a port Step 2 will skip.

## Step 2: Find an unused PORT

Find an unused PORT that we can use for running the development server.

`PORT=$(.claude/fls/scripts/find_available_port.sh)`

Then run the development server:

`uv run python manage.py runserver $PORT`

**CRITICAL** There might be other servers running, and those might be associated with different branches or applications. It is CRITICAL that you do not use existing processes. Launch your own `runserver` at your own port!


## Step 3: Check that the runserver is pointing at the right branch

Go to the base url at http://127.0.0.1:$PORT/ using the playwright MCP (if Playwright MCP is unavailable, follow rule 1 in the CRITICAL section above and STOP).

Look for the debug-branch-badge on the bottom left of the page. It has the id `debug-branch-badge`. It should name the current branch.

If the debug-branch-badge names a branch other than the one we are on then that means that there is a PORT collision and some other process is using the PORT we chose. If this happens, return to STEP 2.

## Step 4: (Optional) Login

If you don't need to log in, go to Step 5

Navigate to the base url and log in using the credentials above. Confirm you are logged in before proceeding with the test plan.

## Step 5: Desktop testing

Use the Playwright MCP server tools (browser_navigate, browser_snapshot, browser_click, browser_type, browser_take_screenshot, etc.) to manually walk through the test plan.
DO NOT write test scripts — interact with the site directly using the MCP tools, just as a human tester would.

Beyond the scripted steps, probe the obvious failure/side-effect branches for the functionality under test (e.g. repeat submissions, an existing account instead of a fresh one, invalid input, permission/enumeration edges) — not just the golden path. Keep it proportionate.

Set the browser to a desktop resolution of 1920x1080.

Take screenshots of relevant functionality and put them in a "screenshots" directory in this current directory (alongside the test plan file). Name screenshots with this pattern: `desktop_<test-id>_<short-description>.png` (e.g. `desktop_1.1_cohort_list.png`).

If anything unrelated to the current feature under test seems out of place or broken, spawn **one `fls:sdd-worker`** to explore it (non-interactive; it returns a structured `status`/`reason`). This is a single ad-hoc probe — no scratch-file resume is needed — but it follows the "one subagent per unit + structured return" shape so no fan-out site is left ad-hoc.

If you are unable to run a test due to missing or incorrect data, follow rule 2 in the CRITICAL section above: delegate to `fls:qa-data-helper` rather than creating the data yourself or skipping the test.

## Step 6: Mobile testing

Don't do mobile tests if we are checking the django admin interface. Only do mobile tests for custom frontend code.


Resize the browser to 375x812 (iPhone-sized viewport).

You do NOT need to re-run every test from Step 5. Focus on:
- Navigation and menu behaviour (hamburger menus, drawers, etc.)
- Layout and readability — do elements overflow, overlap, or become unusable?
- Touch-target sizing — are buttons and links large enough?
- Any test from Step 5 that involves tables, forms, or multi-column layouts

Name mobile screenshots with the pattern: `mobile_<test-id>_<short-description>.png`.

## Step 7: Tablet testing

Don't do tablet tests if we are checking the django admin interface. Only do tablet tests for custom frontend code.


Resize the browser to 768x1024 (iPad-sized viewport).

As with mobile testing, you do NOT need to re-run every test. Focus on:
- Navigation and menu behaviour — does the tablet get the desktop nav or mobile nav? Does it work correctly?
- Multi-column layouts, tables, and grids — do they adapt sensibly at this width?
- Sidebars and panels — are they still usable or do they crowd the main content?
- Forms and modals — do they render at a reasonable width?

Name tablet screenshots with the pattern: `tablet_<test-id>_<short-description>.png`.

## Step 8: Compress screenshots

Compress all screenshots to reduce file sizes:

`uv run --with pillow python ${CLAUDE_PLUGIN_ROOT}/scripts/compress_screenshots.py`

## Step 9: Generate a report

Create a new file called qa_report.md (in the same directory as the test plan file).

For each error:
- give it a title
- include relevant screenshots using markdown image syntax: `![](screenshots/<filename>.png)`
- mention the test that was failed
- say what the expected behavior was, and what the actual behavior was

If anything was not tested for any reason, or if there were any difficulties, then explain.

If anything unrelated to the current tests, or tangential to the functionality under test seemed out of place then include that in the report.

## Step 10: Clean up

Kill the development server you started:

`.claude/fls/scripts/kill_runserver.sh $PORT`

## Step 11: Update the todo list

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory (same directory as `qa_report.md`)
- `tick:"Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `fls:qa-data-helper` agent)"`
- For each failing test recorded in `qa_report.md`, pass one `add:"QA|user + cmd|Fix QA bug: <short title from the report> (TDD — failing test first, then fix)"`.
- For each test that was skipped because of missing data, pass one `add:"QA|cmd|Use the `fls:qa-data-helper` agent to create missing data for <short description>, then re-run `/do_qa`"`.
- If no bugs were found and no tests were skipped, omit `add:`.
