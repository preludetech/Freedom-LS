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
- if there is an images directory in the current directory, delete it

## Step 3

Use the Playwright MCP server tools (browser_navigate, browser_snapshot, browser_click, browser_type, browser_take_screenshot, etc.) to manually walk through the test plan. Do NOT write test scripts — interact with the site directly using the MCP tools, just as a human tester would.

Make sure the browser is maximised, it should take up the whole screen

Take screenshots of relevant functionality and put them in a "screenshots" directory in this current directory (alongside the frontend_qa file). Make sure the screenshots are named in a way that ties them back to the specific test you are running through.

If anything unrelated to the current feature under test seems out of place or broken then use a sub agent to explore it.

## Step 4: Repeat the whole QA test for mobile 

Execute the whole test again, but this time size the browser as though it were a mobile phone.

Note any issues with mobile responsiveness.

## Step 5: Generate a report

Create a new file called qa_report.md (in the same directory as the frontend_qa file we are working with).

For each error:
- give it a title
- include relevant screenshots using markdown syntax
- mention the test that was failed
- say what the expected behavior was, and the desired behavior

If anything was not tested for any reason, or if there were any difficulties, then explain.

If anything unrelated to the current tests, or tangentiual to the functionality under test seemed out of place then include that in the report.


