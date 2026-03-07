---
description: Execute a frontend QA test plan using Playwright MCP
allowed-tools: Read, Write, Glob, mcp__playwright*
---

Act like a human QA expert. Execute the given test plan

# Useful info

- Base url: http://127.0.0.1:8000/
- Admin email and password: demodev@email.com
- to run the server: `uv run python manage.py runserver`

# CRITICAL

You MUST use Playwright MCP. If you can't use it then:

- Explain why you can't use it
- Explain how to fix the error
- DO NOT CONTINUE WITH THE TESTS IF YOU CAN'T USE PLAYWRIGHT

Before doing anything else, use playwright to open the base url and make sure it works.

# Instructions

## Step 1

Make sure the playwright MCP is available. If it is not available then say:
"Please install the playwright mcp server, then try again"

## Step 2

Clean up last QA run
- if there is a qa_report in the current directory, delete it
- if there is a screenshots directory in the current directory, delete it

## Step 3: Login

Navigate to the base url and log in using the admin credentials above. Confirm you are logged in before proceeding with the test plan.

## Step 4: Desktop testing

Use the Playwright MCP server tools (browser_navigate, browser_snapshot, browser_click, browser_type, browser_take_screenshot, etc.) to manually walk through the test plan. Do NOT write test scripts — interact with the site directly using the MCP tools, just as a human tester would.

Set the browser to a desktop resolution of 1920x1080.

Take screenshots of relevant functionality and put them in a "screenshots" directory in this current directory (alongside the frontend_qa file). Name screenshots with this pattern: `desktop_<test-id>_<short-description>.png` (e.g. `desktop_1.1_cohort_list.png`).

If anything unrelated to the current feature under test seems out of place or broken then use a sub agent to explore it.

**IMPORTANT** If you are unable to run a test due to missing or incorrect data then make use of the qa-data-helper agent. Tell the agent what data you need and what changes you need made.

## Step 5: Mobile testing

Resize the browser to 375x812 (iPhone-sized viewport).

You do NOT need to re-run every test from Step 4. Focus on:
- Navigation and menu behaviour (hamburger menus, drawers, etc.)
- Layout and readability — do elements overflow, overlap, or become unusable?
- Touch-target sizing — are buttons and links large enough?
- Any test from Step 4 that involves tables, forms, or multi-column layouts

Name mobile screenshots with the pattern: `mobile_<test-id>_<short-description>.png`.

## Step 6: Tablet testing

Resize the browser to 768x1024 (iPad-sized viewport).

As with mobile testing, you do NOT need to re-run every test. Focus on:
- Navigation and menu behaviour — does the tablet get the desktop nav or mobile nav? Does it work correctly?
- Multi-column layouts, tables, and grids — do they adapt sensibly at this width?
- Sidebars and panels — are they still usable or do they crowd the main content?
- Forms and modals — do they render at a reasonable width?

Name tablet screenshots with the pattern: `tablet_<test-id>_<short-description>.png`.

## Step 7: Generate a report

Create a new file called qa_report.md (in the same directory as the frontend_qa file we are working with).

For each error:
- give it a title
- include relevant screenshots using markdown syntax
- mention the test that was failed
- say what the expected behavior was, and what the actual behavior was

If anything was not tested for any reason, or if there were any difficulties, then explain.

If anything unrelated to the current tests, or tangential to the functionality under test seemed out of place then include that in the report.
